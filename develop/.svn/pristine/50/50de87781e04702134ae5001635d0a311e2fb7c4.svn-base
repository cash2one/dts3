from django.conf.urls import url

from .views import FileListView, UpFileView, gethead, savefields, MapFileListView


urlpatterns = [
    url(r'^filelist/$', FileListView.as_view(), name='che_file_list'),
    url(r'^upfile/$', UpFileView.as_view(), name='che_up_file'),
    url(r'^mapfilelist/(?P<pk>[0-9]+)/$', MapFileListView.as_view(), name='che_mapfile_list'),
    url(r'^gethead/$', gethead, name='gethead'),
    url(r'^savefields/$', savefields, name='savefields'),
]
