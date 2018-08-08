"""
Django database models supporting the organizations app
"""
import json
from django.contrib.auth.models import Group, User
from django.db import models
from django.core.validators import RegexValidator

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

    def is_attribute_exists(self, name):
        attributes = json.loads(self.attributes)
        return name in attributes.values()


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


class OrganizationUsersAttributes(models.Model):
    """Organization Users Attributes, used to store organization specific data"""
    KEY_REGEX = r"[-_a-zA-Z0-9]+"
    user = models.ForeignKey(User, related_name="user_attributes")
    organization = models.ForeignKey(Organization, related_name="user_attributes")
    key = models.CharField(max_length=255, db_index=True, validators=[RegexValidator(KEY_REGEX)])
    value = models.TextField()

    class Meta(object):
        unique_together = ("user", "key")

    @staticmethod
    def get_all_attributes(user):
        """
        Gets all attributes for a given user

        Returns: Set of (attributes type, value) pairs for each of the user's organizational attributes
        """
        return dict([(pref.key, pref.value) for pref in user.attributes.all()])

    @classmethod
    def get_value(cls, user, attribute_key, default=None):
        """Gets the user attributes value for a given key.
        """
        try:
            attribute = cls.objects.get(user=user, key=attribute_key)
            return attribute.value
        except cls.DoesNotExist:
            return default
