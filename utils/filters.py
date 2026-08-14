from django.contrib.postgres.search import SearchVector


def filter_search(data, queryset):
    """
    Check if a search is applied in a filtered result
    """

    if 'keyword' in data:
        search_vector = SearchVector('title', 'content')

        # In search the queryset won't be ordered by datetime
        queryset = queryset.annotate(search=search_vector).filter(
            search=data['keyword'])
    else:
        queryset = queryset.order_by('-datetime_modified')
    # Drafts are unpublished, so exclude them on both branches
    return queryset.filter(is_draft=False)
