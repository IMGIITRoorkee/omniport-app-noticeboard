from django.contrib.postgres.search import TrigramWordSimilarity
from django.db.models.functions import Greatest

def filter_search(data, queryset):
    """
    Check if a search is applied in a filtered result
    """

    if 'keyword' in data:
        # In search the queryset won't be ordered by datetime
        queryset = queryset.annotate(
            similarity=Greatest(TrigramWordSimilarity(data['keyword'], 'content'),
            TrigramWordSimilarity(data['keyword'], 'title'))
        ).filter(similarity__gte=0.5).filter(is_draft=False)
    else:
        queryset = queryset.order_by('-datetime_modified')
    return queryset
