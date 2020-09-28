from emails.actions import email_push

from noticeboard.apps import Config

def send_email(
    subject_text,
    body_text,
    persons=None,
    has_custom_user_target=True,
    send_only_to_subscribed_targets=True,
    category=None,
    by=None,
    check_if_primary_email_verified=True,
    notice_id=None,
):
    """
    Utility to send an email
    :param subject_text: the subject of the e-mail
    :param body_text: the body of the e-mail
    :param persons: the list of ids of persons
    :param has_custom_user_target: whether to e-mail specified persons or not
    :param send_only_to_subscribed_targets: Flag for a notification only to be sent to subscribed users
    :param category: Category under which notice was uploaded
    :param by: id of the person who is posting the mail
    :param notice_id: id of the notice instance for full_path
    """

    app_verbose_name = Config.verbose_name
    app_slug = Config.name

    full_path = f'https://internet.channeli.in/{app_slug}'
    if notice_id:
        full_path = f'{full_path}/notice/{notice_id}'
    relative_url_resolver = (
        '<base href="https://internet.channeli.in/" target="_blank">'
    )
    body_text = f'{relative_url_resolver}{body_text}'
    email_push(
        subject_text=subject_text,
        body_text=body_text,
        category=category,
        has_custom_user_target=has_custom_user_target,
        persons=persons,
        by=by,
        target_app_name=app_verbose_name,
        target_app_url=full_path,
        send_only_to_subscribed_targets=send_only_to_subscribed_targets,
    )
