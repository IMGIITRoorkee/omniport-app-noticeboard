import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "omniport.settings")
import django
django.setup()
import swapper

from noticeboard.models import Banner
from categories.models import Category

Department = swapper.load_model('kernel', 'Department')

try:
    noticeboard_parent = Category.objects.get(slug='noticeboard')       
except Category.DoesNotExist:
    noticeboard_parent = Category.objects.create(
        Name='Noticeboard',
        slug='noticeboard'
    ).save()

try:
    noticeboard_department = Category.objects.get(slug='noticeboard__department')
except Category.DoesNotExist:
    noticeboard_department = Category.objects.create(
        name='Departments',
        slug='noticeboard__department',
        parent=noticeboard_parent
    ).save()
print(noticeboard_department)    
    
for department in Department.objects.all():
    try:
        category_node = Category.objects.get(
            slug='noticeboard__'+department.code
        )
    except Category.DoesNotExist:
        category_node = Category.objects.create(
            slug='noticeboard__' + department.code,
            name=department.name,
            parent=noticeboard_department
        )
        print(category_node)
    print(category_node)    

    try:    
        banner = Banner.objects.get(name=department.name)
    except Banner.DoesNotExist:
        banner = Banner.objects.create(
            entity=department,
            name=department.name,
            category_node=category_node)
    print(banner)    
