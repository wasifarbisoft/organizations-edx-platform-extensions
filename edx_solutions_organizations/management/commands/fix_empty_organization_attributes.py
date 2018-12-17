"""
Management command to fix organisations that have an empty attributes field.
"""
import logging
from django.core.management.base import BaseCommand
from edx_solutions_organizations.models import Organization

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command to fix organisations that have an empty attributes entry.
    """
    help = 'Updates organizations with an invalid blank attributes entry.'

    def handle(self, *args, **options):
        fix_count = Organization.objects.filter(attributes='').update(attributes='{}')
        log.info('Fixed %s Organizations with blank attributes', fix_count)
