"""
Run as

```
docker exec -ti <container-id> python \
/omniport/app/noticeboard/create_categories_and_banners.py
```

"""

import os

import django
from django.core import management
import swapper


def populate_nodes():
    from noticeboard.models import Banner
    from categories.models import Category

    Department = swapper.load_model('kernel', 'Department')
    from shell.models import Centre

    try:
        noticeboard_parent = Category.objects.get(
            slug='noticeboard'
        )
    except Category.DoesNotExist:
        noticeboard_parent = Category.objects.create(
            Name='Noticeboard',
            slug='noticeboard'
        )

    try:
        noticeboard_department = Category.objects.get(
            slug='noticeboard__departments'
        )
    except Category.DoesNotExist:
        noticeboard_department = Category.objects.create(
            name='Departments',
            slug='noticeboard__departments',
            parent=noticeboard_parent
        )
    try:
        noticeboard_centres = Category.objects.get(
            slug='noticeboard__centres'
        )
    except Category.DoesNotExist:
        noticeboard_centres = Category.objects.create(
            name='Centres',
            slug='noticeboard__centres',
            parent=noticeboard_parent
        )

    if noticeboard_centres is None or noticeboard_department is None:
        raise Exception("ABC", noticeboard_department, noticeboard_centres)

    for department in Department.objects.all():
        try:
            category_node = Category.objects.get(
                slug='noticeboard__' + department.code
            )
        except Category.DoesNotExist:
            category_node = Category.objects.create(
                slug='noticeboard__' + department.code,
                name=department.name,
                parent=noticeboard_department
            )
            print(category_node)

        try:
            banner = Banner.objects.get(name=department.name)
        except Banner.DoesNotExist:
            banner = Banner.objects.create(
                entity=department,
                name=department.name,
                category_node=category_node
            )
        print(banner)

    for centre in Centre.objects.all():
        try:
            category_node = Category.objects.get(
                slug='noticeboard__' + centre.code
            )
        except Category.DoesNotExist:
            category_node = Category.objects.create(
                slug='noticeboard__' + centre.code,
                name=centre.name,
                parent=noticeboard_centres
            )
            print(category_node)

        try:
            banner = Banner.objects.get(name=centre.name)
        except Banner.DoesNotExist:
            banner = Banner.objects.create(
                entity=centre,
                name=centre.name,
                category_node=category_node
            )
        print(banner)


if __name__ == '__main__':
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "omniport.settings")
    django.setup()

    # management.call_command('generatetree', 'noticeboard')
    populate_nodes()
