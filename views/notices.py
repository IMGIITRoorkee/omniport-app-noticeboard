import logging

from django.contrib.postgres.search import SearchVector, SearchQuery
from rest_framework import viewsets
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from noticeboard.utils.notices import (
    get_drafted_notices, has_super_upload_right
)
from noticeboard.utils.get_recipients import get_recipients
from noticeboard.utils.send_email import send_email
from noticeboard.utils.send_push_notification import send_push_notification
from noticeboard.serializers.notices import *
from noticeboard.models import *
from noticeboard.permissions import IsUploader, isPublicInternet
from noticeboard.pagination import NoticesPageNumberPagination
from notifications.actions import push_notification

logger = logging.getLogger('noticeboard')


class NoticeViewSet(viewsets.ModelViewSet):
    """
    This view handles the drafted and the current notices

    This view takes the GET Params:
    1. 'class': Notice class corresponding to drafts
    2. 'keyword': Search keyword
    """

    permission_classes = [IsAuthenticatedOrReadOnly, IsUploader, isPublicInternet]
    pagination_class = NoticesPageNumberPagination
    http_method_names = ['get', 'post', 'put', 'delete']

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

        elif self.action in ['retrieve', 'update', 'destroy']:
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
        else:
            return NoticeSerializer

    def create(self, *args, **kwargs):
        serializer = NoticeSerializer(data=self.request.data)

        if serializer.is_valid():
            person = self.request.person
            notice = serializer.save(uploader=person)
            category = notice.banner.category_node
            logger.info(f'Notice #{notice.id} uploaded successfully by '
                        f'{self.request.person}')
            super_upload_right = has_super_upload_right(person, notice.banner_id)
            is_send_notification = self.request.data.get('is_send_notification')
            send_notification_to_role = self.request.data.get('send_notification_to_role')
            persons = list()
            ignore_subscriptions = False
            mail_subject_text = f'{notice.banner.name}: {notice.title}'
            notification_template = f'{notice.uploader.full_name} uploaded a notice '\
                                    f'in {notice.banner.category_node.name}'
            if super_upload_right and is_send_notification and send_notification_to_role:
                persons = get_recipients(role=send_notification_to_role)
                ignore_subscriptions = True
            else:
                persons = None
                ignore_subscriptions = False
            send_email(
                subject_text=mail_subject_text,
                body_text=notice.content,
                persons=persons,
                has_custom_user_target=ignore_subscriptions,
                send_only_to_subscribed_targets=(not ignore_subscriptions),
                category=category,
                by=person.id,
                notice_id=notice.id,
            )
            send_push_notification(
                    template=notification_template,
                    persons=persons,
                    has_custom_user_target=ignore_subscriptions,
                    send_only_to_subscribed_targets=(not ignore_subscriptions),
                    category=category,
                    notice_id=notice.id,
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.warning(f'Request to upload notice denied for '
                       f'{self.request.person}')
        return Response(status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        notice = self.get_object()
        serializer = NoticeSerializer(notice, data=self.request.data)

        if serializer.is_valid():
            person = self.request.person
            serializer.save(uploader=person)
            category = notice.banner.category_node
            # Remove this notice from all users' read notices set
            notice.read_notice_set.clear()
            logger.info(f'Notice #{notice.id} updated successfully by '
                        f'{self.request.person}')
            super_upload_right = has_super_upload_right(person, notice.banner_id)
            is_send_notification = self.request.data.get('is_send_notification')
            send_notification_to_role = self.request.data.get('send_notification_to_role')
            persons = list()
            ignore_subscriptions = False
            mail_subject_text = f'[Updated] {notice.banner.name}: {notice.title}'
            notification_template = f'{notice.uploader.full_name} updated the notice '\
                                    f'#{notice.id} in {notice.banner.category_node.name}'
            if super_upload_right and is_send_notification and send_notification_to_role:
                persons = get_recipients(role=send_notification_to_role)
                ignore_subscriptions = True
            else:
                persons = None
                ignore_subscriptions = False
            send_email(
                subject_text=mail_subject_text,
                body_text=notice.content,
                persons=persons,
                has_custom_user_target=ignore_subscriptions,
                send_only_to_subscribed_targets=(not ignore_subscriptions),
                category=category,
                by=person.id,
                notice_id=notice.id,
            )
            send_push_notification(
                    template=notification_template,
                    persons=persons,
                    has_custom_user_target=ignore_subscriptions,
                    send_only_to_subscribed_targets=(not ignore_subscriptions),
                    category=category,
                    notice_id=notice.id,
            )

            return Response(serializer.data, status=status.HTTP_200_OK)
        logger.warning(f'Request to update notice #{notice.id} denied for '
                       f'{self.request.person}')
        return Response(status=status.HTTP_400_BAD_REQUEST)


class ExpiredNoticeViewSet(viewsets.ModelViewSet):
    """
    This view handles the expired notices

    This view takes the GET Params:
    1. 'keyword': Search keyword
    """

    lookup_field = 'notice_id'
    permission_classes = [IsAuthenticatedOrReadOnly, IsUploader]
    http_method_names = ['get', 'delete']

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
