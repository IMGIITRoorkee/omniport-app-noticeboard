from categories.redisdb import Subscription
from notifications.actions import push_notification

from noticeboard.apps import Config


def is_first_publication(was_draft, is_draft):
    """
    A notice is announced once, when it first becomes visible
    :param was_draft: whether it was a draft before this save, True on create
    :param is_draft: whether it is a draft after this save
    :return: whether this save publishes it
    """

    return was_draft and not is_draft


def send_push_notification(template, category, notice_id, persons=None):
    """
    Push a notice to the people subscribed to its banner's category, or to an
    explicit list of people when an uploader targeted a whole role
    :param template: the text of the notification
    :param category: Category under which notice was uploaded
    :param notice_id: id of the notice, which a tap on the phone opens
    :param persons: ids of persons who replace the subscribers
    """

    if persons is None:
        # Redis returns ids as strings, which match nothing downstream
        persons = [
            int(person_id)
            for person_id in Subscription.fetch_people(
                category_slug=category.slug,
                action='notifications',
            )
        ]

    push_notification(
        template=template,
        category=category,
        web_onclick_url=f'{Config.name}/notice/{notice_id}',
        has_custom_users_target=True,
        persons=persons,
        send_only_to_subscribed_users=False,
        data={'type': 'noticeboard_notice', 'noticeId': str(notice_id)},
    )
