import swapper
import datetime
from tinymce.models import HTMLField

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from formula_one.models.base import Model


class AbstractNotice(Model):
    """
    This abstract model is inherited by Notice and ExpiredNotice
    models

    This class holds general informations about a notice.
    """

    title = models.CharField(
        max_length=255,
    )
    content = HTMLField(
        'Content',
    )

    banner = models.ForeignKey(
        to='Banner',
        on_delete=models.CASCADE,
    )

    expiry_date = models.DateTimeField()

    send_email = models.BooleanField(
        default=False,
    )

    is_draft = models.BooleanField(
        default=False,
    )

    is_edited = models.BooleanField(
        default=False,
    )

    class Meta:
        """
        Meta class for AbstractNotice
        """

        abstract = True

    def __str__(self):
        """
        Return the string representation of the model
        :return: the string representation of the model
        """

        title = self.title
        banner = self.banner

        return f'{title}: {banner}'

    @property
    def notice_has_expired(self):
        """
        Return whether or not the notice has expired
        :return: True if the notice has expired, False otherwise
        """

        return datetime.date.today() > self.expiry_date


class Notice(AbstractNotice):
    """
    This class holds information about current notices

    When a notice is deleted manually by a user, it is soft
    deleted in this model.

    After the notice has expired or the notice created
    time has crossed one year, that notice is hard deleted
    from this model and moved to ExpiredNotice.
    The soft deleted notices are also moved to ExpiredNotice
    and remain soft deleted in that model.
    """

    pass


class ExpiredNotice(AbstractNotice):
    """
    This class holds information about the expired notices

    After the expired notice has crossed three years of time,
    a data dump is taken and the notices are hard deleted
    from this model.
    """

    notice_id = models.BigIntegerField(
        primary_key=True,
    )
