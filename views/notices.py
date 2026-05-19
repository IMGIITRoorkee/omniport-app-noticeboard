import logging
import os

from django.contrib.postgres.search import SearchVector
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
from categories.models import Category
from noticeboard.permissions import IsUploader, isPublicInternet
from noticeboard.pagination import NoticesPageNumberPagination

logger = logging.getLogger('noticeboard')

MAX_SEARCH_RESULTS = int(os.getenv('NOTICEBOARD_MAX_SEARCH_RESULTS', '1000'))
ELASTICSEARCH_REQUEST_TIMEOUT = 3
ELASTICSEARCH_RECENCY_DECAY_ORIGIN = os.getenv('NOTICEBOARD_ES_RECENCY_ORIGIN', 'now')
ELASTICSEARCH_RECENCY_DECAY_SCALE = os.getenv('NOTICEBOARD_ES_RECENCY_SCALE', '60d')
ELASTICSEARCH_RECENCY_DECAY_OFFSET = os.getenv('NOTICEBOARD_ES_RECENCY_OFFSET', '3d')
ELASTICSEARCH_RECENCY_DECAY_FACTOR = float(
    os.getenv('NOTICEBOARD_ES_RECENCY_DECAY', '0.20')
)

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
        sort_mode = self.request.query_params.get('sort', 'date')
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

            elif notice_class == 'institute_notices':
                category_node = Category.objects.get(slug='noticeboard__authorities__pic')
                banner_object = Banner.objects.get(category_node=category_node)
                queryset = Notice.objects.filter(
                    is_draft=False
                ).exclude(banner=banner_object).order_by('-datetime_modified')

            elif keyword:
                from elasticsearch_dsl import Q as ES_Q
                from elasticsearch_dsl.connections import connections
                from elastic_transport import (
                    ApiError as ElasticTransportApiError,
                    ConnectionError as ElasticTransportConnectionError,
                    ConnectionTimeout,
                )
                from django.db.models import Case, When

                normalized_sort_mode = (sort_mode or 'date').strip().lower()
                sort_by_relevance = normalized_sort_mode == 'relevance'

                # Reuse the connection configured by ELASTICSEARCH_DSL in
                # omniport.settings.third_party.elastic. This honors host,
                # auth, TLS, and timeout settings driven by the environment
                # (see noticeboard/elasticsearch.env in omniport-docker), and
                # avoids spinning up a fresh connection pool per request.
                es = connections.get_connection()

                normalized_keyword = keyword.replace('_', ' ')
                keyword_lower = normalized_keyword.lower()

                draft_filter = ES_Q('term', is_draft=False)

                def _wrap_with_recency_decay(query_dict):
                    return {
                        'function_score': {
                            'query': query_dict,
                            'functions': [
                                {
                                    'gauss': {
                                        'datetime_modified': {
                                            'origin': ELASTICSEARCH_RECENCY_DECAY_ORIGIN,
                                            'scale': ELASTICSEARCH_RECENCY_DECAY_SCALE,
                                            'decay': ELASTICSEARCH_RECENCY_DECAY_FACTOR,
                                            'offset': ELASTICSEARCH_RECENCY_DECAY_OFFSET,
                                        }
                                    }
                                }
                            ],
                            'score_mode': 'multiply',
                            'boost_mode': 'multiply',
                        }
                    }

                try:
                    exact_should = [
                        ES_Q(
                            'multi_match',
                            query=normalized_keyword,
                            type='phrase',
                            fields=['title^5', 'content'],
                        ),
                        ES_Q(
                            'wildcard',
                            title={
                                'value': f'*{keyword_lower}*',
                                'boost': 2,
                            },
                        ),
                        ES_Q(
                            'wildcard',
                            content={
                                'value': f'*{keyword_lower}*',
                                'boost': 0.5,
                            },
                        ),
                    ]

                    exact_query = ES_Q(
                        'bool',
                        must=[draft_filter],
                        should=exact_should,
                        minimum_should_match=1,
                    )

                    logger.debug("Elasticsearch notice phase 1 (strict) query: %s", exact_query.to_dict())
                    search_results = es.search(
                        index='notice',
                        body={
                            'query': _wrap_with_recency_decay(exact_query.to_dict()),
                            'size': MAX_SEARCH_RESULTS,
                        },
                        request_timeout=ELASTICSEARCH_REQUEST_TIMEOUT,
                    )

                    total_hits = search_results.get('hits', {}).get('total', 0)
                    if isinstance(total_hits, dict):
                        total_hits = total_hits.get('value', 0)
                    if total_hits > MAX_SEARCH_RESULTS:
                        logger.warning(
                            'Notice search returned %s hits; truncating to first %s. '
                            'Increase NOTICEBOARD_MAX_SEARCH_RESULTS or paginate at ES layer.',
                            total_hits,
                            MAX_SEARCH_RESULTS,
                        )

                    notice_id_list = [
                        hit['_source']['id']
                        for hit in search_results.get('hits', {}).get('hits', [])
                    ]

                    if not notice_id_list:
                        relaxed_query = ES_Q(
                            'multi_match',
                            query=normalized_keyword,
                            fields=['title^5', 'content'],
                            type='best_fields',
                            minimum_should_match='2<75%',
                        )

                        base_query = ES_Q(
                            'bool',
                            must=[draft_filter, relaxed_query],
                        )

                        logger.debug("Elasticsearch notice phase 2 (relaxed) query: %s", base_query.to_dict())
                        search_results = es.search(
                            index='notice',
                            body={
                                'query': _wrap_with_recency_decay(base_query.to_dict()),
                                'size': MAX_SEARCH_RESULTS,
                            },
                            request_timeout=ELASTICSEARCH_REQUEST_TIMEOUT,
                        )

                        total_hits = search_results.get('hits', {}).get('total', 0)
                        if isinstance(total_hits, dict):
                            total_hits = total_hits.get('value', 0)
                        if total_hits > MAX_SEARCH_RESULTS:
                            logger.warning(
                                'Notice search returned %s hits; truncating to first %s. '
                                'Increase NOTICEBOARD_MAX_SEARCH_RESULTS or paginate at ES layer.',
                                total_hits,
                                MAX_SEARCH_RESULTS,
                            )

                        notice_id_list = [
                            hit['_source']['id']
                            for hit in search_results.get('hits', {}).get('hits', [])
                        ]

                    if not notice_id_list:
                        fuzzy_query = ES_Q(
                            'multi_match',
                            query=normalized_keyword,
                            fields=['title^5', 'content'],
                            fuzziness='AUTO',
                            prefix_length=1,
                            max_expansions=50,
                        )

                        base_query = ES_Q(
                            'bool',
                            must=[draft_filter, fuzzy_query],
                        )

                        logger.debug("Elasticsearch notice phase 3 (fuzzy) query: %s", base_query.to_dict())
                        search_results = es.search(
                            index='notice',
                            body={
                                'query': _wrap_with_recency_decay(base_query.to_dict()),
                                'size': MAX_SEARCH_RESULTS,
                            },
                            request_timeout=ELASTICSEARCH_REQUEST_TIMEOUT,
                        )

                        total_hits = search_results.get('hits', {}).get('total', 0)
                        if isinstance(total_hits, dict):
                            total_hits = total_hits.get('value', 0)
                        if total_hits > MAX_SEARCH_RESULTS:
                            logger.warning(
                                'Notice search returned %s hits; truncating to first %s. '
                                'Increase NOTICEBOARD_MAX_SEARCH_RESULTS or paginate at ES layer.',
                                total_hits,
                                MAX_SEARCH_RESULTS,
                            )

                        notice_id_list = [
                            hit['_source']['id']
                            for hit in search_results.get('hits', {}).get('hits', [])
                        ]

                    if notice_id_list:
                        queryset = Notice.objects.filter(id__in=notice_id_list)

                        if sort_by_relevance:
                            order_cases = [
                                When(id=pk, then=pos)
                                for pos, pk in enumerate(notice_id_list)
                            ]
                            order_by_case = Case(*order_cases)
                            queryset = queryset.order_by(order_by_case)
                        else:
                            queryset = queryset.order_by('-datetime_modified')
                    else:
                        queryset = Notice.objects.none()

                except (
                    ElasticTransportApiError,
                    ElasticTransportConnectionError,
                    ConnectionTimeout,
                ) as exc:
                    logger.warning(
                        'Elasticsearch unavailable for notice search or index missing, falling back to '
                        'PostgreSQL full-text search: %s',
                        exc,
                        exc_info=True,
                    )
                    search_vector = SearchVector('title', 'content')
                    queryset = Notice.objects.annotate(
                        search=search_vector,
                    ).filter(
                        search=normalized_keyword,
                    ).filter(
                        is_draft=False,
                    ).order_by('-datetime_modified')
                except Exception as exc:
                    logger.error("Elasticsearch notice search failed: %s", exc, exc_info=True)
                    queryset = Notice.objects.none()

            else:
                queryset = Notice.objects.filter(
                    is_draft=False
                ).order_by('-datetime_modified')

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

        ip_address_rings = self.request.ip_address_rings
        if ('internet' in ip_address_rings) and (len(ip_address_rings) <= 1):
            queryset = queryset.filter(
                is_public=True
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
            notice = serializer.save(uploader=person)
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

    def destroy(self, request, *args, **kwargs):
        notice = self.get_object()

        self.perform_destroy(notice)

        return Response(status=status.HTTP_204_NO_CONTENT)


class ExpiredNoticeViewSet(viewsets.ModelViewSet):
    """
    This view handles the expired notices

    This view takes the GET Params:
    1. 'keyword': Search keyword
    """

    lookup_field = 'notice_id'
    permission_classes = [IsAuthenticatedOrReadOnly, IsUploader, isPublicInternet]
    http_method_names = ['get', 'delete']

    def get_queryset(self):
        keyword = self.request.query_params.get('keyword', None)

        if keyword:
            search_vector = SearchVector('title', 'content')
            queryset = ExpiredNotice.objects.annotate(
                search=search_vector
            ).filter(search=keyword).filter(is_draft=False)
        else:
            queryset = ExpiredNotice.objects.filter(
                is_draft=False
            ).order_by('datetime_modified')

        ip_address_rings = self.request.ip_address_rings
        if ('internet' in ip_address_rings) and (len(ip_address_rings) <= 1):
            queryset = queryset.filter(
                is_public=True
            )

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
