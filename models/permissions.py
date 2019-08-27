from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from formula_one.models.base import Model
from noticeboard.models.banner import Banner


class Permissions(Model):
    """
    This class holds information about the persona which
    have permissions to upload a notice through a specific
    banner
    """

    # Persona are mapped to models like Students, Faculty etc.
    persona_content_type = models.ForeignKey(
        to=ContentType,
        related_name='persona',
        on_delete=models.CASCADE,
    )
    persona_object_id = models.PositiveIntegerField()

    persona = GenericForeignKey(
        ct_field='persona_content_type',
        fk_field='persona_object_id',
    )

    # Personas are mapped to models like Departments, Bhawans etc.
    banner = models.ForeignKey(
        to='Banner',
        on_delete=models.CASCADE,
    )

    class Meta:
        """
        Meta class for Permissions
        """

        verbose_name_plural = 'permissions'

    def __str__(self):
        """
        Return the string representation of the model
        :return: the string representation of the model
        """

        persona = self.persona
        banner = self.banner

        return f'{persona}: {banner}'
