from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404

from noticeboard.models import (
    Notice,
    ExpiredNotice,
    User,
)


class StarReadNotices(APIView):

    def get_object(self, pk):
        try:
            Notice.objects.get(pk=pk)
        except Notice.DoesNotExist:
            try:
                ExpiredNotice.objects.get(pk=pk)
            except ExpiredNotice.DoesNotExist:
                raise Http404

    def post(self, request, format=None):
        """
        This view marks notices as read, unread, starred or unstarred

        We recieve the following data:
        notices: [List[id]]
        keyword: str  (unread, read, starred, unstarred)
        """
        person = request.person
        notice_user, created = User.objects.get_or_create(person=person)

        data = request.data
        notices, keyword = data['notices'], data['keyword']
        if keyword not in ['read', 'unread', 'star', 'unstar']:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if person:
            for notice_id in notices:
                self.get_object(notice_id)

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
        return Response(status=status.HTTP_400_BAD_REQUEST)
