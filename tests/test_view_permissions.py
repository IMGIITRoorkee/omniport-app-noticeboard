"""
Tests for the permission classes the notice views declare

`DEFAULT_PERMISSION_CLASSES` in the backend only supplies the
`permission_classes` attribute to a view that does not set one. Every view
here sets one, so the project-wide default never reaches them and the
declaration in this package is the only thing deciding who gets in. These
tests read those declarations out of the source with `ast`, which needs
neither Django nor DRF installed.
"""

import ast
import pathlib
import unittest

VIEWS = pathlib.Path(__file__).resolve().parent.parent / 'views'

# A permission that admits unauthenticated callers to a safe method. Anonymous
# read is what F-7 is about, so none of these views may declare it.
FORBIDDEN = {'IsAuthenticatedOrReadOnly', 'AllowAny'}

# Listed rather than discovered, so deleting a class cannot empty the suite
EXPECTED_VIEWS = {
    'views/notices.py': {'NoticeViewSet', 'ExpiredNoticeViewSet'},
    'views/filters.py': {
        'FilterListViewSet',
        'FilterViewSet',
        'DateFilterViewSet',
        'InstituteNoticesDateFilterViewSet',
        'StarFilterViewSet',
    },
}

# The modules whose `get_queryset` returns notices rather than categories or
# permissions, and so has to narrow what the caller is allowed to read.
NOTICE_MODULES = ('views/notices.py', 'views/filters.py')

# The views that may relax permissions per action, and what they must return
ANONYMOUS_READ_VIEWS = {
    'views/notices.py': {
        'NoticeViewSet': {
            'actions': {'retrieve'},
            'permissions': {'IsUploader', 'isPublicInternet'},
        },
    },
}


def declared_permissions(path):
    """
    Return {class name: [permission names]} for one views module
    """

    tree = ast.parse(path.read_text())
    declarations = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for statement in node.body:
            if not isinstance(statement, ast.Assign):
                continue
            targets = [
                target.id for target in statement.targets
                if isinstance(target, ast.Name)
            ]
            if 'permission_classes' not in targets:
                continue
            names = [
                element.id for element in ast.walk(statement.value)
                if isinstance(element, ast.Name)
            ]
            declarations[node.name] = names

    return declarations


def methods(path, method_name):
    """
    Return {class name: the node of that method} for one module
    """

    tree = ast.parse(path.read_text())
    found = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for statement in node.body:
            if not isinstance(statement, ast.FunctionDef):
                continue
            if statement.name != method_name:
                continue
            found[node.name] = statement

    return found


def names_used(node):
    """
    Every name the method refers to
    """

    return {
        element.id for element in ast.walk(node)
        if isinstance(element, ast.Name)
    }


def strings_used(node):
    """
    Every string literal in the method, its docstring aside
    """

    body = node.body[1:] if ast.get_docstring(node) else node.body

    return {
        element.value
        for statement in body for element in ast.walk(statement)
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    }


def permissions_returned(node):
    """
    The permission classes a `get_permissions` override returns explicitly

    A bare `return super().get_permissions()` is the fall-through to the
    declaration, which the other tests already cover, so it is skipped.
    """

    returned = set()

    for statement in ast.walk(node):
        if not isinstance(statement, ast.Return) or statement.value is None:
            continue
        if isinstance(statement.value, ast.Call):
            continue
        returned |= {
            element.id for element in ast.walk(statement.value)
            if isinstance(element, ast.Name)
        }

    return returned


class TestNoticeViewsRequireAuthentication(unittest.TestCase):
    """
    A notice must not be readable without an account
    """

    def test_every_expected_view_declares_permissions(self):
        """
        The views this suite is about must exist and declare something

        Without this, renaming or deleting a viewset would silently empty the
        checks below rather than fail them.
        """

        for relative, expected in EXPECTED_VIEWS.items():
            path = VIEWS.parent / relative
            declared = declared_permissions(path)
            missing = expected - set(declared)
            self.assertFalse(
                missing,
                f'{relative}: these views no longer declare permission_classes '
                f'or have been renamed: {sorted(missing)}'
            )

    def test_no_notice_view_admits_anonymous_readers(self):
        """
        This is F-7

        Every view module is scanned, and every class in it, so that a view
        added later cannot slip past a hardcoded list of the ones that exist
        today. F-7 arose one omitted line at a time.
        """

        for path in sorted(VIEWS.glob('*.py')):
            relative = f'views/{path.name}'
            for name, permissions in sorted(declared_permissions(path).items()):
                offending = set(permissions) & FORBIDDEN
                self.assertFalse(
                    offending,
                    f'{relative}: {name} declares {sorted(offending)}, which '
                    f'lets an unauthenticated caller read notices'
                )

    def test_every_notice_view_requires_authentication(self):
        """
        Requiring it explicitly, rather than relying on the project default

        These views declare `permission_classes`, so the backend's
        `DEFAULT_PERMISSION_CLASSES` will never apply to them.
        """

        for relative, expected in EXPECTED_VIEWS.items():
            path = VIEWS.parent / relative
            declared = declared_permissions(path)
            for name in sorted(expected):
                self.assertIn(
                    'IsAuthenticated', declared.get(name, []),
                    f'{relative}: {name} does not require authentication'
                )

    def test_only_the_public_notice_route_relaxes_its_permissions(self):
        """
        A `get_permissions` override is invisible to the scans above

        It replaces `permission_classes` at request time, so a second one, or
        a wider set of actions in the one there is, reopens anonymous read
        without changing a declaration.
        """

        for path in sorted(VIEWS.glob('*.py')):
            relative = f'views/{path.name}'
            expected = ANONYMOUS_READ_VIEWS.get(relative, {})
            overriding = methods(path, 'get_permissions')
            self.assertEqual(
                set(overriding), set(expected),
                f'{relative}: {sorted(overriding)} override get_permissions, '
                f'which decides permissions per request rather than by the '
                f'declaration this suite reads'
            )
            for name, rule in sorted(expected.items()):
                self.assertEqual(
                    strings_used(overriding[name]), rule['actions'],
                    f'{relative}: {name}.get_permissions relaxes its '
                    f'permissions for actions other than '
                    f'{sorted(rule["actions"])}'
                )
                self.assertEqual(
                    permissions_returned(overriding[name]), rule['permissions'],
                    f'{relative}: {name}.get_permissions no longer returns '
                    f'{sorted(rule["permissions"])} for '
                    f'{sorted(rule["actions"])}. Pinning the action alone lets '
                    f'the one deliberately open route become AllowAny.'
                )


class TestNoticeQuerysetsAreScoped(unittest.TestCase):
    """
    Authentication alone does not decide which notices a caller may read

    `scope_to_visible_notices` is what keeps an internal notice away from a
    person on the internet ring and from a session with no person, so every
    notice queryset has to route through it.
    """

    def test_every_notice_queryset_is_scoped_to_the_caller(self):
        for relative in NOTICE_MODULES:
            path = VIEWS.parent / relative
            querysets = methods(path, 'get_queryset')
            self.assertTrue(
                querysets, f'{relative}: no get_queryset left to check'
            )
            for name, node in sorted(querysets.items()):
                self.assertIn(
                    'scope_to_visible_notices', names_used(node),
                    f'{relative}: {name}.get_queryset does not narrow its '
                    f'notices to what the caller is allowed to read'
                )

    def test_notice_routes_keep_the_object_level_check(self):
        """
        The detail routes are reached by primary key, not through a list
        """

        declared = declared_permissions(VIEWS / 'notices.py')
        for name in sorted(EXPECTED_VIEWS['views/notices.py']):
            self.assertIn(
                'isPublicInternet', declared.get(name, []),
                f'views/notices.py: {name} no longer applies the object level '
                f'check that refuses an internal notice fetched by id'
            )


if __name__ == '__main__':
    unittest.main()
