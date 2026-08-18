import logging

from django.contrib.postgres.search import (
    SearchQuery, SearchRank, SearchVector
)
from django.db.models import Case, When

from noticeboard.utils.search import (
    ElasticsearchUnavailable,
    MAX_FILTERED_SEARCH_RESULTS,
    get_ranked_notice_ids,
)

logger = logging.getLogger('noticeboard')


def postgres_search(queryset, keyword, sort_mode):
    """
    Search a queryset using PostgreSQL full-text search
    :param queryset: the queryset to search within
    :param keyword: the search keyword
    :param sort_mode: either 'relevance' or 'date'
    :return: the matching queryset, ordered
    """

    search_vector = (
        SearchVector('title', weight='A')
        + SearchVector('content', weight='B')
    )

    queryset = queryset.annotate(
        search=search_vector,
    ).filter(
        search=keyword,
    ).filter(
        is_draft=False,
    )

    if sort_mode == 'relevance':
        return queryset.annotate(
            rank=SearchRank(search_vector, SearchQuery(keyword)),
        ).order_by('-rank', '-datetime_modified')
    return queryset.order_by('-datetime_modified')


def filter_search(data, queryset):
    """
    Check if a search is applied in a filtered result
    """

    keyword = data.get('keyword')
    if not keyword:
        return queryset.order_by('-datetime_modified')

    sort_mode = (data.get('sort') or 'date').strip().lower()

    try:
        notice_id_list = get_ranked_notice_ids(
            keyword,
            size=MAX_FILTERED_SEARCH_RESULTS,
            sort_by_relevance=sort_mode == 'relevance',
        )
    except ElasticsearchUnavailable as exc:
        logger.warning(
            'Elasticsearch unavailable for filtered notice search, falling '
            'back to PostgreSQL full-text search: %s',
            exc,
            exc_info=True,
        )
        return postgres_search(queryset, keyword, sort_mode)

    if not notice_id_list:
        return queryset.none()

    queryset = queryset.filter(id__in=notice_id_list, is_draft=False)

    if sort_mode == 'relevance':
        return queryset.order_by(Case(*[
            When(id=pk, then=pos)
            for pos, pk in enumerate(notice_id_list)
        ]))
    return queryset.order_by('-datetime_modified')
