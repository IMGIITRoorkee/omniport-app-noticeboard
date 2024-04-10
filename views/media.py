import re
import os
import shutil
import tempfile
import hashlib

from django.conf import settings
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError
from PIL import Image
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from noticeboard.apps import Config


class CopyMedia(APIView):
    """
    Copy media entities like images or pdf files for notice content
    into Django media folder from network files. This also ensures that
    even if media is deleted from network file, the notice remains unharmed
    """
    permission_classes = [IsAuthenticated, ]
    http_method_names = ['post', ]

    def post(self, request, format=None):
        """
        Take the path from network file from the django_filemanager, check MIME
        and copy the same in noticeboard media directory
        :param request:
        :param format:
        :return:
        """
        try:
            user = request.user.username
            path = request.data['path'].strip('/')
            source = os.path.normpath(os.path.join(settings.NETWORK_STORAGE_ROOT, path))
            filename = path.split('/')[-1]
            file = os.path.splitext(filename)
            filename = user + '_' + hashlib.md5(str(file[0]).encode('utf-8')).hexdigest() + file[1]
            app_name = Config.name
            app_media = os.path.join(settings.MEDIA_DIR, app_name)
            os.makedirs(app_media, exist_ok=True)
            destination = os.path.join(app_media, filename)
            new_path = os.path.join(
                settings.MEDIA_URL, app_name, filename
            )
            media_path=new_path
            try:
                shutil.copyfile(source, destination)
            except IOError:
                return Response(status=status.HTTP_417_EXPECTATION_FAILED)

            try:
                pdf2img_path = os.path.join(app_media, 'pdf2images')
                os.makedirs(pdf2img_path, exist_ok=True)
                with tempfile.TemporaryDirectory() as temp_dir:
                    images = convert_from_path(
                        pdf_path=destination,
                        dpi=256,
                        fmt='jpeg',
                        output_folder=temp_dir
                    )
                    merged_image = self._merge_images(images)
                    image_file = os.path.splitext(filename)[0] + '.jpg'
                    image_path = os.path.join(
                        pdf2img_path,
                        image_file
                    )
                    merged_image.save(
                        fp=image_path,
                        format='JPEG'
                    )
                    media_path=new_path
                    new_path = os.path.join(
                        settings.MEDIA_URL, app_name, 'pdf2images', image_file
                    )
            except (PDFPageCountError, PDFSyntaxError) as e:
                image_path = destination
                pass
            try:
                Image.open(image_path)
            except OSError:
                return Response(
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY
                )
            return Response(
                data={
                    'path': new_path,
                    'media_path': media_path
                }, status=status.HTTP_200_OK
            )
        except KeyError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def _merge_images(images):
        """
        Merge converted images vertically into one image file
        :param images:
        :return:
        """
        widths, heights = zip(*(i.size for i in images))
        max_img_width = max(widths)
        total_height = sum(heights)
        merged_image = Image.new(
            mode=images[0].mode,
            size=(max_img_width, total_height),
        )
        y_offset = 0
        for image in images:
            merged_image.paste(image, (0, y_offset))
            y_offset += image.size[1]

        return merged_image
