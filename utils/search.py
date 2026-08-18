import logging
import os

logger = logging.getLogger('noticeboard')

MAX_SEARCH_RESULTS = int(os.getenv('NOTICEBOARD_MAX_SEARCH_RESULTS', '1000'))
MAX_FILTERED_SEARCH_RESULTS = int(
    os.getenv('NOTICEBOARD_MAX_FILTERED_SEARCH_RESULTS', '10000')
)

# Below this many hits a phase escalates to the next. Escalating only on zero
# strands a misspelling that also appears in the notices themselves.
MIN_SEARCH_RESULTS = int(os.getenv('NOTICEBOARD_MIN_SEARCH_RESULTS', '5'))
REQUEST_TIMEOUT = 3
RECENCY_DECAY_ORIGIN = os.getenv('NOTICEBOARD_ES_RECENCY_ORIGIN', 'now')
RECENCY_DECAY_SCALE = os.getenv('NOTICEBOARD_ES_RECENCY_SCALE', '365d')
RECENCY_DECAY_OFFSET = os.getenv('NOTICEBOARD_ES_RECENCY_OFFSET', '30d')
RECENCY_DECAY_FACTOR = float(os.getenv('NOTICEBOARD_ES_RECENCY_DECAY', '0.5'))

# The share of the score recency can never take away. At zero the gaussian
# multiplies old but perfect matches out of the results entirely.
RECENCY_DECAY_FLOOR = float(os.getenv('NOTICEBOARD_ES_RECENCY_FLOOR', '0.5'))


class ElasticsearchUnavailable(Exception):
    """
    Raised when Elasticsearch cannot serve a query and the caller should
    fall back to PostgreSQL full-text search
    """


def _wrap_with_recency_decay(query_dict):
    return {
        'function_score': {
            'query': query_dict,
            'functions': [
                {
                    'gauss': {
                        'datetime_modified': {
                            'origin': RECENCY_DECAY_ORIGIN,
                            'scale': RECENCY_DECAY_SCALE,
                            'decay': RECENCY_DECAY_FACTOR,
                            'offset': RECENCY_DECAY_OFFSET,
                        }
                    },
                    'weight': 1 - RECENCY_DECAY_FLOOR,
                },
                {'weight': RECENCY_DECAY_FLOOR},
            ],
            'score_mode': 'sum',
            'boost_mode': 'multiply',
        }
    }


def _build_phases(keyword):
    """
    Build the strict, relaxed and fuzzy queries, tried in that order
    """

    from elasticsearch_dsl import Q as ES_Q

    draft_filter = ES_Q('term', is_draft=False)

    strict = ES_Q(
        'bool',
        must=[draft_filter],
        should=[
            ES_Q(
                'multi_match',
                query=keyword,
                type='phrase',
                fields=['title^5', 'content'],
            ),
            # Scores a partly typed word against the title. The wildcard below
            # matches one too, but is constant-scored and loses to any body hit.
            ES_Q(
                'match_phrase_prefix',
                title={
                    'query': keyword,
                    'max_expansions': 50,
                    'boost': 5,
                },
            ),
            ES_Q(
                'wildcard',
                title={
                    'value': f'*{keyword.lower()}*',
                    'boost': 2,
                },
            ),
        ],
        minimum_should_match=1,
    )

    relaxed = ES_Q(
        'bool',
        must=[
            draft_filter,
            ES_Q(
                'multi_match',
                query=keyword,
                fields=['title^5', 'content'],
                type='best_fields',
                minimum_should_match='2<75%',
            ),
        ],
    )

    fuzzy = ES_Q(
        'bool',
        must=[
            draft_filter,
            ES_Q(
                'multi_match',
                query=keyword,
                fields=['title^5', 'content'],
                fuzziness='AUTO',
                prefix_length=1,
                max_expansions=50,
            ),
        ],
    )

    return (('strict', strict), ('relaxed', relaxed), ('fuzzy', fuzzy))


def _run_phase(es, query, size, sort_by_relevance):
    body = {
        'size': size,
        '_source': ['id', 'datetime_modified'],
    }

    if sort_by_relevance:
        body['query'] = _wrap_with_recency_decay(query.to_dict())
    else:
        # Sorting here rather than after the cut-off means the tail we lose is
        # the oldest matches rather than the least relevant ones.
        body['query'] = query.to_dict()
        body['sort'] = [{'datetime_modified': {'order': 'desc'}}]

    search_results = es.search(
        index='notice',
        body=body,
        request_timeout=REQUEST_TIMEOUT,
    )

    hits = search_results.get('hits', {})

    total_hits = hits.get('total', 0)
    if isinstance(total_hits, dict):
        total_hits = total_hits.get('value', 0)
    if total_hits > size:
        logger.warning(
            'Notice search matched %s notices; only the top %s are returned. '
            'Raise NOTICEBOARD_MAX_SEARCH_RESULTS to widen this.',
            total_hits,
            size,
        )

    return [
        (hit['_source']['id'], hit['_source'].get('datetime_modified') or '')
        for hit in hits.get('hits', [])
    ]


def get_ranked_notice_ids(
        keyword, size=MAX_SEARCH_RESULTS, sort_by_relevance=True
):
    """
    Return the ids of notices matching the keyword
    :param keyword: the search keyword
    :param size: the maximum number of ids to return
    :param sort_by_relevance: order by relevance if True, newest first if not
    :return: a list of notice ids, in the requested order
    :raises ElasticsearchUnavailable: if the query could not be served
    """

    from elasticsearch_dsl.connections import connections

    normalized_keyword = keyword.replace('_', ' ')

    try:
        es = connections.get_connection()

        collected = []
        seen = set()

        for label, query in _build_phases(normalized_keyword):
            # Strict and relaxed always merge, since adjacency is too narrow a
            # reading of a multi-word query. Fuzzy is only for misspellings.
            if label == 'fuzzy' and len(collected) >= MIN_SEARCH_RESULTS:
                break

            logger.debug('Elasticsearch notice phase %s: %s', label, query)

            for notice_id, datetime_modified in _run_phase(
                    es, query, size, sort_by_relevance
            ):
                if notice_id not in seen:
                    seen.add(notice_id)
                    collected.append((notice_id, datetime_modified))

        # Each phase is ordered on its own, so the union needs sorting again.
        # Relevance order needs no fix: the stricter phases already lead.
        if not sort_by_relevance:
            collected.sort(key=lambda pair: pair[1], reverse=True)

        return [notice_id for notice_id, _ in collected[:size]]
    except Exception as exc:
        raise ElasticsearchUnavailable(exc) from exc
