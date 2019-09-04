import swapper

from rest_framework import serializers
from formula_one.serializers.base import ModelSerializer
from noticeboard.models import Permissions
from noticeboard.serializers.filters import BannerSerializer


class PermissionsSerializer(ModelSerializer):
    """
    Serializer for Permissions object
    """

    banner = BannerSerializer()

    class Meta:
        model = Permissions
        fields = ('banner', 'is_super_uploader')
