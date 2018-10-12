# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('edx_solutions_organizations', '0005_auto_20180807_0911'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organization',
            name='attributes',
            field=models.TextField(default=b'{}'),
        ),
    ]
