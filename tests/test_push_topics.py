"""
Tests for marking the noticeboard categories as pushed to directly

`utils/push_topics.py` imports nothing from Omniport, so it is loaded straight
from its file and run on plain objects standing in for categories.
"""

import importlib.util
import pathlib
import types
import unittest

APP = pathlib.Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    'noticeboard_push_topics', APP / 'utils/push_topics.py'
)
push_topics = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(push_topics)


def category(slug, meta=None):
    return types.SimpleNamespace(slug=slug, meta=meta)


class SendDirectlyTestCase(unittest.TestCase):
    """
    Every noticeboard category opts out of FCM topics, and nothing else does
    """

    def test_the_root_and_every_row_below_it_are_marked(self):
        for slug in ('noticeboard', 'noticeboard__departments',
                     'noticeboard__departments__ce'):
            node = category(slug)

            self.assertTrue(push_topics.send_directly(node))
            self.assertEqual(node.meta, {'fcmTopic': False})

    def test_the_rest_of_the_meta_is_kept(self):
        node = category('noticeboard__authorities__dosw', {'icon': 'bell'})

        push_topics.send_directly(node)

        self.assertEqual(node.meta, {'icon': 'bell', 'fcmTopic': False})

    def test_an_explicit_true_is_overridden(self):
        node = category('noticeboard__centres', {'fcmTopic': True})

        self.assertTrue(push_topics.send_directly(node))
        self.assertEqual(node.meta, {'fcmTopic': False})

    def test_a_marked_category_is_left_alone(self):
        node = category('noticeboard__bhawans', {'fcmTopic': False})

        self.assertFalse(push_topics.send_directly(node))

    def test_other_apps_are_left_alone(self):
        for slug in ('placement_and_internship__results__pla',
                     'noticeboardish', 'lectures__noticeboard'):
            node = category(slug, {'fcmTopic': True})

            self.assertFalse(push_topics.send_directly(node))
            self.assertEqual(node.meta, {'fcmTopic': True})

    def test_the_save_hook_marks_the_instance(self):
        node = category('noticeboard__authorities__new')

        push_topics.mark_on_save(sender=object, instance=node, raw=False)

        self.assertEqual(node.meta, {'fcmTopic': False})


if __name__ == '__main__':
    unittest.main()
