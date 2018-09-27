from rest_framework.views import APIView
from rest_framework import viewsets
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404
from django.contrib.postgres.search import SearchVector

from noticeboard.serializers import (
    BannerSerializer,
    MainCategorySerializer,
    NoticeListSerializer,
)
from noticeboard.models import (
    Notice,
    MainCategory,
    Banner,
    User
)


class FilterListViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This view fetches all the main categories and their banners
    """

    serializer_class = MainCategorySerializer
    queryset = MainCategory.objects.all()


def filter_search(data, queryset):
    """
    Check if a search is applied in a filtered result
    """

    if 'keyword' in data:
        search_vector = SearchVector('title', 'content')
        queryset = queryset.annotate(search=search_vector).filter(
            search=data['keyword']).filter(is_draft=False)
    return queryset


class FilterViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This view filters the notices according to a banner
    """

    serializer_class = NoticeListSerializer

    def get_object(self, pk):
        try:
            return Banner.objects.get(pk=pk)
        except Banner.DoesNotExist:
            raise Http404

    def get_queryset(self):
        data = self.request.query_params

        banner_id = data.get('banner', None)
        banner_object = self.get_object(banner_id)

        queryset = Notice.objects.filter(banner=banner_object)
        queryset = filter_search(data, queryset)
        return queryset


class DateFilterViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This view filters the notices according to the start and
    end date
    """

    serializer_class = NoticeListSerializer

    def get_queryset(self):
        data = self.request.query_params
        start_date, end_date = data.get('start', None), data.get('end', None)

        queryset = Notice.objects.filter(datetime_created__range=(
            start_date,
            end_date
        ))
        queryset = filter_search(data, queryset)
        return queryset


class StarFilterViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This view filters the notices according to the start and
    end date
    """

    serializer_class = NoticeListSerializer

    def get_queryset(self):
        person = self.request.person

        if person:
            notice_user, created = User.objects.get_or_create(person=person)
            queryset = notice_user.starred_notices.all()
        else:
            queryset = Notice.objects.none()
        return queryset
