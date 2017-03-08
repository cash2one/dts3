from django.conf.urls import url

from .views import (
    FileListView, ComListView, ReportFileListView, changecode,
    UpReportFileView, MapFileListView, getperm, taskdel,
    starcheck, ScheduleView, get_taskschedule, stoptask
)

urlpatterns = [
    url(r'^filelist/$', FileListView.as_view(), name='ana_file_list'),
    url(r'^comlist/$', ComListView.as_view(), name='com_list'),
    url(r'^reportfilelist/(?P<pk>[0-9]+)/$', ReportFileListView.as_view(), name='ana_reportfile_list'),
    url(r'^mapfilelist/(?P<pk>[0-9]+)/$', MapFileListView.as_view(), name='ana_mapfile_list'),
    url(r'^upreportfile/$', UpReportFileView.as_view(), name='ana_up_reportfile'),
    url(r'^getpermission/$', getperm, name='getpermission'),
    url(r'^starcheck/$', starcheck, name='starcheck'),
    url(r'^schedule/$', ScheduleView.as_view(), name='schedule'),
    url(r'^getschedule/$', get_taskschedule, name='task_schedule_list'),
    url(r'^stoptask/$', stoptask, name='stop_task'),
    url(r'^delwtask/$', taskdel, name='delete_task'),
    url(r'^changecode/$', changecode, name='change_apicode'),
]
