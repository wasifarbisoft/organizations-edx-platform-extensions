""" Organizations API URI specification """
from django.conf.urls import url

from edx_solutions_organizations import views as organizations_views


urlpatterns = [
    url(r'^(?P<organization_id>[0-9]+)/groups/(?P<group_id>[0-9]+)/users$',
        organizations_views.OrganizationsGroupsUsersList.as_view()),
    url(r'^(?P<organization_id>[0-9]+)/attributes',
        organizations_views.OrganizationAttributesView.as_view()),
]
