from formula_one.serializers.base import ModelSerializer
from categories.serializers import CategorySerializer
from noticeboard.models import Banner


class BannerSerializer(ModelSerializer):
    """
    Serializer for Banner object
    """

    category_node = CategorySerializer(many=False, read_only=True)
    parent_category = CategorySerializer(many=False, read_only=True)

    class Meta:
        model = Banner
        fields = ('id', 'name', 'category_node', 'parent_category')


class MainCategorySerializer(CategorySerializer):
    """
    Serializer for MainCategory object
    """

    def to_representation(self, instance):
        """
        Overwrite the to_representation of CategorySerializer
        """

        representation = super().to_representation(instance)
        representation['banner'] = [
            BannerSerializer(child.noticeboard_banner).data
            for child
            in instance.get_children()
        ]
        return representation
