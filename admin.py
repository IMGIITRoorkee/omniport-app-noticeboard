from kernel.admin.site import omnipotence

from noticeboard.models import (
    Notice,
    ExpiredNotice,
    User,
    Permissions,
    Banner,
    MainCategory,
)

# Register all models

## TODO Generic foreign key relations admin view

omnipotence.register(Notice)
omnipotence.register(ExpiredNotice)

omnipotence.register(User)

omnipotence.register(Permissions)
omnipotence.register(Banner)
omnipotence.register(MainCategory)
