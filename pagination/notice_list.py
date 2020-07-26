from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class NoticesPageNumberPagination(PageNumberPagination):
    """
    Custom pagination class to include count of unread important notices.
    """

    def paginate_queryset(self, queryset, request, view=None):
        """
        Override PageNumberPagination.paginate_queryset to include count of
        unread important notices.
        """
        self.important_unread_count = queryset.filter(
            is_important=True,
        ).exclude(
                read_notice_set__person=request.person
        ).count()
        return super().paginate_queryset(queryset, request, view)

    def get_paginated_response(self, data):
        """
        Override PageNumberPagination.get_paginated_response to include count of
        unread important notices.
        :param data: iterable data as results
        :return: DRF http response
        """
        return Response({
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'count': self.page.paginator.count,
            'importantUnreadCount': self.important_unread_count,
            'results': data
        })
