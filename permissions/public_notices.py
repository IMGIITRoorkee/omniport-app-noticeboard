from rest_framework.permissions import BasePermission


class isPublicInternet(BasePermission):
    """
    Permission for public notices
    """

    def has_object_permission(self, request, view, obj, **kwargs):
        ip_address_rings = request.ip_address_rings

        if len(ip_address_rings) == 0:
            return False

        # A public notice is readable by anyone who can reach the portal
        if obj.is_public:
            return True

        # An internal notice needs an authenticated person. The ring on its
        # own used to be enough, which meant an anonymous caller on the
        # institute network could read every notice without an account.
        if getattr(request, 'person', None) is None:
            return False

        # Check if the request only comes under the  internet IP address ring
        is_request_from_internet = (
            'internet' in ip_address_rings and len(ip_address_rings) <= 1
        )

        return not is_request_from_internet
