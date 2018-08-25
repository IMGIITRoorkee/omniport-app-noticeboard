from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from kernel.models.root import Model


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

    main_category = models.ForeignKey(
        to='MainCategory',
        on_delete=models.CASCADE,
    )

    class Meta:
        """
        Meta class for Banner
        """

        unique_together = (('main_category', 'entity_content_type', 'entity_object_id'),)

    def __str__(self):
        """
        Return the string representation of the model
        :return: the string representation of the model
        """

        entity = self.entity
        name = self.name
        main_category = self.main_category

        return f'{name}: {entity}, {main_category}'


class MainCategory(Model):
    """
    This class holds information about the main category
    """

    name = models.CharField(
        max_length=31,
    )

    class Meta:
        """
        Meta class for MainCategory
        """

        verbose_name_plural = 'main categories'

    def __str__(self):
        """
        Return the string representation of the model
        :return: the string representation of the model
        """

        name = self.name

        return f'{name}'
