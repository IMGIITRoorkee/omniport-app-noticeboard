import logging
import os

logger = logging.getLogger('noticeboard')

# What each of these does, what it costs and why the default is what it is:
# docs/architecture/search.md. All are overridable per deployment.

# Result caps, and the hit count below which a phase escalates to the next
MAX_SEARCH_RESULTS = int(os.getenv('NOTICEBOARD_MAX_SEARCH_RESULTS', '2000'))
MAX_FILTERED_SEARCH_RESULTS = int(
    os.getenv('NOTICEBOARD_MAX_FILTERED_SEARCH_RESULTS', '10000')
)
MIN_SEARCH_RESULTS = int(os.getenv('NOTICEBOARD_MIN_SEARCH_RESULTS', '5'))
REQUEST_TIMEOUT = 3

# Recency decay, applied as a multiplier on the BM25 score
RECENCY_DECAY_ORIGIN = os.getenv('NOTICEBOARD_ES_RECENCY_ORIGIN', 'now')
RECENCY_DECAY_SCALE = os.getenv('NOTICEBOARD_ES_RECENCY_SCALE', '365d')
RECENCY_DECAY_OFFSET = os.getenv('NOTICEBOARD_ES_RECENCY_OFFSET', '30d')
RECENCY_DECAY_FACTOR = float(os.getenv('NOTICEBOARD_ES_RECENCY_DECAY', '0.5'))
RECENCY_DECAY_FLOOR = float(os.getenv('NOTICEBOARD_ES_RECENCY_FLOOR', '0.5'))

# Strict clause names, which Elasticsearch reports per hit in matched_queries
PHRASE_CLAUSE = 'phrase'
TITLE_PREFIX_CLAUSE = 'title_prefix'
TITLE_WILDCARD_CLAUSE = 'title_wildcard'

# Relevance tiers, lowest first, read from matched_queries rather than score
TIER_TITLE_EXACT = 1
TIER_TITLE_PARTIAL = 2
TIER_CONTENT_EXACT = 3
TIER_TITLE_SUBSTRING = 4
TIER_RELAXED = 5
TIER_FUZZY = 6

# Group equally relevant notices and date-order each group; 0 for score order
TIERED_RELEVANCE = os.getenv('NOTICEBOARD_TIERED_RELEVANCE', '1') != '0'

# Past this tier the score still discriminates, so date order would cost
# precision
LAST_DATE_ORDERED_TIER = TIER_TITLE_SUBSTRING


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
                _name=PHRASE_CLAUSE,
            ),
            # Scores a partly typed word against the title. The wildcard below
            # matches one too, but is constant-scored and loses to any body hit.
            ES_Q(
                'match_phrase_prefix',
                title={
                    'query': keyword,
                    'max_expansions': 50,
                    'boost': 5,
                    '_name': TITLE_PREFIX_CLAUSE,
                },
            ),
            ES_Q(
                'wildcard',
                title={
                    'value': f'*{keyword.lower()}*',
                    'boost': 2,
                    '_name': TITLE_WILDCARD_CLAUSE,
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


def _tier_for(phase_label, matched_queries):
    """
    Read a relevance tier off the clauses a hit matched
    :param phase_label: the phase that returned the hit
    :param matched_queries: the clause names Elasticsearch reported for it
    :return: the tier, lower being more relevant
    """

    if phase_label == 'relaxed':
        return TIER_RELAXED
    if phase_label == 'fuzzy':
        return TIER_FUZZY

    matched = set(matched_queries or ())
    in_title = TITLE_PREFIX_CLAUSE in matched
    is_phrase = PHRASE_CLAUSE in matched

    if in_title and is_phrase:
        return TIER_TITLE_EXACT
    if in_title:
        return TIER_TITLE_PARTIAL
    if is_phrase:
        return TIER_CONTENT_EXACT

    # Either the wildcard alone matched, a fragment inside a word, or the names
    # went missing. Either way this is the weakest reading of a strict hit.
    return TIER_TITLE_SUBSTRING


def _run_phase(es, query, size, sort_by_relevance, phase_label='strict'):
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
        (
            hit['_source']['id'],
            hit['_source'].get('datetime_modified') or '',
            _tier_for(phase_label, hit.get('matched_queries')),
        )
        for hit in hits.get('hits', [])
    ]


def get_ranked_notices(
        keyword, size=MAX_SEARCH_RESULTS, sort_by_relevance=True
):
    """
    Return the notices matching the keyword, each with the tier it matched at
    :param keyword: the search keyword
    :param size: the maximum number of notices to return
    :param sort_by_relevance: order by tier then date if True, date alone if not
    :return: a list of (notice id, tier) pairs, in the requested order
    :raises ElasticsearchUnavailable: if the query could not be served
    """

    from elasticsearch_dsl.connections import connections

    normalized_keyword = keyword.replace('_', ' ')

    try:
        es = connections.get_connection()

        collected = []
        tiers = {}

        for label, query in _build_phases(normalized_keyword):
            # Strict and relaxed always merge, since adjacency is too narrow a
            # reading of a multi-word query. Fuzzy is only for misspellings.
            if label == 'fuzzy' and len(collected) >= MIN_SEARCH_RESULTS:
                break

            logger.debug('Elasticsearch notice phase %s: %s', label, query)

            for notice_id, datetime_modified, tier in _run_phase(
                    es, query, size, sort_by_relevance, label
            ):
                if notice_id in tiers:
                    # The phases run strongest first, so whatever tier is
                    # already recorded is the strongest reading of this notice
                    # and a later phase must not overwrite it.
                    continue

                tiers[notice_id] = tier
                collected.append((notice_id, datetime_modified))

        # Each phase is ordered on its own, so the union needs sorting again.
        if not sort_by_relevance:
            collected.sort(key=lambda pair: pair[1], reverse=True)
        elif TIERED_RELEVANCE:
            # Two stable passes. The first puts everything in date order; the
            # second groups by tier, and hands the weak tiers a tie-breaker of
            # the rank Elasticsearch gave them, which restores their score
            # order. The strong tiers tie on 0 and keep the date order.
            scored_rank = {
                notice_id: rank
                for rank, (notice_id, _) in enumerate(collected)
            }
            collected.sort(key=lambda pair: pair[1], reverse=True)
            collected.sort(key=lambda pair: (
                tiers[pair[0]],
                0 if tiers[pair[0]] <= LAST_DATE_ORDERED_TIER
                else scored_rank[pair[0]],
            ))

        return [
            (notice_id, tiers[notice_id])
            for notice_id, _ in collected[:size]
        ]
    except Exception as exc:
        raise ElasticsearchUnavailable(exc) from exc


def get_ranked_notice_ids(
        keyword, size=MAX_SEARCH_RESULTS, sort_by_relevance=True
):
    """
    Return the ids of notices matching the keyword
    :param keyword: the search keyword
    :param size: the maximum number of ids to return
    :param sort_by_relevance: order by tier then date if True, date alone if not
    :return: a list of notice ids, in the requested order
    :raises ElasticsearchUnavailable: if the query could not be served
    """

    return [
        notice_id for notice_id, _ in get_ranked_notices(
            keyword, size, sort_by_relevance
        )
    ]
