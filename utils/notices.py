from django.contrib.contenttypes.models import ContentType

from noticeboard.models import Permissions, Notice


def user_allowed_banners(roles):
    """
    Given a user, return all the allowed banners.

    This view handles the permissions of a user under a particular banner
    """

    banner_ids = []
    for role in roles.values():
        role_object = role['instance']
        role_content_type = ContentType.objects.get_for_model(role_object)

        banner_ids += Permissions.objects.filter(
            persona_object_id=role_object.id,
            persona_content_type=role_content_type
        ).values_list('banner_id', flat=True)

    return banner_ids


def has_super_upload_right(roles, banner_id):
    """
    Having verified the permission to upload in the corresponding banner,
    check if person with given roles has the right to upload an IMPORTANT notice
    :param roles:
    :param banner_id:
    :return:
    """

    has_right = False
    for role in roles.values():
        role_object = role['instance']
        role_content_type = ContentType.objects.get_for_model(role_object)
        try:
            has_right |= Permissions.objects.get(
                persona_object_id=role_object.id,
                persona_content_type=role_content_type,
                banner_id=banner_id
            ).is_super_uploader
        except Permissions.DoesNotExist:
            continue

    return has_right


def get_drafted_notices(request):
    """
    Corresponding to a person, this function checks all the allowed banners
    and gets all the notices drafted according to those banners
    """

    roles = request.roles
    allowed_banner_ids = user_allowed_banners(roles)

    queryset = Notice.objects.filter(
        is_draft=True,
        banner_id__in=allowed_banner_ids).order_by('-datetime_modified')
    return queryset
