import re
import os
import shutil

from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from noticeboard.apps import Config


class CopyMedia(APIView):
    """
    Copy media entities like images or pdf files for notice content
    into Django media folder from personal files. This also ensures that
    even if media is deleted from personal file, the notice remains unharmed
    """
    permission_classes = [IsAuthenticated, ]
    http_method_names = ['post', ]

    def post(self, request, format=None):
        """
        Take the path from personal file from the django_filemanager, check MIME
        and copy the same in noticeboard media directory
        :param request:
        :param format:
        :return:
        """
        print(request.data, Config.name)
        try:
            path = request.data['path'].strip('/')
            source = os.path.normpath(os.path.join(settings.PERSONAL_DIR, path))
            authorized_pattern = str(os.path.join(
                settings.PERSONAL_DIR,
                str(request.person.folder_user.folder_name())
            ))

            print(source, authorized_pattern)
            if re.match(
                    pattern=f'^{authorized_pattern}/',
                    string=str(source),
            ) is None:
                return Response(status=status.HTTP_401_UNAUTHORIZED)

            if not os.path.exists(source):
                return Response(status=status.HTTP_400_BAD_REQUEST)

            filename = path.split('/')[-1]
            app_name = Config.name
            app_media = os.path.join(settings.MEDIA_DIR, app_name)
            os.makedirs(app_media, exist_ok=True)
            destination = os.path.join(app_media, filename)
            new_path = os.path.join(
                settings.MEDIA_URL, app_name, filename
            )
            try:
                shutil.copyfile(source, destination)
            except IOError:
                return Response(status=status.HTTP_417_EXPECTATION_FAILED)

            return Response(
                data={
                    'path': new_path
                }, status=status.HTTP_200_OK
            )
        except KeyError:
            return Response(status=status.HTTP_400_BAD_REQUEST)
