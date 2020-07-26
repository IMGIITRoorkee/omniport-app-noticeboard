from formula_one.serializers.base import ModelSerializer
from noticeboard.models import Permission
from noticeboard.serializers.filters import BannerSerializer


class PermissionSerializer(ModelSerializer):
    """
    Serializer for Permission object
    """

    banner = BannerSerializer()

    class Meta:
        model = Permission
        fields = ('banner', )

    def to_representation(self, instance):
        """

        :param instance:
        :return:
        """
        representation = super().to_representation(instance)
        representation['banner']['is_super_uploader'] = \
            instance.is_super_uploader
        return representation
