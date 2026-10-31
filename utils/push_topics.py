# Root slug of the noticeboard category tree; every row below it is prefixed
ROOT_SLUG = 'noticeboard'


def send_directly(category):
    """
    Mark a noticeboard category so that subscribing to it never joins an FCM
    topic, since notices are pushed to each subscriber's phones instead
    :param category: Category object, or a historical one in a migration
    :return: whether the category was changed
    """

    slug = category.slug
    if slug != ROOT_SLUG and not slug.startswith(f'{ROOT_SLUG}__'):
        return False

    meta = category.meta or {}
    if meta.get('fcmTopic') is False:
        return False

    category.meta = {**meta, 'fcmTopic': False}
    return True


def mark_on_save(sender, instance, **kwargs):
    """
    pre_save receiver that marks a noticeboard category as it is created
    """

    send_directly(instance)
