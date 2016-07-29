"""
Management command to revert renaming organizations app to edx_solutions_organizations
"""
import logging
from south.db import db
from django.core.management.base import BaseCommand
from django.db import transaction

log = logging.getLogger(__name__)


def get_table_names():
    """
    Returns list of table name organization app has
    """
    return [
        'organizationgroupuser',
        'organization_workgroups',
        'organization_groups',
        'organization_users',
        'organization',
    ]


class Command(BaseCommand):
    """
    Renames organizations app to edx_solutions_organizations and updates database accordingly
    """
    help = 'Makes database level changes to rename edx_solutions_organizations app to organizations'
    old_appname = 'edx_solutions_organizations'
    new_appname = 'organizations'

    def handle(self, *args, **options):
        log.info('reverting renaming of organizations app')
        with transaction.commit_on_success():
            db.execute(
                "UPDATE south_migrationhistory SET app_name = %s WHERE app_name = %s", [self.new_appname, self.old_appname]
            )
            db.execute(
                "UPDATE django_content_type SET app_label = %s WHERE app_label = %s", [self.new_appname, self.old_appname]
            )

            for table_name in get_table_names():
                db.rename_table(
                    '{old_app}_{table_name}'.format(old_app=self.old_appname, table_name=table_name),
                    '{new_app}_{table_name}'.format(new_app=self.new_appname, table_name=table_name),
                )

            log.info('renaming of organizations app successfully reverted')
