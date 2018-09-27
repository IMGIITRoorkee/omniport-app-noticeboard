from rest_framework.response import Response
from rest_framework import viewsets
from django.contrib.postgres.search import SearchVector

from noticeboard.serializers import (
    NoticeListSerializer,
    ExpiredNoticeListSerializer,
)
from noticeboard.models import (
    Notice,
    ExpiredNotice
)


class SearchViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This view searches notice
    """

    def get_serializer_class(self):
        data = self.request.query_params
        notice_class = data.get('class', None)

        if notice_class == 'expired':
            return ExpiredNoticeListSerializer
        return NoticeListSerializer

    def get_queryset(self):
        person = self.request.person
        data = self.request.query_params

        keyword = data.get('keyword', None)
        notice_class = data.get('class', None)

        search_vector = SearchVector('title', 'content')

        if notice_class == 'expired':
            queryset = ExpiredNotice.objects.annotate(
                search=search_vector
            ).filter(search=keyword).filter(is_draft=False)
        else:
            queryset = Notice.objects.annotate(
                search=search_vector
            ).filter(search=keyword).filter(is_draft=False)

        return queryset
