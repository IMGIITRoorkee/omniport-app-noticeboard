import datetime

from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from django.http import Http404
from django.contrib.postgres.search import SearchVector

from categories.models import Category
from noticeboard.serializers import (
    BannerSerializer,
    MainCategorySerializer,
    NoticeListSerializer,
)
from noticeboard.utils.filters import filter_search
from noticeboard.models import (
    Notice,
    Banner,
    NoticeUser
)


class FilterListViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This view fetches the category tree for noticeboard and the 
    corresponding child banners
    """

    serializer_class = MainCategorySerializer
    queryset = Category.objects.get(slug='noticeboard').get_children()
    pagination_class = None
    permission_classes = [IsAuthenticated, ]


class FilterViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This view filters the notices according to a banner

    This view takes the following GET Parameters:
    1. 'banner': Filter corresponding to a banner id
    2. 'keyword': Search keyword
    """

    serializer_class = NoticeListSerializer
    permission_classes = [IsAuthenticated, ]

    def get_banner_object(self, pk):
        try:
            return Banner.objects.get(pk=pk)
        except Banner.DoesNotExist:
            raise Http404

    def get_queryset(self):
        data = self.request.query_params

        banner_id = data.get('banner', None)
        banner_object = self.get_banner_object(banner_id)

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
    permission_classes = [IsAuthenticated, ]

    def get_banner_object(self, pk):
        try:
            return Banner.objects.get(pk=pk)
        except Banner.DoesNotExist:
            raise Http404

    def get_queryset(self):
        data = self.request.query_params

        # Filter corresponding to a date
        start_date, end_date = data.get('start', None), data.get('end', None)

        start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
        end_date = datetime.datetime.combine(end_date, datetime.time.max)

        queryset = Notice.objects.filter(datetime_created__range=(
            start_date,
            end_date
        ))

        # Filter corresponding to a banner
        banner_id = data.get('banner', None)
        if banner_id:
            banner_object = self.get_banner_object(banner_id)
            queryset = queryset.filter(banner=banner_object)

        # Search
        queryset = filter_search(data, queryset)
        return queryset


class StarFilterViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This view returns all the starred notices of a notice user
    """

    serializer_class = NoticeListSerializer
    permission_classes = [IsAuthenticated, ]

    def get_queryset(self):
        person = self.request.person

        notice_user, created = NoticeUser.objects.get_or_create(person=person)
        queryset = notice_user.starred_notices.all().order_by('-datetime_modified')
        return queryset
