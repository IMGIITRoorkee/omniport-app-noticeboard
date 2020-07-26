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

    def has_permission(self, request, view, **kwargs):
        """
        Primary permission for notices.
        :param request: Django request object
        :param view:
        :param kwargs: keyword arguments
        :return: boolean expression of permission
        """

        if request.method == 'GET' or request.method == 'DELETE':
            return True

        person = request.person
        data = request.data

        try:
            banner_id = data['banner']
        except KeyError:
            return False

        allowed_banner_ids = user_allowed_banners(person)
        if banner_id in allowed_banner_ids:
            if data.get('is_important', False):
                return has_super_upload_right(person, banner_id)
            else:
                return True
        else:
            return False

    def has_object_permission(self, request, view, obj, **kwargs):
        """
        Object level permission for notices.
        :param request: Django request object
        :param view:
        :param obj: instance of the model
        :param kwargs: keyword arguments
        :return: boolean expression of permission
        """
        if request.method == 'GET':
            return True

        return obj.uploader.id == request.person.id
