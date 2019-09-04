from django.conf.urls import url
from noticeboard.views import *


notice_list = NoticeViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
notice = NoticeViewSet.as_view({
    'get': 'retrieve',
    'put': 'update'
})

expired_notice_list = ExpiredNoticeViewSet.as_view({
    'get': 'list',
})
expired_notice = ExpiredNoticeViewSet.as_view({
    'get': 'retrieve',
})

filter_list = FilterListViewSet.as_view({
    'get': 'list'
})
filter_view = FilterViewSet.as_view({
    'get': 'list'
})
date_filter_view = DateFilterViewSet.as_view({
    'get': 'list'
})
star_filter_view = StarFilterViewSet.as_view({
    'get': 'list'
})

permissions = BannerPermissionViewSet.as_view({
    'get': 'list'
})

urlpatterns = [
    url(r'new/$', notice_list),
    url(r'new/(?P<pk>[0-9]+)/', notice),
    url(r'old/$', expired_notice_list, name='expired_notice_list'),
    url(r'old/(?P<notice_id>[0-9]+)/', expired_notice, name='expired_notice'),
    url(r'star_read/', StarReadNotices.as_view(), name='star_read'),
    url(r'filter_list/', filter_list),
    url(r'filter/', filter_view),
    url(r'date_filter_view/', date_filter_view),
    url(r'star_filter_view/', star_filter_view),
    url(r'permissions/', permissions),
]
