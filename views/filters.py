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

    This view takes the following GET Parameters:
    1. 'banner': Filter corresponding to a banner id
    2. 'keyword': Search keyword
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

    This view takes the following GET Parameters:
    1. 'start': Start date
    2. 'end': End date
    3. 'banner': Filter corresponding to a banner id
    4. 'keyword': Search keyword
    """

    serializer_class = NoticeListSerializer

    def get_object(self, pk):
        try:
            return Banner.objects.get(pk=pk)
        except Banner.DoesNotExist:
            raise Http404

    def get_queryset(self):
        data = self.request.query_params

        # Filter corresponding to a date
        start_date, end_date = data.get('start', None), data.get('end', None)
        queryset = Notice.objects.filter(datetime_created__range=(
            start_date,
            end_date
        ))

        # Filter corresponding to a banner
        banner_id = data.get('banner', None)
        if banner_id:
            banner_object = self.get_object(banner_id)
            queryset = queryset.filter(banner=banner_object)

        # Search
        queryset = filter_search(data, queryset)
        return queryset


class StarFilterViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This view returns all the starred notices of a notice user
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
