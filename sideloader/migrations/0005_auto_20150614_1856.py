# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sideloader', '0004_project_package_manager'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='deploy_type',
            field=models.CharField(default=b'virtualenv', max_length=64),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='project',
            name='package_manager',
            field=models.CharField(default=b'deb', max_length=64),
            preserve_default=True,
        ),
    ]
