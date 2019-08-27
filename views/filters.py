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
    try:
        queryset = Category.objects.get(slug='noticeboard').get_children()
    except Exception:
        queryset = Category.objects.none()
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

    def get_banner_object_from_id(self, pk):
        try:
            return Banner.objects.get(pk=pk)
        except Banner.DoesNotExist:
            raise Http404

    def get_category_object_from_slug(self, main_category_slug):
        try:
            return Category.objects.get(slug=main_category_slug)
        except Category.DoesNotExist:
            raise Http404

    def get_queryset(self):
        data = self.request.query_params

        banner_id = data.get('banner', None)
        main_category_slug = data.get('main_category', None)

        # Filter corresponding to a banner or main category of banners
        if banner_id:
            banner_object = self.get_banner_object_from_id(banner_id)
            queryset = Notice.objects.filter(banner=banner_object)

        elif main_category_slug:
            category_nodes = self.get_category_object_from_slug(main_category_slug).get_children()

            banners = Banner.objects.filter(category_node__in=category_nodes)
            queryset = Notice.objects.filter(banner__in=banners)
        else:
            raise Http404

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

    def get_category_object_from_slug(self, main_category_slug):
        try:
            return Category.objects.get(slug=main_category_slug)
        except Category.DoesNotExist:
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

        # Filter corresponding to a banner or main category of banners
        banner_id = data.get('banner', None)
        main_category_slug = data.get('main_category', None)

        if banner_id:
            banner_object = self.get_banner_object(banner_id)
            queryset = queryset.filter(banner=banner_object)

        elif main_category_slug:
            category_nodes = self.get_category_object_from_slug(main_category_slug).get_children()

            banners = Banner.objects.filter(category_node__in=category_nodes)
            queryset = queryset.filter(banner__in=banners)

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
        try:
            queryset = notice_user.starred_notices.all().order_by('-datetime_modified')
        except Exception:
            queryset = Notice.objects.none()
        return queryset
