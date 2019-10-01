from django.contrib.contenttypes.models import ContentType
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets

from noticeboard.serializers import (
    PermissionsSerializer,
)
from noticeboard.models import (
    Permissions,
)


class BannerPermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This view fetches all the banner permissions of a person
    """

    serializer_class = PermissionsSerializer
    permission_classes = [IsAuthenticated, ]

    def get_queryset(self):
        person, roles = self.request.person, self.request.roles
        permissions = Permissions.objects.none()

        for role in roles.values():
            role_object = role['instance']
            role_content_type = ContentType.objects.get_for_model(role_object)

            permissions = permissions.union(Permissions.objects.filter(
                persona_object_id=role_object.id,
                persona_content_type=role_content_type))
        return permissions
