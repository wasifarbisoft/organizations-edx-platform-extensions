# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('edx_solutions_organizations', '0004_auto_20180710_1019'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrganizationUsersAttributes',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('key', models.CharField(db_index=True, max_length=255, validators=[django.core.validators.RegexValidator(b'[-_a-zA-Z0-9]+')])),
                ('value', models.TextField()),
                ('organization', models.ForeignKey(related_name='user_attributes', to='edx_solutions_organizations.Organization')),
                ('user', models.ForeignKey(related_name='user_attributes', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='organizationusersattributes',
            unique_together=set([('user', 'key')]),
        ),
    ]
