from django.contrib.postgres.search import SearchVector, SearchQuery

from rest_framework import viewsets
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from noticeboard.utils.notices import (
    user_allowed_banners,
    has_super_upload_right,
    get_drafted_notices,
)
from noticeboard.serializers.notices import *
from noticeboard.models import *


class NoticeViewSet(viewsets.ModelViewSet):
    """
    This view handles the drafted and the current notices

    This view takes the GET Params:
    1. 'class': Notice class corresponding to drafts
    2. 'keyword': Search keyword
    """

    permission_classes = [IsAuthenticated, ]

    def get_queryset(self):

        notice_class = self.request.query_params.get('class', None)
        keyword = self.request.query_params.get('keyword', None)
        important_only = self.request.query_params.get('important', False)
        unread_only = self.request.query_params.get('unread', False)

        queryset = Notice.objects.none()

        if self.action == 'create':
            queryset = Notice.objects.all()

        elif self.action == 'list':
            """
            List of notices will not contain the drafts
            """

            if notice_class == 'draft':
                queryset = get_drafted_notices(self.request)

            elif keyword:
                search_vector = SearchVector('title', 'content')
                queryset = Notice.objects.annotate(
                    search=search_vector
                ).filter(
                    search=SearchQuery(keyword)
                ).filter(
                    is_draft=False
                ).order_by(
                    '-datetime_modified'
                )

            else:
                queryset = Notice.objects.filter(is_draft=False).order_by(
                    '-datetime_modified')

        elif self.action in ['retrieve', 'update']:
            """
            The users would be able to view the draft if they are authenticated
            """

            drafted_notices = get_drafted_notices(self.request)
            all_notices = Notice.objects.filter(is_draft=False)
            queryset = (all_notices | drafted_notices).distinct()

        if important_only:
            """
            Send only important notices
            """
            queryset = queryset.filter(
                is_important=True
            )
        if unread_only:
            """
            Send only unread notices
            """
            queryset = queryset.exclude(
                read_notice_set__person=self.request.person
            )

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

    def create(self, request, format=None):
        roles = request.roles

        data = request.data
        serializer = NoticeSerializer(data=data)

        if serializer.is_valid():
            banner_id = data['banner']['id']

            # Check if the user is authenticated to post under a banner
            allowed_banner_ids = user_allowed_banners(roles)
            if banner_id in allowed_banner_ids:
                if data.get('is_important', False):
                    serializer.is_important = has_super_upload_right(
                        roles,
                        banner_id
                    )
                print(request.person)
                serializer.save(uploader=request.person)
                return Response(serializer.data, status=status.HTTP_201_CREATED)

            return Response(status=status.HTTP_401_UNAUTHORIZED)
        return Response(status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk, format=None):
        notice = self.get_object()
        roles = request.roles

        data = request.data
        serializer = NoticeUpdateSerializer(notice, data=data)

        if serializer.is_valid():
            banner_id = data['banner']['id']

            # Check if the user is authenticated to put under a banner
            allowed_banner_ids = user_allowed_banners(roles)
            if banner_id in allowed_banner_ids:
                if data.get('is_important', False):
                    serializer.is_important = has_super_upload_right(
                        roles,
                        banner_id
                    )

                serializer.save(uploader=request.person)
                return Response(serializer.data, status=status.HTTP_200_OK)

            return Response(status=status.HTTP_401_UNAUTHORIZED)
        return Response(status=status.HTTP_400_BAD_REQUEST)


class ExpiredNoticeViewSet(viewsets.ModelViewSet):
    """
    This view handles the expired notices

    This view takes the GET Params:
    1. 'keyword': Search keyword
    """

    lookup_field = 'notice_id'
    permission_classes = [IsAuthenticated, ]

    def get_queryset(self):
        keyword = self.request.query_params.get('keyword', None)

        if keyword:
            search_vector = SearchVector('title', 'content')
            queryset = ExpiredNotice.objects.annotate(
                search=search_vector
            ).filter(search=keyword).filter(is_draft=False)
        else:
            queryset = ExpiredNotice.objects.filter(is_draft=False).order_by(
                'datetime_modified')
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
