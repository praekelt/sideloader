from django.conf.urls import patterns, include, url

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Index
    url(r'^$', 'sideloader.views.index', name='home'),

    # Projects
    url(r'^projects/$', 'sideloader.views.projects_index', name='projects_index'),
    url(r'^projects/create$', 'sideloader.views.projects_create', name='projects_create'),
    url(r'^projects/edit/(?P<id>[\w-]+)$', 'sideloader.views.projects_edit', name='projects_edit'),
    url(r'^projects/build/(?P<id>[\w-]+)$', 'sideloader.views.projects_build', name='projects_build'),

    # API
    url(r'^api/build/(?P<hash>[\w-]+)$', 'sideloader.views.api_build', name='api_build'),

    # Authentication
    url(r'^accounts/login/$', 'django.contrib.auth.views.login', {'template_name': 'login.html'}),


    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
)
