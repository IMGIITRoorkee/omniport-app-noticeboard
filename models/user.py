import swapper
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from kernel.models.root import Model
from noticeboard.models import Notice


class NoticeUser(Model):
    """
    This class holds information about a user
    """

    person = models.OneToOneField(
        to=swapper.get_model_name('kernel', 'Person'),
        related_name='notice_user',
        on_delete=models.CASCADE,
    )

    is_subscribed_via_email = models.BooleanField(
        default=False,
    )

    read_notices = models.ManyToManyField(
        to='Notice',
        related_name='read_notice_set',
        blank=True,
    )

    starred_notices = models.ManyToManyField(
        to='Notice',
        related_name='starred_notice_set',
        blank=True,
    )

    def __str__(self):
        """
        Return the string representation of the model
        :return: the string representation of the model
        """

        person = self.person
        
        return f'{person}'
