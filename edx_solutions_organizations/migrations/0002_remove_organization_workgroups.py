# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('edx_solutions_organizations', '0001_initial'),
    ]

    operations = [
        # We need to drop table created by workgroups manytomany field if it exists
        # We cannot write schema migration for it due to workgroups field
        # dependency on edx_solutions_projects app
        migrations.RunSQL(
            "DROP TABLE IF EXISTS `edx_solutions_organizations_organization_workgroups`;",
        )
    ]
