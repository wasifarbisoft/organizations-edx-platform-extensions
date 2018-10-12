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
    attributes = models.TextField(default='{}')
    include_manager_info = models.BooleanField(default=False)

    def is_attribute_exists(self, name):
        """
        method to check if attribute exists and is active
        """
        attributes = json.loads(self.attributes)
        return name in [value['label'] for key, value in attributes.items() if value['is_active'] == True]

    def is_key_exists(self, name):
        """
        method to check if key exists and is active
        """
        attributes = json.loads(self.attributes)
        return name in [key for key, value in attributes.items() if value['is_active'] == True]

    def get_all_attributes(self):
        """
        method to get all active attributes
        """
        attributes = json.loads(self.attributes)
        return [
                    {
                        'key': key,
                        'label': value['label'],
                        'order': value['order']
                    } for key, value in attributes.items() if value['is_active'] == True
                ]

    def get_all_attribute_keys(self):
        """
        method to get all active attribute keys
        """
        attributes = json.loads(self.attributes)
        return [key for key, value in attributes.items() if value['is_active'] == True]


    @staticmethod
    def get_all_users_by_organization_attribute_filter(users, organizations, attribute_keys, attribute_values):
        attribute_active_keys = []
        for organization in organizations:
            attribute_active_keys = attribute_active_keys + organization.get_all_attribute_keys()

        for i, attribute_key in enumerate(attribute_keys):
            if attribute_key in attribute_active_keys:
                users = users.filter(
                    user_attributes__key=attribute_key,
                    user_attributes__value=attribute_values[i],
                    user_attributes__organization_id__in=organizations,
                ).all()
        return users


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

    @classmethod
    def get_value(cls, user, attribute_key, default=None):
        """Gets the user attributes value for a given key.
        """
        try:
            attribute = cls.objects.get(user=user, key=attribute_key)
            return attribute.value
        except cls.DoesNotExist:
            return default
