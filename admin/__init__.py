from omniport.admin.site import omnipotence

from noticeboard.models import *

# Register all models

omnipotence.register(Notice)
omnipotence.register(ExpiredNotice)
omnipotence.register(NoticeUser)
omnipotence.register(Permission)
omnipotence.register(Banner)
