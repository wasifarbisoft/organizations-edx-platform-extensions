# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('edx_solutions_organizations', '0002_remove_organization_workgroups'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='attributes',
            field=models.CharField(max_length=512, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='include_manager_info',
            field=models.BooleanField(default=False),
        ),
    ]
