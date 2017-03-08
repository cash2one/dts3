from django.conf.urls import include, url
from django.contrib import admin
from django.conf.urls.static import static
from django.conf import settings

from .views import index, docs, delete, crm_cre_user


urlpatterns = [
    url(r'^$', index),
    url(r'^accounts/', include('account.urls')),
    url(r'^analyst/', include('analyst.urls')),
    url(r'^checker/', include('checker.urls')),
    url(r'^customer/', include('customer.urls')),
    url(r'^crm/creuser/$', crm_cre_user),
    url(r'^docs/$', docs),
    url(r'^down/analyst/(?P<pk>[0-9]+)/$', docs, name='down_analyst_mapfile'),
    url(r'^down/checker/(?P<pk>[0-9]+)/$', docs, name='down_checker_sourcefile'),
    url(r'^down/customer/(?P<pk>[0-9]+)/$', docs, name='down_customer_reportfile'),
    url(r'^delete/reportfile/$', delete, name='deletereportfile'),
    url(r'^delete/sourcefile/$', delete, name='deletesourcefile'),

    url(r'^dts/', include(admin.site.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
