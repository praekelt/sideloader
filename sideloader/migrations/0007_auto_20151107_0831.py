# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sideloader', '0006_auto_20150624_0900'),
    ]

    operations = [
        migrations.AddField(
            model_name='releaseflow',
            name='notify',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='releaseflow',
            name='notify_list',
            field=models.TextField(blank=True),
        ),
    ]
