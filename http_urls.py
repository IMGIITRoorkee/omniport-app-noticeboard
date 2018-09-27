from django.conf.urls import url
from noticeboard.views import *

app_name = 'noticeboard'


notice_list = NoticeViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
notice = NoticeViewSet.as_view({
    'get': 'retrieve',
    'put': 'update'
})

expired_notices = ExpiredNoticeViewSet.as_view({
    'get': 'list',
})
expired_notice = ExpiredNoticeViewSet.as_view({
    'get': 'retrieve',
})

search_notices = SearchViewSet.as_view({
    'get': 'list'
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

permissions = PersonPermissionViewSet.as_view({
    'get': 'list'
})

urlpatterns = [
    url(r'notice_list/', notice_list),
    url(r'notice/(?P<pk>[0-9]+)/$', notice),
    url(r'expired_notices/', expired_notices),
    url(r'expired_notice/(?P<notice_id>[0-9]+)/$', expired_notice),
    url(r'search/', search_notices),
    url(r'star_read/', StarReadNotices.as_view(), name='star_read'),
    url(r'filter_list/', filter_list),
    url(r'filter/', filter_view),
    url(r'date_filter_view/', date_filter_view),
    url(r'star_filter_view/', star_filter_view),
    url(r'permissions/', permissions),
]
