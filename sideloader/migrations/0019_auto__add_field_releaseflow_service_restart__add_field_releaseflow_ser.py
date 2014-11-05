# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'ReleaseFlow.service_restart'
        db.add_column(u'sideloader_releaseflow', 'service_restart',
                      self.gf('django.db.models.fields.BooleanField')(default=True),
                      keep_default=False)

        # Adding field 'ReleaseFlow.service_pre_stop'
        db.add_column(u'sideloader_releaseflow', 'service_pre_stop',
                      self.gf('django.db.models.fields.BooleanField')(default=True),
                      keep_default=False)

        # Adding field 'ReleaseFlow.puppet_run'
        db.add_column(u'sideloader_releaseflow', 'puppet_run',
                      self.gf('django.db.models.fields.BooleanField')(default=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'ReleaseFlow.service_restart'
        db.delete_column(u'sideloader_releaseflow', 'service_restart')

        # Deleting field 'ReleaseFlow.service_pre_stop'
        db.delete_column(u'sideloader_releaseflow', 'service_pre_stop')

        # Deleting field 'ReleaseFlow.puppet_run'
        db.delete_column(u'sideloader_releaseflow', 'puppet_run')


    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Group']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'sideloader.build': {
            'Meta': {'object_name': 'Build'},
            'build_file': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'build_time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'log': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'project': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['sideloader.Project']"}),
            'state': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'task_id': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255'})
        },
        u'sideloader.buildnumbers': {
            'Meta': {'object_name': 'BuildNumbers'},
            'build_num': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'package': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'})
        },
        u'sideloader.modulemanifest': {
            'Meta': {'object_name': 'ModuleManifest'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'structure': ('django.db.models.fields.TextField', [], {})
        },
        u'sideloader.project': {
            'Meta': {'object_name': 'Project'},
            'allowed_users': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.User']", 'symmetrical': 'False', 'blank': 'True'}),
            'branch': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'created_by_user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ProjectCreatedBy'", 'to': u"orm['auth.User']"}),
            'deploy_file': ('django.db.models.fields.CharField', [], {'default': "'.deploy.yaml'", 'max_length': '255'}),
            'github_url': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idhash': ('django.db.models.fields.CharField', [], {'max_length': '48'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'notifications': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'release_stream': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['sideloader.ReleaseStream']", 'null': 'True'}),
            'slack_channel': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'})
        },
        u'sideloader.release': {
            'Meta': {'object_name': 'Release'},
            'build': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['sideloader.Build']"}),
            'flow': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['sideloader.ReleaseFlow']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lock': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'release_date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'scheduled': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'waiting': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'sideloader.releaseflow': {
            'Meta': {'object_name': 'ReleaseFlow'},
            'auto_release': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'project': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['sideloader.Project']"}),
            'puppet_run': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'quorum': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'require_signoff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'service_pre_stop': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'service_restart': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'signoff_list': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'stream': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['sideloader.ReleaseStream']", 'null': 'True', 'blank': 'True'}),
            'stream_mode': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'sideloader.releasesignoff': {
            'Meta': {'object_name': 'ReleaseSignoff'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idhash': ('django.db.models.fields.CharField', [], {'max_length': '48'}),
            'release': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['sideloader.Release']"}),
            'signature': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'signed': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'sideloader.releasestream': {
            'Meta': {'object_name': 'ReleaseStream'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'push_command': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        u'sideloader.server': {
            'Meta': {'object_name': 'Server'},
            'change': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_checkin': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'last_puppet_run': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'specter_status': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'})
        },
        u'sideloader.servermanifest': {
            'Meta': {'object_name': 'ServerManifest'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'module': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['sideloader.ModuleManifest']"}),
            'release': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['sideloader.ReleaseFlow']"}),
            'value': ('django.db.models.fields.TextField', [], {})
        },
        u'sideloader.target': {
            'Meta': {'object_name': 'Target'},
            'current_build': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['sideloader.Build']", 'null': 'True', 'blank': 'True'}),
            'deploy_state': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'log': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'release': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['sideloader.ReleaseFlow']"}),
            'server': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['sideloader.Server']"})
        }
    }

    complete_apps = ['sideloader']