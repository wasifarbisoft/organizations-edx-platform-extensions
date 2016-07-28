# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import model_utils.fields
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0006_require_contenttypes_0002'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('name', models.CharField(max_length=255)),
                ('display_name', models.CharField(max_length=255, null=True, blank=True)),
                ('contact_name', models.CharField(max_length=255, null=True, blank=True)),
                ('contact_email', models.EmailField(max_length=255, null=True, blank=True)),
                ('contact_phone', models.CharField(max_length=50, null=True, blank=True)),
                ('logo_url', models.CharField(max_length=255, null=True, blank=True)),
                ('groups', models.ManyToManyField(related_name='organizations', to='auth.Group')),
                ('users', models.ManyToManyField(related_name='organizations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='OrganizationGroupUser',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('group', models.ForeignKey(to='auth.Group')),
                ('organization', models.ForeignKey(to='edx_solutions_organizations.Organization')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='organizationgroupuser',
            unique_together=set([('organization', 'group', 'user')]),
        ),
    ]
