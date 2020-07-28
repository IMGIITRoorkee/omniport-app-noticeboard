import logging
import swapper
from django.contrib.postgres.search import SearchVector, SearchQuery
from rest_framework import viewsets
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from formula_one.enums.active_status import ActiveStatus
from notifications.actions import push_notification

from noticeboard.utils.notices import (
    get_drafted_notices,
)
from noticeboard.serializers.notices import *
from noticeboard.models import *
from noticeboard.permissions import IsUploader
from noticeboard.pagination import NoticesPageNumberPagination
from noticeboard.utils.send_email import send_email

logger = logging.getLogger('noticeboard')
Person = swapper.load_model('kernel', 'Person')
FacultyMember = swapper.load_model('kernel', 'FacultyMember')
Student = swapper.load_model('kernel', 'Student')


class NoticeViewSet(viewsets.ModelViewSet):
    """
    This view handles the drafted and the current notices

    This view takes the GET Params:
    1. 'class': Notice class corresponding to drafts
    2. 'keyword': Search keyword
    """

    permission_classes = [IsAuthenticatedOrReadOnly, IsUploader]
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

    def get_recipients(self, is_send_email_role):
        """
        Return the recipients of the notice's change e-mail
        :param is_send_email_role: can be all, student or faculty
        :return: the recipients of the notice's change e-mail
        """

        students = Student.objects_filter(
            active_status=ActiveStatus.IS_ACTIVE,
        ) \
            .values_list('person__id', flat=True)

        faculties = FacultyMember.objects_filter(
            active_status=ActiveStatus.IS_ACTIVE,
        ) \
            .values_list('person__id', flat=True)
        if is_send_email_role == 'student':
            return list(students)

        elif is_send_email_role == 'faculty':
            return list(faculties)

        elif is_send_email_role == 'all':
            return list(students.union(faculties))

        return list()

    def create(self, *args, **kwargs):
        serializer = NoticeSerializer(data=self.request.data)

        if serializer.is_valid():
            notice = serializer.save(uploader=self.request.person)
            logger.info(f'Notice #{notice.id} uploaded successfully by '
                        f'{self.request.person}')
            push_notification(
                template=f'{notice.uploader.full_name} uploaded a notice '
                         f'in {notice.banner.category_node.name}',
                category=notice.banner.category_node
            )
            is_send_email_role = self.request.data.get('is_send_email_role')
            persons = self.get_recipients(is_send_email_role)
            send_email(
                subject_text=notice.title,
                body_text=notice.content,
                persons=persons,
                by=self.request.person.id,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.warning(f'Request to upload notice denied for '
                       f'{self.request.person}')
        return Response(status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        notice = self.get_object()
        serializer = NoticeSerializer(notice, data=self.request.data)

        if serializer.is_valid():
            serializer.save(uploader=self.request.person)
            # Remove this notice from all users' read notices set
            notice.read_notice_set.clear()
            logger.info(f'Notice #{notice.id} updated successfully by '
                        f'{self.request.person}')
            push_notification(
                template=f'{notice.uploader.full_name} updated the notice '
                         f'#{notice.id} in {notice.banner.category_node.name}',
                category=notice.banner.category_node
            )
            is_send_email_role = self.request.data.get('is_send_email_role')
            persons = self.get_recipients(is_send_email_role)
            send_email(
                subject_text=f'{notice.title} [UPDATED]',
                body_text=notice.content,
                persons=persons,
                by=self.request.person.id,
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
