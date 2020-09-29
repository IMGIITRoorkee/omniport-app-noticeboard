from notifications.actions import push_notification

from noticeboard.apps import Config

def send_push_notification(
    template,
    persons=None,
    has_custom_user_target=True,
    send_only_to_subscribed_targets=True,
    category=None,
    notice_id=None,
):
    """
    Utility to send an email
    :param template: the subject of the notification
    :param persons: the list of ids of persons
    :param has_custom_user_target: whether to notify specified persons or not
    :param send_only_to_subscribed_targets: Flag for a notification only to be sent to subscribed users
    :param category: Category under which notice was uploaded
    :param notice_id: id of the notice instance for full_path
    """

    app_verbose_name = Config.verbose_name
    app_slug = Config.name

    front_path = f'{app_slug}'
    if notice_id:
        front_path = f'{front_path}/notice/{notice_id}'
    push_notification(
        template=template,
        category=category,
        web_onclick_url=front_path,
        android_onclick_activity='',
        ios_onclick_action='',
        is_personalised=False,
        person=None,
        has_custom_users_target=has_custom_user_target,
        persons=persons,
        send_only_to_subscribed_users=send_only_to_subscribed_targets,
    )
