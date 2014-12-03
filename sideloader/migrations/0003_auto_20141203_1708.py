# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sideloader', '0002_auto_20141203_1611'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='build_script',
            field=models.CharField(default=b'', max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='project',
            name='package_name',
            field=models.CharField(default=b'', max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='project',
            name='postinstall_script',
            field=models.CharField(default=b'', max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
