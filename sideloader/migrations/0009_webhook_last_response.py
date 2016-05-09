# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sideloader', '0008_webhook'),
    ]

    operations = [
        migrations.AddField(
            model_name='webhook',
            name='last_response',
            field=models.TextField(blank=True),
        ),
    ]
