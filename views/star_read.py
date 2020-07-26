from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from django.http import Http404

from noticeboard.models import (
    Notice,
    NoticeUser,
)


class StarReadNotices(APIView):
    permission_classes = [IsAuthenticated, ]

    @staticmethod
    def check_notice_object(pk):
        if Notice.objects.filter(pk=pk).exists():
            pass
        else:
            raise Http404

    def post(self, request, format=None):
        """
        This view marks notices as read, unread, starred or unstarred

        We recieve the following data:
        notices: [List[id]]
        keyword: str  (unread, read, starred, unstarred)
        """

        notice_user, created = NoticeUser.objects.get_or_create(person=request.person)
        data = request.data

        if 'notices' not in data.keys() or 'keyword' not in data.keys():
            return Response(status=status.HTTP_400_BAD_REQUEST)

        notices, keyword = data['notices'], data['keyword']
        if keyword not in ['read', 'unread', 'star', 'unstar']:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        for notice_id in notices:
            self.check_notice_object(notice_id)

        if keyword == 'read':
            notice_user.read_notices.add(*notices)
        elif keyword == 'unread':
            notice_user.read_notices.remove(*notices)
        elif keyword == 'star':
            notice_user.starred_notices.add(*notices)
        elif keyword == 'unstar':
            notice_user.starred_notices.remove(*notices)

        notice_user.save()
        return Response(status=status.HTTP_201_CREATED)
