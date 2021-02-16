from rest_framework import serializers
from omniport.utils import switcher
from formula_one.serializers.base import ModelSerializer
from categories.models import UserSubscription

from noticeboard.models import Notice, ExpiredNotice, NoticeUser, Banner
from noticeboard.serializers import BannerSerializer

AvatarSerializer = switcher.load_serializer('kernel', 'Person', 'Avatar')


class NoticeSerializer(ModelSerializer):
    """
    Serializer for Notice object creation
    """

    banner = serializers.PrimaryKeyRelatedField(
        queryset=Banner.objects,
    )

    class Meta:
        model = Notice
        exclude = ['uploader']


class NoticeDetailSerializer(ModelSerializer):
    """
    Serializer for Notice object
    """

    banner = BannerSerializer(
        read_only=True, fields=['id', 'name', 'category_node']
    )
    uploader = AvatarSerializer(read_only=True, fields=['id', 'full_name'])
    read = serializers.SerializerMethodField('is_read')
    starred = serializers.SerializerMethodField('is_starred')

    class Meta:
        model = Notice
        fields = ('id', 'title', 'datetime_modified', 'content',
                  'is_draft', 'is_edited', 'is_important', 'is_public',
                  'banner', 'read', 'starred', 'uploader', 'expiry_date')

    def is_read(self, obj):
        person = self.context['request'].person

        if person:
            notice_user, created = NoticeUser.objects.get_or_create(person=person)
            read_notices = notice_user.read_notices.all()

            return read_notices.filter(id=obj.id).exists()

        return False

    def is_starred(self, obj):
        person = self.context['request'].person

        if person:
            notice_user, created = NoticeUser.objects.get_or_create(person=person)
            starred_notices = notice_user.starred_notices.all()

            return starred_notices.filter(id=obj.id).exists()
        
        return False


class NoticeListSerializer(NoticeDetailSerializer):
    """
    Serializer for Notice object in list form
    """

    class Meta:
        model = Notice
        exclude = ['content']


class ExpiredNoticeDetailSerializer(ModelSerializer):
    """
    Serializer for Expired Notice object
    """

    banner = BannerSerializer(
        read_only=True, fields=['id', 'name', 'category_node']
    )
    uploader = AvatarSerializer(read_only=True, fields=['id', 'full_name'])
    id = serializers.IntegerField(source="notice_id")

    class Meta:
        model = ExpiredNotice
        fields = ('id', 'title', 'banner',
                  'is_important', 'datetime_modified', 'content', 'uploader')


class ExpiredNoticeListSerializer(ExpiredNoticeDetailSerializer):
    """
    Serializer for Expired Notice object in list form
    """

    class Meta:
        model = Notice
        exclude = ['content']
