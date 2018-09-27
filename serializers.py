import swapper

from rest_framework import serializers

from kernel.serializers.root import ModelSerializer
from noticeboard.models import *


class BannerSerializer(ModelSerializer):
    """
    Serializer for Banner object
    """

    class Meta:
        model = Banner
        fields = ('id', 'name')

    def validate_banner_entity(self, value):
        """
        Validate the generic foreign key with the allowed models
        """

        if isinstance(value, swapper.load_model('kernel', 'Department')):
            pass
        else:
            raise serializers.ValidationError('Unexpected type of banner entity')


class PermissionsSerializer(ModelSerializer):
    """
    Serializer for Permissions object
    """
    banner = BannerSerializer()

    class Meta:
        model = Permissions
        fields = ('banner',)


class MainCategorySerializer(ModelSerializer):
    """
    Serializer for MainCategory object
    """
    banner = BannerSerializer(many=True, source='banner_set')

    class Meta:
        model = MainCategory
        fields = ('id', 'name', 'banner')


class NoticeSerializer(ModelSerializer):
    """
    Serializer for Notice object
    """

    banner = BannerSerializer()

    class Meta:
        model = Notice
        exclude = ()

    def create(self, validated_data):
        """
        Create and return new Notice, given the validated data
        """
        banner_data = validated_data.pop('banner')
        banner = Banner.objects.get(**banner_data)
        notice = Notice.objects.create(**validated_data, banner=banner)
        return notice


class NoticeDetailSerializer(ModelSerializer):
    """
    Serializer for Notice object
    """

    banner = BannerSerializer()

    class Meta:
        model = Notice
        fields = ('id', 'title', 'datetime_modified', 'content',
                  'is_draft', 'is_edited', 'banner')


class NoticeListSerializer(ModelSerializer):
    """
    Serializer for Notice object
    """

    banner = BannerSerializer(read_only=True)
    read = serializers.SerializerMethodField('is_read')
    starred = serializers.SerializerMethodField('is_starred')

    class Meta:
        model = Notice
        fields = ('id', 'title', 'banner', 'datetime_modified',
                  'is_draft', 'read', 'starred')

    def is_read(self, obj):
        person = self.context['request'].person

        if person:
            notice_user, created = User.objects.get_or_create(person=person)
            read_notices = notice_user.read_notices.all()

            if read_notices.filter(id=obj.id).exists():
                return True
        return False

    def is_starred(self, obj):
        person = self.context['request'].person

        if person:
            notice_user, created = User.objects.get_or_create(person=person)
            starred_notices = notice_user.starred_notices.all()

            if starred_notices.filter(id=obj.id).exists():
                return True
        return False


class NoticeUpdateSerializer(ModelSerializer):
    """
    Serializer for Notice object
    """

    class Meta:
        model = Notice
        fields = ('title', 'datetime_modified', 'content',
                  'is_draft', 'is_edited', 'send_email')


class ExpiredNoticeListSerializer(ModelSerializer):
    """
    Serializer for Expired Notice object
    """
    banner = BannerSerializer(read_only=True)

    class Meta:
        model = ExpiredNotice
        fields = ('notice_id', 'title', 'banner', 'datetime_modified')


class ExpiredNoticeDetailSerializer(ModelSerializer):
    """
    Serializer for Expired Notice object
    """
    banner = BannerSerializer(read_only=True)

    class Meta:
        model = ExpiredNotice
        fields = ('notice_id', 'title', 'banner',
                  'datetime_modified', 'content')
