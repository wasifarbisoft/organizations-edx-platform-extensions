# pylint: disable=E1103

"""
Run these tests @ Devstack:
paver test_system -s lms -t organizations
"""
import uuid
import mock
import ddt
from urllib import urlencode

from django.conf import settings
from django.test.client import Client
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test.utils import override_settings
from django.utils.translation import ugettext as _

from gradebook.models import StudentGradebook
from .models import OrganizationGroupUser
from student.models import UserProfile
from student.tests.factories import CourseEnrollmentFactory, UserFactory, GroupFactory
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.modulestore.tests.factories import CourseFactory
from edx_solutions_api_integration.test_utils import (
    APIClientMixin,
)
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.django_utils import (
    ModuleStoreTestCase,
    TEST_DATA_SPLIT_MODULESTORE
)

@mock.patch.dict("django.conf.settings.FEATURES", {'ENFORCE_PASSWORD_POLICY': False,
                                                   'ADVANCED_SECURITY': False,
                                                   'PREVENT_CONCURRENT_LOGINS': False
                                                   })
@ddt.ddt
class OrganizationsApiTests(ModuleStoreTestCase, APIClientMixin):
    """ Test suite for Users API views """

    MODULESTORE = TEST_DATA_SPLIT_MODULESTORE

    def setUp(self):
        super(OrganizationsApiTests, self).setUp()
        self.test_server_prefix = 'https://testserver'
        self.base_organizations_uri = '/api/server/organizations/'
        self.base_users_uri = '/api/server/users'
        self.base_groups_uri = '/api/server/groups'
        self.test_organization_name = str(uuid.uuid4())
        self.test_organization_display_name = 'Test Org'
        self.test_organization_contact_name = 'John Org'
        self.test_organization_contact_email = 'john@test.org'
        self.test_organization_contact_phone = '+1 332 232 24234'
        self.test_organization_logo_url = 'org_logo.jpg'

        self.test_user_email = str(uuid.uuid4())
        self.test_user_username = str(uuid.uuid4())
        self.test_user = User.objects.create(
            email=self.test_user_email,
            username=self.test_user_username
        )
        profile = UserProfile(user=self.test_user)
        profile.city = 'Boston'
        profile.save()

        self.test_user2 = User.objects.create(
            email=str(uuid.uuid4()),
            username=str(uuid.uuid4())
        )
        profile2 = UserProfile(user=self.test_user2)
        profile2.city = 'NYC'
        profile2.save()

        self.course = CourseFactory.create()
        self.second_course = CourseFactory.create(
            number="899"
        )

        cache.clear()

    def setup_test_organization(self, org_data=None):
        """
        Creates a new organization with given org_data
        if org_data is not present it would create organization with test values
        :param org_data: Dictionary witch each item represents organization attribute
        :return: newly created organization
        """
        org_data = org_data if org_data else {}
        data = {
            'name': org_data.get('name', self.test_organization_name),
            'display_name': org_data.get('display_name', self.test_organization_display_name),
            'contact_name': org_data.get('contact_name', self.test_organization_contact_name),
            'contact_email': org_data.get('contact_email', self.test_organization_contact_email),
            'contact_phone': org_data.get('contact_phone', self.test_organization_contact_phone),
            'logo_url': org_data.get('logo_url', self.test_organization_logo_url),
            'users': org_data.get('users', []),
            'groups': org_data.get('groups', [])
        }
        response = self.do_post(self.base_organizations_uri, data)
        self.assertEqual(response.status_code, 201)
        return response.data

    def test_organizations_list_post(self):
        users = []
        for i in xrange(1, 6):
            data = {
                'email': 'test{}@example.com'.format(i),
                'username': 'test_user{}'.format(i),
                'password': 'test_pass',
                'first_name': 'John{}'.format(i),
                'last_name': 'Doe{}'.format(i),
                'city': 'Boston',
            }
            response = self.do_post(self.base_users_uri, data)
            self.assertEqual(response.status_code, 201)
            users.append(response.data['id'])

        organization = self.setup_test_organization(org_data={'users': users})
        confirm_uri = '{}{}{}/'.format(
            self.test_server_prefix,
            self.base_organizations_uri,
            organization['id']
        )
        self.assertEqual(organization['url'], confirm_uri)
        self.assertGreater(organization['id'], 0)
        self.assertEqual(organization['name'], self.test_organization_name)
        self.assertEqual(organization['display_name'], self.test_organization_display_name)
        self.assertEqual(organization['contact_name'], self.test_organization_contact_name)
        self.assertEqual(organization['contact_email'], self.test_organization_contact_email)
        self.assertEqual(organization['contact_phone'], self.test_organization_contact_phone)
        self.assertEqual(organization['logo_url'], self.test_organization_logo_url)
        self.assertIsNotNone(organization['created'])
        self.assertIsNotNone(organization['modified'])

        users_get_uri = "{}users/?view=ids".format(confirm_uri)
        response = self.do_get(users_get_uri)
        self.assertEqual(len(response.data), len(users))

    def test_organizations_list_get(self):
        courses = CourseFactory.create_batch(5)
        users = UserFactory.create_batch(5)

        organizations = []
        for i in xrange(30):
            data = {
                'name': 'Test Organization {}'.format(i),
                'display_name': 'Test Name {}'.format(i),
                'contact_name': 'Test Contact {}'.format(i),
                'contact_email': 'test{}@test.com'.format(i),
                'contact_phone': '12313{}'.format(i),
            }
            organizations.append(self.setup_test_organization(org_data=data))


        for i, user in enumerate(users):
            user.organizations.add(organizations[0]['id'])
            CourseEnrollmentFactory.create(user=user, course_id=courses[i].id)

        # to test if number_of_courses has distinct course count
        CourseEnrollmentFactory.create(user=users[0], course_id=courses[1].id)

        test_uri = '{}'.format(self.base_organizations_uri)
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], len(organizations))
        self.assertEqual(len(response.data['results']), 20)
        self.assertEqual(response.data['num_pages'], 2)
        for i, organization in enumerate(response.data['results']):
            uri = '{}{}{}/'.format(self.test_server_prefix, self.base_organizations_uri, organizations[i]['id'])
            self.assertEqual(organization['url'], uri)
            self.assertEqual(organization['id'], organizations[i]['id'])
            self.assertEqual(organization['name'], organizations[i]['name'])
            self.assertEqual(organization['display_name'], organizations[i]['display_name'])
            self.assertEqual(organization['contact_name'], organizations[i]['contact_name'])
            self.assertEqual(organization['contact_email'], organizations[i]['contact_email'])
            self.assertEqual(organization['contact_phone'], organizations[i]['contact_phone'])
            self.assertEqual(organization['logo_url'], self.test_organization_logo_url)
            number_of_courses = 0 if i else 5
            self.assertEqual(organization['number_of_courses'], number_of_courses)
            self.assertIsNotNone(organization['created'])
            self.assertIsNotNone(organization['modified'])

        # fetch organization data with page outside range
        response = self.do_get('{}?page=5'.format(test_uri))
        self.assertEqual(response.status_code, 404)

        # test with page_size 0, should not paginate and return all results
        response = self.do_get('{}?page_size=0'.format(test_uri))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), len(organizations))

    def test_organizations_list_number_of_participants(self):
        """
        Test number_of_participants field in organization list
        """
        number_of_participants = 5
        users = UserFactory.create_batch(number_of_participants)
        courses = CourseFactory.create_batch(2)
        org = self.setup_test_organization()

        # get org list without any users/participants
        response = self.do_get(self.base_organizations_uri)
        self.assertEqual(response.data['results'][0]['number_of_participants'], 0)

        for user in users:
            user.organizations.add(org['id'])

        response = self.do_get(self.base_organizations_uri)
        self.assertEqual(response.data['results'][0]['number_of_participants'], number_of_participants)

        # enroll users in both course to test distinct count
        for user in users:
            CourseEnrollmentFactory.create(user=user, course_id=courses[0].id)
            CourseEnrollmentFactory.create(user=user, course_id=courses[1].id)

        response = self.do_get(self.base_organizations_uri)
        self.assertEqual(response.data['results'][0]['number_of_participants'], number_of_participants)

    def test_organizations_list_get_filter_by_display_name(self):
        organizations = []
        organizations.append(self.setup_test_organization(org_data={'display_name': 'Abc Organization'}))
        organizations.append(self.setup_test_organization(org_data={'display_name': 'Xyz Organization'}))
        organizations.append(self.setup_test_organization(org_data={'display_name': 'Abc Organization'}))

        # test for not matching organization
        test_uri = '{}?display_name={}'.format(self.base_organizations_uri, 'no org')
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 0)

        # test for matching organization
        test_uri = '{}?display_name={}'.format(self.base_organizations_uri, 'Xyz Organization')
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['display_name'], 'Xyz Organization')

        # test for multiple matching organization with same display_name
        test_uri = '{}?display_name={}'.format(self.base_organizations_uri, 'Abc Organization')
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 2)
        self.assertEqual(response.data['results'][0]['display_name'], 'Abc Organization')
        self.assertEqual(response.data['results'][1]['display_name'], 'Abc Organization')
        self.assertNotEqual(response.data['results'][0]['id'], response.data['results'][1]['id'])

    def test_organizations_detail_get(self):
        org = self.setup_test_organization()
        test_uri = '{}{}/'.format(self.base_organizations_uri, org['id'])
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)
        confirm_uri = self.test_server_prefix + test_uri
        self.assertEqual(response.data['url'], confirm_uri)
        self.assertGreater(response.data['id'], 0)
        self.assertEqual(response.data['name'], self.test_organization_name)
        self.assertEqual(response.data['display_name'], self.test_organization_display_name)
        self.assertEqual(response.data['contact_name'], self.test_organization_contact_name)
        self.assertEqual(response.data['contact_email'], self.test_organization_contact_email)
        self.assertEqual(response.data['contact_phone'], self.test_organization_contact_phone)
        # we have separate api for groups and users organization so that data should not be returned
        self.assertFalse("users" in response.data)
        self.assertFalse("groups" in response.data)
        self.assertIsNotNone(response.data['created'])
        self.assertIsNotNone(response.data['modified'])

    def test_organizations_detail_get_undefined(self):
        test_uri = '{}123456789/'.format(self.base_organizations_uri)
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 404)

    def test_organizations_detail_delete(self):
        data = {'name': self.test_organization_name}
        response = self.do_post(self.base_organizations_uri, data)
        self.assertEqual(response.status_code, 201)
        test_uri = '{}{}/'.format(self.base_organizations_uri, response.data['id'])
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)
        response = self.do_delete(test_uri, data={})
        self.assertEqual(response.status_code, 204)
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 404)

    def test_organizations_list_post_invalid(self):
        data = {
            'name': self.test_organization_name,
            'display_name': self.test_organization_display_name,
            'contact_name': self.test_organization_contact_name,
            'contact_email': 'testatme.com',
            'contact_phone': self.test_organization_contact_phone
        }
        response = self.do_post(self.base_organizations_uri, data)
        self.assertEqual(response.status_code, 400)

    def test_organizations_list_post_with_groups(self):
        groups = []
        for i in xrange(1, 6):
            data = {
                'name': '{} {}'.format('Test Group', i),
                'type': 'series',
                'data': {'display_name': 'My first series'}
            }
            response = self.do_post(self.base_groups_uri, data)
            self.assertEqual(response.status_code, 201)
            groups.append(response.data['id'])

        organization = self.setup_test_organization(org_data={'groups': groups})
        groups_get_uri = "{base_url}{organization_id}/groups/?view=ids".format(
            base_url=self.base_organizations_uri,
            organization_id=organization['id'],
        )
        response = self.do_get(groups_get_uri)
        self.assertEqual(len(response.data), len(groups))

    def test_organizations_users_post(self):
        organization = self.setup_test_organization()
        test_uri = '{}{}/'.format(self.base_organizations_uri, organization['id'])
        users_uri = '{}users/'.format(test_uri)
        data = {"id": self.test_user.id}
        response = self.do_post(users_uri, data)
        self.assertEqual(response.status_code, 201)

        users_get_uri = '{}users/?view=ids'.format(test_uri)
        response = self.do_get(users_get_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0], self.test_user.id)

    def test_organizations_users_post_invalid_user(self):
        organization = self.setup_test_organization()
        test_uri = '{}{}/'.format(self.base_organizations_uri, organization['id'])
        users_uri = '{}users/'.format(test_uri)
        data = {"id": 123456}
        response = self.do_post(users_uri, data)
        self.assertEqual(response.status_code, 400)

    def test_organizations_groups_get_post(self):
        organization = self.setup_test_organization()

        # create groups
        max_groups, groups, contactgroup_count = 4, [], 2
        for i in xrange(1, max_groups + 1):
            grouptype = 'contactgroup' if i <= contactgroup_count else 'series'
            data = {
                'name': '{} {}'.format('Test Group', i),
                'type': grouptype,
                'data': {'display_name': 'organization contacts group'}
            }
            response = self.do_post(self.base_groups_uri, data)
            self.assertEqual(response.status_code, 201)
            groups.append(response.data['id'])

        test_uri = '{}{}/'.format(self.base_organizations_uri, organization['id'])
        groups_uri = '{}groups/'.format(test_uri)
        for group in groups:
            data = {"id": group}
            response = self.do_post(groups_uri, data)
            self.assertEqual(response.status_code, 201)
        response = self.do_get(groups_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), max_groups)

        # get organization groups with type filter
        response = self.do_get('{}?type=contactgroup'.format(groups_uri))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), contactgroup_count)

        # post an invalid group
        data = {"id": '45533333'}
        response = self.do_post(groups_uri, data)
        self.assertEqual(response.status_code, 400)

    def test_organizations_users_get(self):
        organization = self.setup_test_organization()
        test_uri = '{}{}/'.format(self.base_organizations_uri, organization['id'])
        users_uri = '{}users/'.format(test_uri)
        data = {"id": self.test_user.id}
        response = self.do_post(users_uri, data)
        self.assertEqual(response.status_code, 201)
        response = self.do_get(users_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['id'], self.test_user.id)
        self.assertEqual(response.data[0]['username'], self.test_user.username)
        self.assertEqual(response.data[0]['email'], self.test_user.email)

    def test_organizations_courses_get(self):
        organization = self.setup_test_organization()
        courses = CourseFactory.create_batch(2)
        users = UserFactory.create_batch(2)

        for course in courses:
            CourseOverview.get_from_id(course.id)

        for i, user in enumerate(users):
            user.organizations.add(organization['id'])
            CourseEnrollmentFactory.create(user=users[0], course_id=courses[i].id)

        test_uri = '{}{}/'.format(self.base_organizations_uri, organization['id'])
        courses_uri = '{}courses/'.format(test_uri)
        response = self.do_get(courses_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['id'], unicode(courses[0].id))
        self.assertEqual(len(response.data[0]['enrolled_users']), 1)
        self.assertEqual(response.data[1]['id'], unicode(courses[1].id))
        self.assertEqual(len(response.data[1]['enrolled_users']), 1)

        # test course uniqueness if multiple organization users are enrolled in same course
        CourseEnrollmentFactory.create(user=users[1], course_id=courses[0].id)
        response = self.do_get(courses_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['id'], unicode(courses[0].id))
        self.assertEqual(len(response.data[0]['enrolled_users']), 2)
        self.assertEqual(response.data[1]['id'], unicode(courses[1].id))
        self.assertEqual(len(response.data[1]['enrolled_users']), 1)

    def test_organizations_courses_get_organization_user_with_no_course_enrollment(self):
        organization = self.setup_test_organization()
        user = UserFactory.create()
        user.organizations.add(organization['id'])

        courses_uri = '{}{}/courses/'.format(self.base_organizations_uri, organization['id'])
        response = self.do_get(courses_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_organizations_courses_search_by_mobile_available(self):
        organization = self.setup_test_organization()
        courses = CourseFactory.create_batch(2)
        mobile_course = CourseFactory.create(mobile_available=True)
        courses.append(mobile_course)
        users = UserFactory.create_batch(3)

        for course in courses:
            CourseOverview.get_from_id(course.id)

        for i, user in enumerate(users):
            CourseEnrollmentFactory.create(user=user, course_id=courses[i].id)
            user.organizations.add(organization['id'])

        # fetch all courses for organization
        courses_uri = '{}{}/courses/'.format(self.base_organizations_uri, organization['id'])
        response = self.do_get(courses_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

        # fetch mobile available courses for organization
        response = self.do_get("{}?mobile_available=false".format(courses_uri))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['mobile_available'], False)
        self.assertEqual(response.data[1]['mobile_available'], False)

        # fetch mobile available courses for organization
        response = self.do_get("{}?mobile_available=true".format(courses_uri))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['mobile_available'], True)

    def test_organizations_courses_get_enrolled_users(self):
        organization = self.setup_test_organization()
        courses = CourseFactory.create_batch(2)
        users = UserFactory.create_batch(5)

        for course in courses:
            CourseOverview.get_from_id(course.id)

        for i, user in enumerate(users):
            CourseEnrollmentFactory.create(user=user, course_id=courses[i % 2].id)
            if i < 3:
                user.organizations.add(organization['id'])

        # test with all users enrolled but only 3 in organization
        test_uri = '{}{}/'.format(self.base_organizations_uri, organization['id'])
        courses_uri = '{}courses/'.format(test_uri)
        response = self.do_get(courses_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['id'], unicode(courses[0].id))
        self.assertEqual(len(response.data[0]['enrolled_users']), 2)
        self.assertEqual(response.data[0]['enrolled_users'][0], users[0].id)
        self.assertEqual(response.data[0]['enrolled_users'][1], users[2].id)
        self.assertEqual(response.data[1]['id'], unicode(courses[1].id))
        self.assertEqual(len(response.data[1]['enrolled_users']), 1)
        self.assertEqual(response.data[1]['enrolled_users'][0], users[1].id)

        # now add remaining 2 users to organization
        for user in users[3:]:
            user.organizations.add(organization['id'])

        response = self.do_get(courses_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['id'], unicode(courses[0].id))
        self.assertEqual(len(response.data[0]['enrolled_users']), 3)
        self.assertEqual(response.data[0]['enrolled_users'][0], users[0].id)
        self.assertEqual(response.data[0]['enrolled_users'][1], users[2].id)
        self.assertEqual(response.data[0]['enrolled_users'][2], users[4].id)
        self.assertEqual(response.data[1]['id'], unicode(courses[1].id))
        self.assertEqual(len(response.data[1]['enrolled_users']), 2)
        self.assertEqual(response.data[1]['enrolled_users'][0], users[1].id)
        self.assertEqual(response.data[1]['enrolled_users'][1], users[3].id)

    def test_organizations_users_get_with_course_count(self):
        CourseEnrollmentFactory.create(user=self.test_user, course_id=self.course.id)
        CourseEnrollmentFactory.create(user=self.test_user2, course_id=self.course.id)
        CourseEnrollmentFactory.create(user=self.test_user, course_id=self.second_course.id)

        organization = self.setup_test_organization()
        test_uri = '{}{}/'.format(self.base_organizations_uri, organization['id'])
        users_uri = '{}users/'.format(test_uri)
        data = {"id": self.test_user.id}
        response = self.do_post(users_uri, data)
        self.assertEqual(response.status_code, 201)

        data = {"id": self.test_user2.id}
        response = self.do_post(users_uri, data)
        self.assertEqual(response.status_code, 201)
        response = self.do_get('{}{}'.format(users_uri, '?include_course_counts=True'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['id'], self.test_user.id)
        self.assertEqual(response.data[0]['course_count'], 2)
        self.assertEqual(response.data[1]['id'], self.test_user2.id)
        self.assertEqual(response.data[1]['course_count'], 1)

    def test_organizations_users_get_with_grades(self):
        # Create 4 users
        user_course = 4
        users_completed = 2
        users = [UserFactory.create(username="testuser" + str(__), profile='test') for __ in xrange(user_course)]
        for i, user in enumerate(users):
            CourseEnrollmentFactory.create(user=user, course_id=self.course.id)
            grades = (0.75, 0.85)
            # mark 3 users as who completed course and 1 who did not
            if i < users_completed:
                grades = (0.90, 0.91)
            StudentGradebook.objects.create(user=user, course_id=self.course.id, grade=grades[0],
                                            proforma_grade=grades[1])

        organization = self.setup_test_organization()
        test_uri = '{}{}/'.format(self.base_organizations_uri, organization['id'])
        users_uri = '{}users/'.format(test_uri)
        for user in users:
            data = {"id": user.id}
            response = self.do_post(users_uri, data)
            self.assertEqual(response.status_code, 201)

        params = {'course_id': unicode(self.course.id), 'include_grades':True}
        response = self.do_get(users_uri, query_parameters=params)
        self.assertEqual(response.status_code, 200)
        complete_count = len([user for user in response.data if user['complete_status']])
        self.assertEqual(complete_count, users_completed)
        grade_sum = sum([user['grade'] for user in response.data])
        proforma_grade_sum = sum([user['proforma_grade'] for user in response.data])
        self.assertEqual(grade_sum, 0.75 + 0.75 + 0.9 + 0.9)
        self.assertEqual(proforma_grade_sum, 0.85 + 0.85 + 0.91 + 0.91)

    def test_organizations_users_delete(self):
        """
        Tests organization user link removal API works as expected if given user ids are valid
        """
        org_users = [self.test_user.id, self.test_user2.id]
        organization = self.setup_test_organization(org_data={'users': org_users})
        test_uri = '{}{}/'.format(self.base_organizations_uri, organization['id'])
        users_uri = '{}users/'.format(test_uri)
        data = {"users": "{user_id1},{user_id2}".format(user_id1=self.test_user.id, user_id2=self.test_user2.id)}
        response = self.do_delete(users_uri, data=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['detail'], _("2 user(s) removed from organization"))
        response = self.do_get("{}?view=ids".format(users_uri))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        # users in User model are not deleted
        self.assertEqual(len(org_users), User.objects.filter(id__in=org_users).count())

    def test_organizations_single_user_delete(self):
        """
        Tests organization user link removal API works as expected if single user needs to be deleted
        """
        org_users = [self.test_user.id, self.test_user2.id]
        organization = self.setup_test_organization(org_data={'users': org_users})
        test_uri = '{}{}/'.format(self.base_organizations_uri, organization['id'])
        users_uri = '{}users/'.format(test_uri)
        data = {"users": "{user_id1}".format(user_id1=self.test_user.id)}
        response = self.do_delete(users_uri, data=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['detail'], _("1 user(s) removed from organization"))
        response = self.do_get("{}?view=ids".format(users_uri))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        # users in User model are not deleted
        self.assertEqual(len(org_users), User.objects.filter(id__in=org_users).count())

    def test_organizations_users_delete_invalid(self):
        """
        Tests organization user link removal API returns bad request response if given user ids are not valid
        """
        organization = self.setup_test_organization()
        test_uri = '{}{}/'.format(self.base_organizations_uri, organization['id'])
        users_uri = '{}users/'.format(test_uri)
        data = {"users": 'invalid'}
        response = self.do_delete(users_uri, data=data)
        self.assertEqual(response.status_code, 400)

        data = {"users": 'invalid,112323333329'}
        response = self.do_delete(users_uri, data=data)
        self.assertEqual(response.status_code, 400)

        data = {"users": '112323333329'}
        response = self.do_delete(users_uri, data=data)
        self.assertEqual(response.status_code, 204)

    def test_organizations_users_delete_non_existing(self):
        """
        Tests organization user link removal API with non existing user
        """
        organization = self.setup_test_organization()
        test_uri = '{}{}/'.format(self.base_organizations_uri, organization['id'])
        users_uri = '{}users/'.format(test_uri)
        data = {"users": '112323333329'}
        response = self.do_delete(users_uri, data=data)
        self.assertEqual(response.status_code, 204)

    def test_organizations_users_delete_without_param(self):
        """
        Tests organization user link removal API without users param
        """
        organization = self.setup_test_organization()
        test_uri = '{}{}/'.format(self.base_organizations_uri, organization['id'])
        users_uri = '{}users/'.format(test_uri)
        response = self.do_delete(users_uri, data={})
        self.assertEqual(response.status_code, 400)

    def test_organizations_metrics_get(self):
        users = []
        for i in xrange(1, 6):
            data = {
                'email': 'test{}@example.com'.format(i),
                'username': 'test_user{}'.format(i),
                'password': 'test_pass',
                'first_name': 'John{}'.format(i),
                'last_name': 'Doe{}'.format(i),
                'city': 'Boston',
            }
            response = self.do_post(self.base_users_uri, data)
            self.assertEqual(response.status_code, 201)
            user_id = response.data['id']
            user = User.objects.get(pk=user_id)
            users.append(user_id)
            CourseEnrollmentFactory.create(user=user, course_id=self.course.id)
            if i < 2:
                StudentGradebook.objects.create(user=user, course_id=self.course.id, grade=0.75, proforma_grade=0.85)
            elif i < 4:
                StudentGradebook.objects.create(user=user, course_id=self.course.id, grade=0.82, proforma_grade=0.82)
            else:
                StudentGradebook.objects.create(user=user, course_id=self.course.id, grade=0.90, proforma_grade=0.91)

        organization = self.setup_test_organization(org_data={'users': users})
        test_uri = '{}{}/'.format(self.base_organizations_uri, organization['id'])
        metrics_uri = '{}metrics/'.format(test_uri)
        response = self.do_get(metrics_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['users_grade_average'], 0.838)
        self.assertEqual(response.data['users_grade_complete_count'], 4)

    @ddt.data(ModuleStoreEnum.Type.split, ModuleStoreEnum.Type.mongo)
    def test_organizations_metrics_get_courses_filter(self, store):
        users = []
        course1 = CourseFactory.create(display_name="COURSE1", org="CRS1", run="RUN1", default_store=store)
        course2 = CourseFactory.create(display_name="COURSE2", org="CRS2", run="RUN2", default_store=store)
        course3 = CourseFactory.create(display_name="COURSE3", org="CRS3", run="RUN3", default_store=store)

        for i in xrange(1, 12):
            data = {
                'email': 'test{}@example.com'.format(i),
                'username': 'test_user{}'.format(i),
                'password': 'test_pass',
                'first_name': 'John{}'.format(i),
                'last_name': 'Doe{}'.format(i),
                'city': 'Boston',
            }
            response = self.do_post(self.base_users_uri, data)
            self.assertEqual(response.status_code, 201)
            user_id = response.data['id']
            user = User.objects.get(pk=user_id)
            users.append(user_id)

            # first six users are enrolled in course1, course2 and course3
            if i < 7:
                CourseEnrollmentFactory.create(user=user, course_id=course1.id)
                StudentGradebook.objects.create(user=user, grade=0.75, proforma_grade=0.85, course_id=course1.id)
                CourseEnrollmentFactory.create(user=user, course_id=course2.id)
                StudentGradebook.objects.create(user=user, grade=0.82, proforma_grade=0.82, course_id=course2.id)
                CourseEnrollmentFactory.create(user=user, course_id=course3.id)
                StudentGradebook.objects.create(user=user, grade=0.72, proforma_grade=0.78, course_id=course3.id)
            elif i < 9:
                CourseEnrollmentFactory.create(user=user, course_id=course1.id)
                StudentGradebook.objects.create(user=user, grade=0.54, proforma_grade=0.67, course_id=course1.id)
            elif i < 11:
                CourseEnrollmentFactory.create(user=user, course_id=course2.id)
                StudentGradebook.objects.create(user=user, grade=0.90, proforma_grade=0.91, course_id=course2.id)
            else:
                # Not started student - should be considered incomplete
                CourseEnrollmentFactory.create(user=user, course_id=course2.id)
                StudentGradebook.objects.create(user=user, grade=0.00, proforma_grade=0.00, course_id=course2.id)

        organization = self.setup_test_organization(org_data={'users': users})
        test_uri = '{}{}/'.format(self.base_organizations_uri, organization['id'])
        metrics_uri = '{}metrics/'.format(test_uri)
        response = self.do_get(metrics_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['users_grade_complete_count'], 8)
        self.assertEqual(response.data['users_grade_average'], 0.504)

        courses = {'courses': unicode(course1.id)}
        filtered_metrics_uri = '{}?{}'.format(metrics_uri, urlencode(courses))
        response = self.do_get(filtered_metrics_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['users_grade_complete_count'], 0)
        self.assertEqual(response.data['users_grade_average'], 0.698)

        courses = {'courses': unicode(course2.id)}
        filtered_metrics_uri = '{}?{}'.format(metrics_uri, urlencode(courses))
        response = self.do_get(filtered_metrics_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['users_grade_complete_count'], 8)
        self.assertEqual(response.data['users_grade_average'], 0.747)

        courses = {'courses': '{},{}'.format(course1.id, course2.id)}
        filtered_metrics_uri = '{}?{}'.format(metrics_uri, urlencode(courses))
        response = self.do_get(filtered_metrics_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['users_grade_complete_count'], 8)
        self.assertEqual(response.data['users_grade_average'], 0.559)

        courses = {'courses': '{}'.format(self.course.id)}
        filtered_metrics_uri = '{}?{}'.format(metrics_uri, urlencode(courses))
        response = self.do_get(filtered_metrics_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['users_grade_complete_count'], 0)
        self.assertEqual(response.data['users_grade_average'], 0)

    def test_organizations_groups_users_get(self):
        organization = self.setup_test_organization()
        organization_two = self.setup_test_organization()
        group = GroupFactory.create()
        users = UserFactory.create_batch(5)
        group.organizations.add(organization['id'])
        group.organizations.add(organization_two['id'])
        for user in users:
            OrganizationGroupUser.objects.create(organization_id=organization['id'], group=group, user=user)

        # test when organization group have no users
        test_uri = '{}{}/groups/{}/users'.format(self.base_organizations_uri, organization['id'], 1234)
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        # test when organization group have users
        test_uri = '{}{}/groups/{}/users'.format(self.base_organizations_uri, organization['id'], group.id)
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), len(users))
        for i, user in enumerate(response.data):
            self.assertEqual(user['id'], users[i].id)

        # test organization_two group users
        test_uri = '{}{}/groups/{}/users'.format(self.base_organizations_uri, organization_two['id'], group.id)
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_organizations_groups_users_post(self):
        organization = self.setup_test_organization()
        organization_two = self.setup_test_organization()
        groups = GroupFactory.create_batch(2)
        users = UserFactory.create_batch(5)
        groups[0].organizations.add(organization['id'])
        groups[0].organizations.add(organization_two['id'])

        # test for invalid user id
        test_uri = '{}{}/groups/{}/users'.format(self.base_organizations_uri, organization['id'], groups[1].id)
        data = {
            'users': '1,qwerty'
        }
        response = self.do_delete(test_uri, data)
        self.assertEqual(response.status_code, 400)

        # group does not belong to organization
        test_uri = '{}{}/groups/{}/users'.format(self.base_organizations_uri, organization['id'], groups[1].id)
        data = {
            'users': ','.join([str(user.id) for user in users])
        }
        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 404)
        expected_response = "Group {} does not belong to organization {}".format(groups[1].id, organization['id'])
        self.assertEqual(response.data['detail'], expected_response)

        # group belong to organization but users does not exit
        test_uri = '{}{}/groups/{}/users'.format(self.base_organizations_uri, organization['id'], groups[0].id)
        data = {
            'users': '1234,9912,9800'
        }
        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 204)
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        # group belong to organization and users exist
        data = {
            'users': ','.join([str(user.id) for user in users])
        }
        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 201)
        user_ids = ', '.join([str(user.id) for user in users])
        expected_response = "user id(s) {} added to organization {}'s group {}".format(user_ids,
                                                                                       organization['id'],
                                                                                       groups[0].id)
        self.assertEqual(response.data['detail'], expected_response)
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), len(users))
        for i, user in enumerate(response.data):
            self.assertEqual(user['id'], users[i].id)
        # test users were not added to organization_two group relation
        test_uri = '{}{}/groups/{}/users'.format(self.base_organizations_uri, organization_two['id'], groups[0].id)
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_organizations_groups_users_delete(self):
        organization = self.setup_test_organization()
        organization_two = self.setup_test_organization()
        groups = GroupFactory.create_batch(2)
        users = UserFactory.create_batch(5)
        groups[0].organizations.add(organization['id'])
        groups[0].organizations.add(organization_two['id'])
        for user in users:
            OrganizationGroupUser.objects.create(organization_id=organization['id'], group=groups[0], user=user)
            OrganizationGroupUser.objects.create(organization_id=organization_two['id'], group=groups[0], user=user)

        # test for invalid user id
        test_uri = '{}{}/groups/{}/users'.format(self.base_organizations_uri, organization['id'], groups[1].id)
        data = {
            'users': '1,qwerty'
        }
        response = self.do_delete(test_uri, data)
        self.assertEqual(response.status_code, 400)

        # group does not belong to organization
        test_uri = '{}{}/groups/{}/users'.format(self.base_organizations_uri, organization['id'], groups[1].id)
        data = {
            'users': ','.join([str(user.id) for user in users])
        }
        response = self.do_delete(test_uri, data)
        self.assertEqual(response.status_code, 404)
        expected_response = "Group {} does not belong to organization {}".format(groups[1].id, organization['id'])
        self.assertEqual(response.data['detail'], expected_response)

        # group belong to organization but users does not exit
        test_uri = '{}{}/groups/{}/users'.format(self.base_organizations_uri, organization['id'], groups[0].id)
        data = {
            'users': '1234,9912,9800'
        }
        response = self.do_delete(test_uri, data)
        self.assertEqual(response.status_code, 204)

        # organization group user relationship exists for users
        data = {
            'users': ','.join([str(user.id) for user in users])
        }
        response = self.do_delete(test_uri, data)
        self.assertEqual(response.status_code, 200)
        user_ids = ', '.join([str(user.id) for user in users])
        expected_response = "user id(s) {} removed from organization {}'s group {}".format(user_ids,
                                                                                           organization['id'],
                                                                                           groups[0].id)
        self.assertEqual(response.data['detail'], expected_response)
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)
        # test users were not removed from organization_two group relation
        test_uri = '{}{}/groups/{}/users'.format(self.base_organizations_uri, organization_two['id'], groups[0].id)
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), len(users))


@ddt.ddt
class OrganizationsAttributesApiTests(ModuleStoreTestCase, APIClientMixin):
    """ Test suite for Organization Attributes API views """

    MODULESTORE = TEST_DATA_SPLIT_MODULESTORE

    def setUp(self):
        super(OrganizationsAttributesApiTests, self).setUp()
        self.test_server_prefix = 'https://testserver'
        self.base_organizations_uri = '/api/server/organizations/'
        self.test_organization_name = str(uuid.uuid4())
        self.test_organization_display_name = 'Test Org'
        self.test_organization_contact_name = 'John Org'
        self.test_organization_contact_email = 'john@test.org'
        self.test_organization_contact_phone = '+1 332 232 24234'
        self.test_organization_logo_url = 'org_logo.jpg'

        self.course = CourseFactory.create()

        self.client = Client()
        self.user = UserFactory.create(username='test', email='test@edx.org', password='test_password')
        self.client.login(username=self.user.username, password='test_password')

        cache.clear()

    def setup_test_organization(self, org_data=None):
        """
        Creates a new organization with given org_data
        if org_data is not present it would create organization with test values
        :param org_data: Dictionary witch each item represents organization attribute
        :return: newly created organization
        """
        org_data = org_data if org_data else {}
        data = {
            'name': org_data.get('name', self.test_organization_name),
            'display_name': org_data.get('display_name', self.test_organization_display_name),
            'contact_name': org_data.get('contact_name', self.test_organization_contact_name),
            'contact_email': org_data.get('contact_email', self.test_organization_contact_email),
            'contact_phone': org_data.get('contact_phone', self.test_organization_contact_phone),
            'logo_url': org_data.get('logo_url', self.test_organization_logo_url),
            'users': org_data.get('users', []),
            'groups': org_data.get('groups', [])
        }
        response = self.do_post(self.base_organizations_uri, data)
        self.assertEqual(response.status_code, 201)
        return response.data

    def test_organizations_attributes_add(self):
        organization = self.setup_test_organization()

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'name': 'phone'
        }
        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 201)

    def test_organizations_attributes_add_with_already_exists_field(self):
        organization = self.setup_test_organization()

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'name': 'phone'
        }
        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 201)

        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 409)

    def test_organizations_attributes_get(self):
        organization = self.setup_test_organization()

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'name': 'phone'
        }
        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 201)

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)

        expected_response = [
            {
                'order': 1,
                'label': 'phone',
                'key': 'phone',
            }
        ]

        self.assertEqual(response.data, expected_response)

    def test_organizations_attributes_update(self):
        organization = self.setup_test_organization()

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'name': 'phone'
        }
        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 201)

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'name': 'address'
        }
        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 201)

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'name': 'cell',
            'key': 'phone'
        }
        response = self.do_put(test_uri, data)
        self.assertEqual(response.status_code, 200)

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)

        expected_response = [
            {
                'order': 1,
                'label': 'cell',
                'key': 'phone',
            },
            {
                'order': 2,
                'label': 'address',
                'key': 'address',
            }
        ]

        self.assertEqual(response.data, expected_response)

    def test_organizations_attributes_update_with_existing_name(self):
        organization = self.setup_test_organization()

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'name': 'phone'
        }
        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 201)

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'name': 'address'
        }
        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 201)

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'name': 'phone',
            'key': 'address'
        }
        response = self.do_put(test_uri, data)
        self.assertEqual(response.status_code, 409)

    def test_organizations_attributes_update_with_non_existing_key(self):
        organization = self.setup_test_organization()

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'name': 'phone'
        }
        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 201)

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'name': 'address'
        }
        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 201)

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'name': 'mobile',
            'key': 'mobile'
        }
        response = self.do_put(test_uri, data)
        self.assertEqual(response.status_code, 404)

    def test_organizations_attributes_delete_with_key(self):
        organization = self.setup_test_organization()

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'name': 'phone'
        }
        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 201)

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'name': 'address'
        }
        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 201)

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'key': 'address'
        }
        response = self.do_delete(test_uri, data)
        self.assertEqual(response.status_code, 200)

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        response = self.do_get(test_uri)
        self.assertEqual(response.status_code, 200)

        expected_response = [
            {
                "order": 1,
                "key": "phone",
                "label": "phone"
            }
        ]

        self.assertEqual(response.data, expected_response)

    def test_organizations_attributes_delete_with_non_existing_key(self):
        organization = self.setup_test_organization()

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'name': 'phone'
        }
        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 201)

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'name': 'address'
        }
        response = self.do_post(test_uri, data)
        self.assertEqual(response.status_code, 201)

        test_uri = '{}{}/attributes'.format(self.base_organizations_uri, organization['id'])
        data = {
            'key': 'mobile'
        }
        response = self.do_delete(test_uri, data)
        self.assertEqual(response.status_code, 404)


