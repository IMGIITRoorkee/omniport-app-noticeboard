from django.contrib.contenttypes.models import ContentType
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets

from noticeboard.serializers import (
    PermissionSerializer,
)
from noticeboard.models import (
    Permission,
)


class BannerPermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This view fetches all the banner permissions of a person
    """

    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated, ]
    pagination_class = None

    def get_queryset(self):
        person = self.request.person
        return Permission.objects.filter(
            person=person,
        )
