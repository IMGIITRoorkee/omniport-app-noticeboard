import os
from itertools import islice
import datetime

import django
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError

from noticeboard.models import *


batch_size = 1000

def expire_notices(expire_before):
    
    date_array = str(expire_before).split("-")
    datetime_limit = datetime.datetime(int(date_array[0]) , int(date_array[1]) , int(date_array[2]) , tzinfo=datetime.timezone.utc)
    notice_exceptions = []
    notices_to_expire = []
    notices_to_delete = []

    failed = {
        '[EXPIRED NOTICE EXISTS]': [],
        '[SAVE EXPIRED NOTICE]': [],
        '[DELETE NOTICE]': [],
        '[SAVE EXPIRED NOTICE: INTIGRITY ERROR]': []
    }

    all_notices = Notice.objects.all()
    for notice in all_notices:
        if datetime_limit > notice.datetime_created :
            try:
                expired_notice = ExpiredNotice.objects.get(notice_id=notice.id)
            except ObjectDoesNotExist:
                expired_notice = ExpiredNotice(
                    uploader = notice.uploader, 
                    title = notice.title, 
                    content = notice.content, 
                    banner = notice.banner, 
                    expiry_date = notice.expiry_date, 
                    notice_id = notice.id,
                    send_email = notice.send_email,
                    is_draft  = notice.is_draft,
                    is_edited = notice.is_edited,
                    is_important = notice.is_important,
                    is_public = notice.is_public,
                    notice_created_on = notice.datetime_created
                )
                notices_to_expire.append(expired_notice)
                notices_to_delete.append(notice.id)
            else:
                failed['[EXPIRED NOTICE EXISTS]'].append(str(notice.id))
                
    while True:
        batch_to_expire = list(islice(notices_to_expire, batch_size))
        notices_to_expire = notices_to_expire[len(batch_to_expire):]
        batch_to_delete = list(islice(notices_to_delete, batch_size))
        notices_to_delete = notices_to_delete[len(batch_to_delete):]
        if len(batch_to_expire) == 0:
            break
        try:
            ExpiredNotice.objects.bulk_create(batch_to_expire, batch_size)
        except IntegrityError:
            failed['[SAVE EXPIRED NOTICE: INTIGRITY ERROR]'].append(str(batch_to_delete))
        except Exception as e:
            failed['[SAVE EXPIRED NOTICE]'].append(str(batch_to_delete))
        else:
            try:
                queryset = Notice.objects.filter(id__in = batch_to_delete)
                queryset.delete()
            except Exception as e:
                failed['[DELETE NOTICE]'].append(str(batch_to_delete))
        
    print(
        f"[ERROR]\n"
        f"[EXPIRED NOTICE EXISTS]\n"
        f"{', '.join(failed['[EXPIRED NOTICE EXISTS]'])}\n"
        f"\n[SAVE EXPIRED NOTICE: INTIGRITY ERROR]\n"
        f"{', '.join(failed['[SAVE EXPIRED NOTICE: INTIGRITY ERROR]'])}\n"
        f"\n[SAVE EXPIRED NOTICE]\n"
        f"{', '.join(failed['[SAVE EXPIRED NOTICE]'])}\n"
        f"\n[DELETE NOTICE]\n"
        f"{', '.join(failed['[DELETE NOTICE]'])}\n"
    )

