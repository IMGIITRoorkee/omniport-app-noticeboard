from django.urls import re_path
from noticeboard.views import *

notice_list = NoticeViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
notice = NoticeViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'delete': 'destroy'
})

expired_notice_list = ExpiredNoticeViewSet.as_view({
    'get': 'list',
})
expired_notice = ExpiredNoticeViewSet.as_view({
    'get': 'retrieve',
    'delete': 'destroy',
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
    re_path(r'new/$', notice_list),
    re_path(r'new/(?P<pk>[0-9]+)/', notice),
    re_path(r'old/$', expired_notice_list, name='expired_notice_list'),
    re_path(r'old/(?P<notice_id>[0-9]+)/', expired_notice, name='expired_notice'),
    re_path(r'star_read/', StarReadNotices.as_view(), name='star_read'),
    re_path(r'filter_list/', filter_list),
    re_path(r'filter/', filter_view),
    re_path(r'date_filter_view/', date_filter_view),
    re_path(r'star_filter_view/', star_filter_view),
    re_path(r'permissions/', permissions),
    re_path(r'copy_media/', CopyMedia.as_view(), name='copy_media'),
]
