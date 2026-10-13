import os
import time
import django
import swapper
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "omniport.settings")
django.setup()

from noticeboard.models import Notice, ExpiredNotice
from datetime import datetime, timedelta
from threading import Timer

x=datetime.today()
y = x.replace(day=x.day, hour=1, minute=0, second=0, microsecond=0) + timedelta(days=1)
delta_t=y-x
secs=delta_t.total_seconds()
def exp_func():
    all_notices = Notice.objects.filter(is_draft=False)
    for notice in all_notices:
        if notice.notice_has_expired:
            expired_notice = ExpiredNotice.objects.create(
                notice_id = notice.id,
                uploader = notice.uploader,
                title = notice.title,
                content = notice.content,
                banner = notice.banner,
                expiry_date = notice.expiry_date,
                is_important = notice.is_important,
                is_public = notice.is_public,
                is_edited = notice.is_edited,
            )
            print(expired_notice)
            notice.delete()

t = Timer(secs, exp_func)
t.start()