"""
Django database models supporting the organizations app
"""
from django.contrib.auth.models import Group, User
from django.db import models

from model_utils.models import TimeStampedModel
from edx_solutions_projects.models import Workgroup


class Organization(TimeStampedModel):
    """
    Main table representing the Organization concept.  Organizations are
    primarily a collection of Users.
    """
    name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255, null=True, blank=True)
    contact_name = models.CharField(max_length=255, null=True, blank=True)
    contact_email = models.EmailField(max_length=255, null=True, blank=True)
    contact_phone = models.CharField(max_length=50, null=True, blank=True)
    logo_url = models.CharField(max_length=255, blank=True, null=True)
    users = models.ManyToManyField(User, related_name="organizations", blank=True)
    groups = models.ManyToManyField(Group, related_name="organizations", blank=True)
    # attributes are client specific fields.These are optional fields
    # could be different for each organization
    attributes = models.CharField(max_length=512, default='{}')
    include_manager_info = models.BooleanField(default=False)


class OrganizationGroupUser(TimeStampedModel):
    """
    The OrganizationGroupUser model contains information describing the
    link between a particular user, group and an organization.
    """
    organization = models.ForeignKey(Organization)
    group = models.ForeignKey(Group)
    user = models.ForeignKey(User)

    class Meta(object):
        """
        Meta class for setting model meta options
        """
        unique_together = ("organization", "group", "user")
