# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Build',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('build_time', models.DateTimeField(auto_now_add=True)),
                ('state', models.IntegerField(default=0)),
                ('task_id', models.CharField(default=b'', max_length=255)),
                ('log', models.TextField(default=b'')),
                ('build_file', models.CharField(max_length=255)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BuildNumbers',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('package', models.CharField(unique=True, max_length=255)),
                ('build_num', models.IntegerField(default=0)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ModuleManifest',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('key', models.CharField(max_length=255)),
                ('structure', models.TextField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=255)),
                ('github_url', models.CharField(max_length=255)),
                ('branch', models.CharField(max_length=255)),
                ('deploy_file', models.CharField(default=b'.deploy.yaml', max_length=255)),
                ('idhash', models.CharField(max_length=48)),
                ('notifications', models.BooleanField(default=True)),
                ('slack_channel', models.CharField(default=b'', max_length=255, blank=True)),
                ('allowed_users', models.ManyToManyField(to=settings.AUTH_USER_MODEL, blank=True)),
                ('created_by_user', models.ForeignKey(related_name='ProjectCreatedBy', to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Release',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('release_date', models.DateTimeField(auto_now_add=True)),
                ('scheduled', models.DateTimeField(null=True, blank=True)),
                ('waiting', models.BooleanField(default=True)),
                ('lock', models.BooleanField(default=False)),
                ('build', models.ForeignKey(to='sideloader.Build')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ReleaseFlow',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('stream_mode', models.IntegerField(default=0)),
                ('require_signoff', models.BooleanField(default=False)),
                ('signoff_list', models.TextField(blank=True)),
                ('quorum', models.IntegerField(default=0)),
                ('service_restart', models.BooleanField(default=True)),
                ('service_pre_stop', models.BooleanField(default=False)),
                ('puppet_run', models.BooleanField(default=True)),
                ('auto_release', models.BooleanField(default=False)),
                ('project', models.ForeignKey(to='sideloader.Project')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ReleaseSignoff',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('signature', models.CharField(max_length=255)),
                ('idhash', models.CharField(max_length=48)),
                ('signed', models.BooleanField(default=False)),
                ('release', models.ForeignKey(to='sideloader.Release')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ReleaseStream',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('push_command', models.CharField(max_length=255)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Server',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('last_checkin', models.DateTimeField(auto_now_add=True)),
                ('last_puppet_run', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(default=b'', max_length=255, blank=True)),
                ('change', models.BooleanField(default=True)),
                ('specter_status', models.CharField(default=b'', max_length=255, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ServerManifest',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('value', models.TextField()),
                ('module', models.ForeignKey(to='sideloader.ModuleManifest')),
                ('release', models.ForeignKey(to='sideloader.ReleaseFlow')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Target',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('deploy_state', models.IntegerField(default=0)),
                ('log', models.TextField(default=b'')),
                ('current_build', models.ForeignKey(blank=True, to='sideloader.Build', null=True)),
                ('release', models.ForeignKey(to='sideloader.ReleaseFlow')),
                ('server', models.ForeignKey(to='sideloader.Server')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='releaseflow',
            name='stream',
            field=models.ForeignKey(blank=True, to='sideloader.ReleaseStream', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='release',
            name='flow',
            field=models.ForeignKey(to='sideloader.ReleaseFlow'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='project',
            name='release_stream',
            field=models.ForeignKey(to='sideloader.ReleaseStream', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='build',
            name='project',
            field=models.ForeignKey(to='sideloader.Project'),
            preserve_default=True,
        ),
    ]
