from emails.actions import email_push
from categories.models import Category

from noticeboard.apps import Config

def send_email(
    subject_text,
    body_text,
    persons=None,
    has_custom_user_target=True,
    by=None,
    email_ids=None,
    check_if_primary_email_verified=True,
    notice_id=None,
):
    """
    Utility to send an email
    :param subject_text: the subject of the e-mail
    :param body_text: the body of the e-mail
    :param persons: the list of ids of persons
    :param has_custom_user_target: whether to e-mail specified persons or not
    :param by: id of the person who is posting the mail
    :param email_ids: e-mail ids of the persons to whom it is to be sent
    :param check_if_primary_email_verified: Boolean for whether to check email
    verification
    :param notice_id: id of the notice instance for full_path
    """

    app_verbose_name = Config.verbose_name
    app_slug = Config.name

    category, _ = Category.objects.get_or_create(
        name=app_verbose_name,
        slug=app_slug,
    )
    full_path = f'https://stage.channeli.in/{app_slug}'
    if notice_id:
        full_path = f'{full_path}/notice/{notice_id}'
    relative_url_resolver = (
        '<base href="https://stage.channeli.in/" target="_blank">'
    )
    body_text = f'{relative_url_resolver}{body_text}'
    email_push(
        subject_text=subject_text,
        body_text=body_text,
        category=category,
        has_custom_user_target=has_custom_user_target,
        persons=persons,
        by=by,
        email_ids=email_ids,
        check_if_primary_email_verified=check_if_primary_email_verified,
        target_app_name=app_verbose_name,
        target_app_url=full_path,
    )
