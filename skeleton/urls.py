from django.conf.urls import patterns, include, url

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Index
    url(r'^$', 'sideloader.views.index', name='home'),

    # Projects
    url(r'^projects/create$', 'sideloader.views.projects_create', name='projects_create'),
    url(r'^projects/edit/(?P<id>[\w-]+)$', 'sideloader.views.projects_edit', name='projects_edit'),
    url(r'^projects/view/(?P<id>[\w-]+)$', 'sideloader.views.projects_view', name='projects_view'),
    url(r'^projects/build/(?P<id>[\w-]+)$', 'sideloader.views.projects_build', name='projects_build'),
    url(r'^projects/delete/(?P<id>[\w-]+)$', 'sideloader.views.projects_delete', name='projects_delete'),

    url(r'^projects/build/view/(?P<id>[\w-]+)$', 'sideloader.views.build_view', name='build_view'),
    url(r'^projects/build/log/(?P<id>[\w-]+)$', 'sideloader.views.build_output', name='build_output'),
    url(r'^projects/build/cancel/(?P<id>[\w-]+)$', 'sideloader.views.build_cancel', name='build_cancel'),

    # Workflows
    url(r'^workflow/edit/(?P<id>[\w-]+)$', 'sideloader.views.workflow_edit', name='workflow_edit'),
    url(r'^workflow/delete/(?P<id>[\w-]+)$', 'sideloader.views.workflow_delete', name='workflow_delete'),
    url(r'^workflow/suck/(?P<id>[\w-]+)$', 'sideloader.views.release_delete', name='release_delete'),
    url(r'^workflow/create/(?P<project>[\w-]+)$', 'sideloader.views.workflow_create', name='workflow_create'),
    url(r'^workflow/push/(?P<flow>[\w-]+)/(?P<build>[\w-]+)$', 'sideloader.views.workflow_push', name='workflow_push'),
    url(r'^workflow/schedule/(?P<flow>[\w-]+)/(?P<build>[\w-]+)$', 'sideloader.views.workflow_schedule', name='workflow_schedule'),

    url(r'^workflow/manifests/(?P<id>[\w-]+)$', 'sideloader.views.manifest_view', name='manifest_view'),
    url(r'^workflow/manifests/add/(?P<id>[\w-]+)$', 'sideloader.views.manifest_add', name='manifest_add'),
    url(r'^workflow/manifests/edit/(?P<id>[\w-]+)$', 'sideloader.views.manifest_edit', name='manifest_edit'),
    url(r'^workflow/manifests/delete/(?P<id>[\w-]+)$', 'sideloader.views.manifest_delete', name='manifest_delete'),

    # Modules
    url(r'^modules/edit/(?P<id>[\w]+)$', 'sideloader.views.module_edit', name='module_edit'),
    url(r'^modules/create$', 'sideloader.views.module_create', name='module_create'),
    url(r'^modules/get_scheme/(?P<id>[\w]+)$', 'sideloader.views.module_scheme', name='module_scheme'),
    url(r'^modules/$', 'sideloader.views.module_index', name='module_index'),

    # Releases
    url(r'^releases/edit/(?P<id>[\w-]+)$', 'sideloader.views.release_edit', name='edit_release'),
    url(r'^releases/create$', 'sideloader.views.release_create', name='create_release'),
    url(r'^releases/$', 'sideloader.views.release_index', name='release_index'),

    # Servers
    url(r'^servers/$', 'sideloader.views.server_index', name='server_index'),
    url(r'^servers/log/(?P<id>[\w-]+)$', 'sideloader.views.server_log', name='server_log'),
    url(r'^servers/json/$', 'sideloader.views.get_servers', name='get_servers'),
    url(r'^servers/json/workflow/(?P<id>[\w-]+)$', 'sideloader.views.get_workflow_servers', name='get_workflow_servers'),

    # Help
    url(r'^help/$', 'sideloader.views.help_index', name='help_index'),

    # API
    url(r'^api/build/(?P<hash>[\w-]+)$', 'sideloader.views.api_build', name='api_build'),
    url(r'^api/rap/(?P<hash>[\w-]+)$', 'sideloader.views.api_sign', name='api_sign'),
    url(r'^api/checkin$', 'sideloader.views.api_checkin', name='api_checkin'),
    url(r'^api/enc/(?P<server>[\w.-]+)$', 'sideloader.views.api_enc', name='api_enc'),

    # Authentication
    url(r'^accounts/login/$', 'django.contrib.auth.views.login', {'template_name': 'login.html'}),
    url(r'^accounts/logout/$', 'django.contrib.auth.views.logout', {'next_page': '/'}, name='auth_logout'),
    url(r'^accounts/profile/$', 'sideloader.views.accounts_profile', name='accounts_profile'),

    url(r'', include('social_auth.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
)
