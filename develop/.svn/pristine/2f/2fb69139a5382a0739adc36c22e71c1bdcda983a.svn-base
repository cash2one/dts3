from django.conf.urls import url
from views import FileListView, UpFileView, ReportFileListView


urlpatterns = [
    url(r'^filelist/$', FileListView.as_view(), name='cus_file_list'),
    url(r'^upfile/$', UpFileView.as_view(), name='cus_up_file'),
    url(r'^reportfilelist/(?P<pk>[0-9]+)/$', ReportFileListView.as_view(), name='cus_reportfile_list'),
]
