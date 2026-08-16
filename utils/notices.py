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


def scope_to_visible_notices(queryset, request):
    """
    Restrict a queryset of notices to the ones its caller is allowed to read

    A notice is either public or internal. An internal notice is readable only
    by an authenticated person reaching the portal from inside the institute
    network. Every other caller, which includes anyone who is not logged in and
    anyone whose request carries no ring information, sees the public notices
    alone.

    The check this replaces keyed on the IP address ring alone, so an
    anonymous caller on the institute network was indistinguishable from a
    logged in one and could read every notice without an account.

    :param queryset: the queryset of notices to restrict
    :param request: the request whose caller the queryset is restricted to
    :return: the restricted queryset
    """

    # A request that never reached the ring middleware carries no rings; scope
    # it as if it came from the internet rather than trusting it
    ip_address_rings = getattr(request, 'ip_address_rings', None) or ['internet']
    is_request_from_internet = (
        'internet' in ip_address_rings and len(ip_address_rings) <= 1
    )

    if getattr(request, 'person', None) is None or is_request_from_internet:
        return queryset.filter(is_public=True)

    return queryset
