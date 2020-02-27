import swapper
from django.db import models

from formula_one.models.base import Model


class Permission(Model):
    """
    This class holds information about the persona which
    have permissions to upload a notice through a specific
    banner
    """

    person = models.ForeignKey(
        to=swapper.get_model_name('kernel', 'Person'),
        related_name='notice_uploader',
        on_delete=models.CASCADE,
    )
    # Banner is mapped to models like Departments, Bhawans etc.
    banner = models.ForeignKey(
        to='Banner',
        on_delete=models.CASCADE,
    )
    is_super_uploader = models.BooleanField(
        default=False,
    )

    class Meta:
        """
        Meta class for Permission
        """

        verbose_name_plural = 'permissions'

    def __str__(self):
        """
        Return the string representation of the model
        :return: the string representation of the model
        """

        person = self.person
        banner = self.banner
        is_super_uploader = self.is_super_uploader

        return f'{person} | {banner} {" | *" if is_super_uploader else ""}'
