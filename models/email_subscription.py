from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from kernel.models.root import Mode
from noticeboard.models.banner import Banner
from noticeboard.models.user import User


class EmailSubscription(Model):
    """
    This class holds information about the email subscriptions
    of the users
    """

    banner = models.ForeignKey(
        to='Banner',
        on_delete=models.CASCADE,
    )

    user = models.ForeignKey(
        to='User',
        on_delete=models.CASCADE,
    )
    
    is_subscribed = models.BooleanField(
        default=False,
    )

    def __str__(self):
        """
        Return the string representation of the model
        :return: the string representation of the model
        """

        user = self.user
        banner = self.banner
        is_subscribed = self.is_subscribed

        return f'{user}: {banner}, {is_subscribed}'
