import swapper

from rest_framework import serializers

from kernel.serializers.root import ModelSerializer
from categories.serializers import CategorySerializer
from noticeboard.models import Banner


class BannerSerializer(ModelSerializer):
    """
    Serializer for Banner object
    """

    category_node = serializers.PrimaryKeyRelatedField(many=False, read_only=True)

    class Meta:
        model = Banner
        fields = ('id', 'name', 'category_node')


class MainCategorySerializer(CategorySerializer):
    """
    Serializer for MainCategory object
    """

    def to_representation(self, instance):
        """
        Overwrite the to_represention of CategorySerializer
        """

        representation = super().to_representation(instance)
        representation['banner'] = [
            BannerSerializer(child.noticeboard_banner).data
            for child
            in instance.get_children()
        ]
        return representation
