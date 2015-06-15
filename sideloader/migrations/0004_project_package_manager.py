# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sideloader', '0003_auto_20141203_1708'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='package_manager',
            field=models.CharField(default=b'deb', max_length=64, blank=True),
            preserve_default=True,
        ),
    ]
