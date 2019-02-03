import swapper

from rest_framework import serializers
from kernel.serializers.root import ModelSerializer
from noticeboard.models import Notice, ExpiredNotice, User
from noticeboard.serializers import BannerSerializer


class NoticeSerializer(ModelSerializer):
    """
    Serializer for Notice object creation
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
    read = serializers.SerializerMethodField('is_read')
    starred = serializers.SerializerMethodField('is_starred')

    class Meta:
        model = Notice
        fields = ('id', 'title', 'datetime_modified', 'content',
                  'is_draft', 'is_edited', 'banner', 'read', 'starred')

    def is_read(self, obj):    
        person = self.context['request'].person

        notice_user, created = User.objects.get_or_create(person=person)
        read_notices = notice_user.read_notices.all()

        return read_notices.filter(id=obj.id).exists()

    def is_starred(self, obj):
        person = self.context['request'].person

        notice_user, created = User.objects.get_or_create(person=person)
        starred_notices = notice_user.starred_notices.all()

        return starred_notices.filter(id=obj.id).exists()


class NoticeListSerializer(NoticeDetailSerializer):
    """
    Serializer for Notice object in list form
    """

    excluded_fields = ('content',)


class NoticeUpdateSerializer(ModelSerializer):
    """
    Serializer to update Notice
    """

    class Meta:
        model = Notice
        fields = ('title', 'datetime_modified', 'content',
                  'is_draft', 'is_edited', 'send_email')


class ExpiredNoticeDetailSerializer(ModelSerializer):
    """
    Serializer for Expired Notice object
    """

    banner = BannerSerializer(read_only=True)
    id = serializers.IntegerField(source="notice_id")

    class Meta:
        model = ExpiredNotice
        fields = ('id', 'title', 'banner', 'datetime_modified', 'content')


class ExpiredNoticeListSerializer(ExpiredNoticeDetailSerializer):
    """
    Serializer for Expired Notice object in list form
    """

    excluded_fields = ('content',)
