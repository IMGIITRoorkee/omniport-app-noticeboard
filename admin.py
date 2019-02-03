from omniport.admin.site import omnipotence

from noticeboard.models import *

# Register all models

## TODO Generic foreign key relations admin view

omnipotence.register(Notice)
omnipotence.register(ExpiredNotice)

omnipotence.register(User)

omnipotence.register(Permissions)
omnipotence.register(Banner)
