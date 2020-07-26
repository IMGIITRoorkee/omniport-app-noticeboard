from noticeboard.models import Permission, Notice


def user_allowed_banners(person):
    """
    Given a user, return all the allowed banners.

    This view handles the permissions of a user under a particular banner
    """

    return set(
        Permission.objects.filter(
            person=person,
        ).values_list('banner_id', flat=True)
    )


def has_super_upload_right(person, banner_id):
    """
    Having verified the permission to upload in the corresponding banner,
    check if person with given roles has the right to upload an IMPORTANT notice
    :param person:
    :param banner_id:
    :return:
    """

    try:
        return Permission.objects.get(
            person=person,
            banner_id=banner_id
        ).is_super_uploader
    except Permission.DoesNotExist:
        return False


def get_drafted_notices(request):
    """
    Corresponding to a person, this function checks all the allowed banners
    and gets all the notices drafted according to those banners
    """

    person = request.person
    allowed_banner_ids = user_allowed_banners(person)

    queryset = Notice.objects.filter(
        is_draft=True,
        banner_id__in=allowed_banner_ids).order_by('-datetime_modified')
    return queryset
