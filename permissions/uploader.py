from rest_framework.permissions import BasePermission

from noticeboard.utils.notices import (
    user_allowed_banners,
    has_super_upload_right,
)


class IsUploader(BasePermission):
    """
    A custom Django REST permission layer to check authorization
    over different actions on notices.
    """

    def has_permission(self, request, view):
        """
        Primary permission for notices.
        :param request: Django request object
        :param obj: instance of the model
        :return: boolean expression of permission
        """

        if request.method == 'GET' or request.method == 'DELETE':
            return True

        roles = request.roles
        data = request.data

        try:
            banner_id = data['banner']
        except KeyError:
            return False

        allowed_banner_ids = user_allowed_banners(roles)
        if banner_id in allowed_banner_ids:
            if data.get('is_important', False):
                return has_super_upload_right(roles, banner_id)
            else:
                return True
        else:
            return False

    def has_object_permission(self, request, view, obj):
        """
        Object level permission for notices.
        :param request: Django request object
        :param obj: instance of the model
        :return: boolean expression of permission
        """
        if request.method == 'GET':
            return True

        return obj.uploader.id == request.person.id
