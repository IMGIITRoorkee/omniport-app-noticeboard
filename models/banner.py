from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from formula_one.models.base import Model


class Banner(Model):
    """
    This class holds information about the banners
    """

    # Entity is mapped to different models like Departments, Bhawans etc
    entity_content_type = models.ForeignKey(
        to=ContentType,
        related_name='banner',
        on_delete=models.CASCADE,
    )
    entity_object_id = models.PositiveIntegerField()

    entity = GenericForeignKey(
        ct_field='entity_content_type',
        fk_field='entity_object_id',
    )

    name = models.CharField(
        max_length=63,
    )

    category_node = models.OneToOneField(
        to='categories.Category',
        on_delete=models.CASCADE,
        related_name='noticeboard_banner'
    )        

    class Meta:
        """
        Meta class for Banner
        """

        unique_together = ((
            'category_node',
            'entity_content_type',
            'entity_object_id'
        ),)

    def __str__(self):
        """
        Return the string representation of the model
        :return: the string representation of the model
        """

        entity = self.entity
        name = self.name

        return f'{name}: {entity}'
