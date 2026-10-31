"""
Tests for which saves of a notice are announced, and to whom

These load `utils/send_push_notification.py` on its own, with the three
Omniport modules it imports replaced by stand-ins, so they run without Django
like the rest of this suite. The stand-ins are replaced again per test by
mocks that record what the helper asked for.
"""

import importlib.util
import pathlib
import sys
import types
import unittest
from unittest import mock

APP = pathlib.Path(__file__).resolve().parent.parent


def _load_push_module():
    """
    Load utils/send_push_notification.py with its Omniport imports stubbed
    """

    stand_ins = {
        'categories': types.ModuleType('categories'),
        'categories.redisdb': types.SimpleNamespace(Subscription=None),
        'notifications': types.ModuleType('notifications'),
        'notifications.actions': types.SimpleNamespace(push_notification=None),
        'noticeboard': types.ModuleType('noticeboard'),
        'noticeboard.apps': types.SimpleNamespace(
            Config=types.SimpleNamespace(name='noticeboard'),
        ),
    }
    path = APP / 'utils/send_push_notification.py'
    spec = importlib.util.spec_from_file_location('noticeboard_push', path)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, stand_ins):
        spec.loader.exec_module(module)
    return module


push = _load_push_module()

CATEGORY = types.SimpleNamespace(slug='noticeboard__departments__ce')


class FirstPublicationTestCase(unittest.TestCase):
    """
    A draft must not be announced, and an edit must not be announced again
    """

    def test_only_the_move_to_published_counts(self):
        self.assertTrue(push.is_first_publication(was_draft=True, is_draft=False))
        self.assertFalse(push.is_first_publication(was_draft=True, is_draft=True))
        self.assertFalse(push.is_first_publication(was_draft=False, is_draft=False))
        self.assertFalse(push.is_first_publication(was_draft=False, is_draft=True))


class SendPushNotificationTestCase(unittest.TestCase):
    def setUp(self):
        self.push_notification = mock.Mock()
        self.subscription = mock.Mock()
        for name, stand_in in (
            ('push_notification', self.push_notification),
            ('Subscription', self.subscription),
        ):
            patch = mock.patch.object(push, name, stand_in)
            patch.start()
            self.addCleanup(patch.stop)

    def sent(self):
        return self.push_notification.call_args.kwargs

    def test_subscribers_are_sent_as_ints(self):
        """
        Redis returns ids as strings, and a string id matches nothing
        downstream, so every send would silently reach nobody
        """

        self.subscription.fetch_people.return_value = ['7', '9']

        push.send_push_notification(
            template='Hostel allotment list', category=CATEGORY, notice_id=4211,
        )

        self.subscription.fetch_people.assert_called_once_with(
            category_slug='noticeboard__departments__ce',
            action='notifications',
        )
        self.assertEqual(self.sent()['persons'], [7, 9])
        self.assertTrue(self.sent()['has_custom_users_target'])
        self.assertFalse(self.sent()['send_only_to_subscribed_users'])

    def test_the_tap_payload_names_the_notice(self):
        self.subscription.fetch_people.return_value = []

        push.send_push_notification(
            template='Hostel allotment list', category=CATEGORY, notice_id=4211,
        )

        self.assertEqual(self.sent()['template'], 'Hostel allotment list')
        self.assertEqual(
            self.sent()['data'],
            {'type': 'noticeboard_notice', 'noticeId': '4211'},
        )
        self.assertEqual(self.sent()['web_onclick_url'], 'noticeboard/notice/4211')

    def test_a_role_target_ignores_subscriptions(self):
        push.send_push_notification(
            template='Hostel allotment list',
            category=CATEGORY,
            notice_id=4211,
            persons=[3],
        )

        self.subscription.fetch_people.assert_not_called()
        self.assertEqual(self.sent()['persons'], [3])
