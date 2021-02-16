from rest_framework.permissions import BasePermission

from omniport.settings.configuration.base import CONFIGURATION

class isPublicInternet(BasePermission):
    """
    Permission for public notices 
    on internet.channeli.in
    """

    def has_object_permission(self, request, view, obj, **kwargs):
        is_public = obj.is_public
        site_id = CONFIGURATION.site.id

        if (site_id>1 and is_public) or site_id<=1:
            return True
        else:
            return False