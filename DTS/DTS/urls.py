from django.conf.urls import patterns, include, url
from django.contrib import admin
from .views import index, docs, delete, crm_cre_user


urlpatterns = patterns('',
    url(r'^$', index),
    url(r'^dts/', include(admin.site.urls)),
    url(r'^accounts/', include('account.urls')),
    url(r'^analyst/', include('analyst.urls')),
    url(r'^checker/', include('checker.urls')),
    url(r'^customer/', include('customer.urls')),
    url(r'^crm/creuser/$', crm_cre_user),
    url(r'^docs/$', docs),
    url(r'^down/analyst/mapfile/(?P<pk>[0-9]+)/$', docs, name='down_analyst_mapfile'),
    url(r'^down/checker/sourcefile/(?P<pk>[0-9]+)/$', docs, name='down_checker_sourcefile'),
    url(r'^down/checker/mapfile/(?P<pk>[0-9]+)/$', docs, name='down_checker_mapfile'),
    url(r'^down/customer/reportfile/(?P<pk>[0-9]+)/$', docs, name='down_customer_reportfile'),
    url(r'^delete/reportfile/$', delete, name='deletereportfile'),
    url(r'^delete/sourcefile/$', delete, name='deletesourcefile'),
)
