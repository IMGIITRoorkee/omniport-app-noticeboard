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

    banner = BannerSerializer(fields=['id', 'name', 'category_node'])

    class Meta:
        model = Notice
        exclude = ['uploader']

    def create(self, validated_data):
        """
        Create and return new Notice, given the validated data
        """

        banner_data = validated_data.pop('banner')
        banner = Banner.objects.get(**banner_data)
        notice = Notice.objects.create(**validated_data, banner=banner)
        if notice.send_email:
            if notice.is_important:
                # send email to all people
                # People = swapper.load_model('kernel', 'Person')
                # people = Person.objects.all().values_list('id', flat=True)
                pass
            else:
                # send email to subscribed people
                people = UserSubscription.objects.filter(
                    category=notice.banner.category_node,
                    action='email',
                ).values_list('person_id', flat=True)
            # TODO send email to all ids in list 'people'
            # send_email_to(people, notice.content)
        return notice


class NoticeDetailSerializer(ModelSerializer):
    """
    Serializer for Notice object
    """

    banner = BannerSerializer(
        read_only=True, fields=['id', 'name', 'category_node']
    )
    uploader = AvatarSerializer(read_only=True, fields=['full_name'])
    read = serializers.SerializerMethodField('is_read')
    starred = serializers.SerializerMethodField('is_starred')

    class Meta:
        model = Notice
        fields = ('id', 'title', 'datetime_modified', 'content',
                  'is_draft', 'is_edited', 'is_important',
                  'banner', 'read', 'starred', 'uploader')

    def is_read(self, obj):
        person = self.context['request'].person

        notice_user, created = NoticeUser.objects.get_or_create(person=person)
        read_notices = notice_user.read_notices.all()

        return read_notices.filter(id=obj.id).exists()

    def is_starred(self, obj):
        person = self.context['request'].person

        notice_user, created = NoticeUser.objects.get_or_create(person=person)
        starred_notices = notice_user.starred_notices.all()

        return starred_notices.filter(id=obj.id).exists()


class NoticeListSerializer(NoticeDetailSerializer):
    """
    Serializer for Notice object in list form
    """

    class Meta:
        model = Notice
        exclude = ['content']


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

    banner = BannerSerializer(
        read_only=True, fields=['id', 'name', 'category_node']
    )
    uploader = AvatarSerializer(read_only=True)
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
