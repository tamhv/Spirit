from django.conf.urls import re_path

from . import views


app_name = 'flag'
urlpatterns = [
    re_path(r'^(?P<comment_id>[0-9]+)/create/$', views.create, name='create'),
]
