from django.urls import path
from noticeboard.views import HelloWorld

app_name = 'noticeboard'

urlpatterns = [
    path('hello_world/', HelloWorld.as_view(), name='hello_world'),
]
