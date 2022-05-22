from rest_framework.permissions import BasePermission

from omniport.settings.configuration.base import CONFIGURATION


class isPublicInternet(BasePermission):
    """
    Permission for public notices
    """

    def has_object_permission(self, request, view, obj, **kwargs):
        is_public = obj.is_public
        is_request_from_internet = False
        ip_address_rings = request.ip_address_rings

        # Check if the request only comes under the  internet IP address ring
        if ('internet' in ip_address_rings) and (len(ip_address_rings) <= 1):
            is_request_from_internet = True

        if len(ip_address_rings) == 0:
            return False

        return is_public or (not is_request_from_internet)

