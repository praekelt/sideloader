# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sideloader', '0005_auto_20150614_1856'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='deploy_file',
            field=models.CharField(default=b'.deploy.yaml', max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
