"""
Tests for who is allowed to read which notices

These drive the real permission class and the real queryset helper. Django and
Django REST framework are not installed to run them, because neither decision
touches the ORM: `isPublicInternet` reads two attributes off the request and
one off the notice, and `scope_to_visible_notices` either calls `.filter()` on
the queryset it was handed or does not. `rest_framework.permissions` is stubbed
for the import and the queryset is a stand-in that records whether it was
filtered, so the code under test is the code that ships.
"""

import itertools
import pathlib
import sys
import types
import unittest

APP = pathlib.Path(__file__).resolve().parent.parent


def _install_rest_framework_stub():
    """
    Provide the one name `permissions/public_notices.py` imports
    """

    if 'rest_framework.permissions' in sys.modules:
        return

    rest_framework = sys.modules.setdefault(
        'rest_framework', types.ModuleType('rest_framework')
    )
    permissions = types.ModuleType('rest_framework.permissions')

    class BasePermission:
        pass

    permissions.BasePermission = BasePermission
    rest_framework.permissions = permissions
    sys.modules['rest_framework.permissions'] = permissions


def _load_permission_class():
    import importlib.util

    _install_rest_framework_stub()
    path = APP / 'permissions/public_notices.py'
    spec = importlib.util.spec_from_file_location('public_notices', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.isPublicInternet


def _load_scoping_helper():
    """
    Read the helper out of utils/notices.py without importing Django

    The module imports models at the top, so the function is executed on its
    own rather than through an import of the package.
    """

    source = (APP / 'utils/notices.py').read_text()
    marker = 'def scope_to_visible_notices'
    if marker not in source:
        raise AssertionError('scope_to_visible_notices has gone missing')

    namespace = {}
    exec(source[source.index(marker):], namespace)
    return namespace['scope_to_visible_notices']


isPublicInternet = _load_permission_class()
scope_to_visible_notices = _load_scoping_helper()


class Request:
    """
    Stands in for the request the middleware hands to a view
    """

    def __init__(self, person, ip_address_rings):
        self.person = person
        self.ip_address_rings = ip_address_rings


class Notice:
    def __init__(self, is_public):
        self.is_public = is_public


class Queryset:
    """
    Records whether the caller narrowed it to public notices
    """

    def __init__(self, restricted=False):
        self.restricted = restricted

    def filter(self, **kwargs):
        assert kwargs == {'is_public': True}, kwargs
        return Queryset(restricted=True)


ANONYMOUS = None
LOGGED_IN = object()

RINGS = {
    'internet only': ['internet'],
    'institute network': ['intranet'],
    'both rings': ['internet', 'intranet'],
    'no ring': [],
}


def may_read_notice(person, rings, is_public):
    request = Request(person, rings)
    return isPublicInternet().has_object_permission(
        request, None, Notice(is_public)
    )


def list_is_restricted_to_public(person, rings):
    request = Request(person, rings)
    return scope_to_visible_notices(Queryset(), request).restricted


class TestAnonymousCallers(unittest.TestCase):
    """
    A caller with no person is the case both rules used to miss
    """

    def test_an_internal_notice_is_never_readable_anonymously(self):
        """
        This is the finding. On the institute network it used to be allowed.
        """

        for name, rings in RINGS.items():
            with self.subTest(network=name):
                self.assertFalse(
                    may_read_notice(ANONYMOUS, rings, is_public=False),
                    f'an anonymous caller on {name!r} could read an internal '
                    f'notice'
                )

    def test_the_list_is_always_narrowed_for_an_anonymous_caller(self):
        """
        The detail route and the list route have to agree
        """

        for name, rings in RINGS.items():
            with self.subTest(network=name):
                self.assertTrue(
                    list_is_restricted_to_public(ANONYMOUS, rings),
                    f'the notice list was not narrowed to public notices for '
                    f'an anonymous caller on {name!r}'
                )

    def test_a_public_notice_stays_readable_without_an_account(self):
        """
        The public noticeboard is a feature and must survive this change
        """

        for name in ('internet only', 'institute network', 'both rings'):
            with self.subTest(network=name):
                self.assertTrue(
                    may_read_notice(ANONYMOUS, RINGS[name], is_public=True),
                    f'a public notice stopped being readable from {name!r}'
                )

    def test_a_caller_with_no_ring_is_refused(self):
        """
        Pre-existing behaviour, kept
        """

        self.assertFalse(may_read_notice(ANONYMOUS, [], is_public=True))


class TestAuthenticatedCallersAreUnaffected(unittest.TestCase):
    """
    The change must cost a logged-in person nothing
    """

    def _previous_rule(self, rings, is_public):
        """
        The rule this change replaced, kept here as the comparison
        """

        if len(rings) == 0:
            return False
        from_internet = 'internet' in rings and len(rings) <= 1
        return is_public or (not from_internet)

    def test_every_logged_in_answer_is_unchanged(self):
        """
        All eight combinations answer exactly as they did before
        """

        for (name, rings), is_public in itertools.product(
                RINGS.items(), (True, False)):
            with self.subTest(network=name, is_public=is_public):
                self.assertEqual(
                    may_read_notice(LOGGED_IN, rings, is_public),
                    self._previous_rule(rings, is_public),
                    f'the answer for a logged-in caller on {name!r} changed'
                )

    def test_an_internal_notice_is_readable_on_the_institute_network(self):
        """
        The case the whole permission exists to allow
        """

        self.assertTrue(
            may_read_notice(LOGGED_IN, RINGS['institute network'],
                            is_public=False)
        )

    def test_an_internal_notice_is_not_readable_from_the_internet(self):
        """
        Pre-existing behaviour, kept
        """

        self.assertFalse(
            may_read_notice(LOGGED_IN, RINGS['internet only'], is_public=False)
        )


class TestExactlyTheIntendedCellsChanged(unittest.TestCase):
    """
    A blunt fix would also deny things that used to work, so the size of the
    change is asserted rather than described
    """

    def test_only_two_of_sixteen_answers_change(self):
        """
        Both are an anonymous caller reading an internal notice off-internet
        """

        changed = []
        for person_name, person in (('anonymous', ANONYMOUS),
                                    ('logged in', LOGGED_IN)):
            for name, rings in RINGS.items():
                for is_public in (True, False):
                    now = may_read_notice(person, rings, is_public)
                    before = TestAuthenticatedCallersAreUnaffected()._previous_rule(
                        rings, is_public
                    )
                    if now != before:
                        changed.append((person_name, name, is_public))

        self.assertEqual(
            sorted(changed),
            sorted([
                ('anonymous', 'both rings', False),
                ('anonymous', 'institute network', False),
            ]),
            f'the set of answers that changed is not the intended one: '
            f'{changed}'
        )


if __name__ == '__main__':
    unittest.main()
