from rest_framework import viewsets
from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import SearchVector

from noticeboard.serializers import (
    NoticeSerializer,
    NoticeDetailSerializer,
    NoticeUpdateSerializer,
    NoticeListSerializer,
    ExpiredNoticeListSerializer,
    ExpiredNoticeDetailSerializer,
)
from noticeboard.models import *


def user_allowed_banners(roles, person):
    """
    Given a user, return all the allowed banners
    """

    banner_ids = []
    if roles:
        for role in roles.values():
            role_object = role['instance']
            role_content_type = ContentType.objects.get_for_model(role_object)

            banner_ids += Permissions.objects.filter(
                persona_object_id=role_object.id,
                persona_content_type=role_content_type
            ).values_list('banner_id', flat=True)

    return banner_ids


def get_drafted_notices(request):
    person, roles = request.person, request.roles
    allowed_banner_ids = user_allowed_banners(roles, person)

    queryset = Notice.objects.filter(
        is_draft=True,
        banner_id__in=allowed_banner_ids)
    return queryset


class NoticeViewSet(viewsets.ModelViewSet):
    """
    This view handles the drafted and the current notices
    """

    def get_queryset(self):

        notice_class = self.request.query_params.get('class', None)

        keyword = self.request.query_params.get('keyword', None)
        search_vector = SearchVector('title', 'content')

        if self.action == 'create':
            queryset = Notice.objects.all()

        elif self.action == 'list':
            """
            List of notices will not contain the drafts
            """

            if notice_class == 'draft':
                queryset = get_drafted_notices(self.request)
            elif keyword:
                queryset = Notice.objects.annotate(
                    search=search_vector
                ).filter(search=keyword).filter(is_draft=False)
            else:
                queryset = Notice.objects.filter(is_draft=False)

        elif self.action in ['retrieve', 'update']:
            """
            The users would be able to view the draft if they are authenticated
            """

            drafted_notices = get_drafted_notices(self.request)
            all_notices = Notice.objects.filter(is_draft=False)
            queryset = (all_notices | drafted_notices).distinct()

        return queryset

    def get_serializer_class(self):
        """
        This function decides the serializer class according to the type of
        request
        :return: the serializer class
        """
        if self.action == 'list':
            return NoticeListSerializer
        elif self.action == 'retrieve':
            return NoticeDetailSerializer
        elif self.action == 'create':
            return NoticeSerializer
        elif self.action == 'update':
            return NoticeUpdateSerializer

    @action(methods=['post'], detail=True)
    def create(self, request, format=None):

        person, roles = request.person, request.roles

        data = request.data
        serializer = NoticeSerializer(data=data)

        if serializer.is_valid():
            banner_id = data['banner']['id']

            allowed_banner_ids = user_allowed_banners(roles, person)
            if banner_id in allowed_banner_ids:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)

            return Response(serializer.data, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.data, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['put'], detail=True)
    def update(self, request, pk, format=None):

        notice = self.get_object()
        person, roles = request.person, request.roles

        serializer = NoticeUpdateSerializer(notice, data=request.data)

        if serializer.is_valid():
            banner_id = notice.banner.id

            allowed_banner_ids = user_allowed_banners(roles, person)
            if banner_id in allowed_banner_ids:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)

            return Response(serializer.data, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.data, status=status.HTTP_400_BAD_REQUEST)


class ExpiredNoticeViewSet(viewsets.ModelViewSet):
    """
    This view handles the expired notices
    """

    lookup_field = 'notice_id'

    def get_queryset(self):
        keyword = self.request.query_params.get('keyword', None)
        search_vector = SearchVector('title', 'content')

        if keyword:
            queryset = ExpiredNotice.objects.annotate(
                search=search_vector
            ).filter(search=keyword).filter(is_draft=False)
        else:
            queryset = ExpiredNotice.objects.filter(is_draft=False)
        return queryset

    def get_serializer_class(self):
        """
        This function decides the serializer class according to the type of
        request
        :return: the serializer class
        """
        if self.action == 'list':
            return ExpiredNoticeListSerializer
        elif self.action == 'retrieve':
            return ExpiredNoticeDetailSerializer
