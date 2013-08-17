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
    url(r'^projects/view/(?P<id>[\w-]+)$', 'sideloader.views.projects_view', name='projects_view'),
    url(r'^projects/build/(?P<id>[\w-]+)$', 'sideloader.views.projects_build', name='projects_build'),

    url(r'^projects/build/view/(?P<id>[\w-]+)$', 'sideloader.views.build_view', name='build_view'),

    # API
    url(r'^api/build/(?P<hash>[\w-]+)$', 'sideloader.views.api_build', name='api_build'),

    # Authentication
    url(r'^accounts/login/$', 'django.contrib.auth.views.login', {'template_name': 'login.html'}),
    url(r'^accounts/logout/$', 'django.contrib.auth.views.logout', {'next_page': '/'}, name='auth_logout'),
    url(r'^accounts/profile/$', 'sideloader.views.accounts_profile', name='accounts_profile'),

    url(r'', include('social_auth.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
)
