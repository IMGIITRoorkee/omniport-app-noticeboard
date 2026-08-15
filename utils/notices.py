from noticeboard.models import Permission, Notice, NoticeUser


def get_notice_user(person):
    """
    Given a person, return the corresponding notice user, or None when there is
    no person, as is the case for anonymous callers and for authenticated users
    that have no person attached to them
    :param person: the person on the request, possibly None
    :return: the notice user, or None
    """

    if person is None:
        return None

    notice_user, created = NoticeUser.objects.get_or_create(person=person)
    return notice_user


def exclude_read_notices(queryset, person):
    """
    Drop the notices that the given person has read, leaving the queryset
    untouched when there is no person, since such a caller has read nothing
    :param queryset: the queryset of notices to narrow
    :param person: the person on the request, possibly None
    :return: the narrowed queryset
    """

    if person is None:
        return queryset

    return queryset.exclude(
        read_notice_set__person=person
    )


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
