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

# Every view class in this package that serves notices or notice metadata.
# Listed rather than discovered so that deleting a class cannot make the suite
# pass by having nothing left to check.
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
        """

        for relative, expected in EXPECTED_VIEWS.items():
            path = VIEWS.parent / relative
            declared = declared_permissions(path)
            for name in sorted(expected):
                permissions = set(declared.get(name, []))
                offending = permissions & FORBIDDEN
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


if __name__ == '__main__':
    unittest.main()
