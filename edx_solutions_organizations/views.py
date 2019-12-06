# pylint: disable=C0103

""" ORGANIZATIONS API VIEWS """
import json
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Sum, F, Count, Prefetch
from django.db import IntegrityError
from django.utils.translation import ugettext as _
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.user_api.models import UserPreference

from rest_framework import status
from rest_framework.decorators import detail_route, list_route
from rest_framework.response import Response
from rest_framework.exceptions import ParseError

from edx_solutions_api_integration.courseware_access import get_course_key, get_course_descriptor
from edx_solutions_api_integration.courses.serializers import OrganizationCourseSerializer
from edx_solutions_api_integration.users.serializers import SimpleUserSerializer
from edx_solutions_api_integration.groups.serializers import GroupSerializer
from edx_solutions_api_integration.permissions import (
    MobileAPIView,
    SecureListAPIView,
    SecurePaginatedModelViewSet,
)
from edx_solutions_api_integration.utils import (
    str2bool,
    get_aggregate_exclusion_user_ids,
)
from gradebook.models import StudentGradebook
from student.models import CourseEnrollment, CourseAccessRole
from student.roles import (
    CourseAssistantRole,
    CourseInstructorRole,
    CourseObserverRole,
    CourseStaffRole,
)

from edx_solutions_organizations.models import OrganizationUsersAttributes
from edx_solutions_organizations.serializers import OrganizationAttributesSerializer
from edx_solutions_organizations.utils import generate_key_for_field, is_key_exists, is_label_exists, \
    generate_random_key_for_field
from .serializers import OrganizationSerializer, BasicOrganizationSerializer, OrganizationWithCourseCountSerializer
from .models import Organization, OrganizationGroupUser


class OrganizationsViewSet(SecurePaginatedModelViewSet):
    """
    Django Rest Framework ViewSet for the Organization model.
    """
    serializer_class = OrganizationSerializer
    queryset = Organization.objects.all()

    def list(self, request, *args, **kwargs):
        self.serializer_class = OrganizationWithCourseCountSerializer
        queryset = self.get_queryset()

        ids = request.query_params.get('ids', None)
        if ids:
            ids = [int(id) for id in ids.split(',')]
            queryset = queryset.filter(id__in=ids)

        display_name = request.query_params.get('display_name', None)
        if display_name is not None:
            queryset = queryset.filter(display_name=display_name)

        self.queryset = queryset.annotate(
            number_of_courses=Count('users__courseenrollment__course_id', distinct=True)
        ).annotate(
            number_of_participants=Count('users', distinct=True)
        )

        return super(OrganizationsViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        self.serializer_class = BasicOrganizationSerializer
        return super(OrganizationsViewSet, self).retrieve(request, *args, **kwargs)

    @detail_route(methods=['get', ])
    def metrics(self, request, pk):
        """
        Provide statistical information for the specified Organization
        """
        response_data = {}
        grade_avg = 0
        grade_complete_match_range = getattr(settings, 'GRADEBOOK_GRADE_COMPLETE_PROFORMA_MATCH_RANGE', 0.01)
        org_user_grades = StudentGradebook.objects.filter(user__organizations=pk, user__is_active=True)
        courses_filter = request.query_params.get('courses', None)
        courses = []
        exclude_users = set()
        if courses_filter:
            upper_bound = getattr(settings, 'API_LOOKUP_UPPER_BOUND', 100)
            courses_filter = courses_filter.split(",")[:upper_bound]
            for course_string in courses_filter:
                courses.append(get_course_key(course_string))

            # fill exclude users
            for course_key in courses:
                exclude_users.union(get_aggregate_exclusion_user_ids(course_key))

            org_user_grades = org_user_grades.filter(course_id__in=courses).exclude(user_id__in=exclude_users)

        users_grade_sum = org_user_grades.aggregate(Sum('grade'))
        if users_grade_sum['grade__sum']:
            users_enrolled_qs = CourseEnrollment.objects.filter(user__is_active=True, is_active=True,
                                                                user__organizations=pk)\
                .exclude(user_id__in=exclude_users)
            if courses:
                users_enrolled_qs = users_enrolled_qs.filter(course_id__in=courses)
            users_enrolled = users_enrolled_qs.aggregate(Count('user', distinct=True))
            total_users = users_enrolled['user__count']
            if total_users:
                # in order to compute avg across organization we need course of courses org has
                total_courses_in_org = len(courses)
                if not courses:
                    org_courses = users_enrolled_qs.aggregate(Count('course_id', distinct=True))
                    total_courses_in_org = org_courses['course_id__count']
                grade_avg = float('{0:.3f}'.format(
                    float(users_grade_sum['grade__sum']) / total_users / total_courses_in_org
                ))
        response_data['users_grade_average'] = grade_avg

        users_grade_complete_count = org_user_grades\
            .filter(proforma_grade__lte=F('grade') + grade_complete_match_range, proforma_grade__gt=0)\
            .aggregate(Count('user', distinct=True))
        response_data['users_grade_complete_count'] = users_grade_complete_count['user__count'] or 0

        return Response(response_data, status=status.HTTP_200_OK)

    @detail_route(methods=['get', 'post', 'delete'])
    def users(self, request, pk):
        """
        - URI: ```/api/organizations/{org_id}/users/```
        - GET: Returns users in an organization
            * course_id parameter should filter user by course
            * include_course_counts parameter should be `true` to get user's enrollment count
            * include_grades parameter should be `true` to get user's grades
            * for the course given in the course_id parameter
            * view parameter can be used to get a particular data .i.e. view=ids to
            * get list of user ids
        - POST: Adds a User to an Organization
        - DELETE: Removes the user(s) given in the `users` param from an Organization.
        """
        if request.method == 'GET':
            include_course_counts = request.query_params.get('include_course_counts', None)
            include_grades = request.query_params.get('include_grades', None)
            course_id = request.query_params.get('course_id', None)
            view = request.query_params.get('view', None)
            grade_complete_match_range = getattr(settings, 'GRADEBOOK_GRADE_COMPLETE_PROFORMA_MATCH_RANGE', 0.01)
            course_key = None
            if course_id:
                course_key = get_course_key(course_id)

            users = User.objects.filter(organizations=pk)

            if course_key:
                users = users.filter(courseenrollment__course_id__exact=course_key,
                                     courseenrollment__is_active=True)

                if str2bool(include_grades):
                    users = users.prefetch_related(
                        Prefetch('studentgradebook_set', queryset=StudentGradebook.objects.filter(course_id=course_key))
                    )

            if str2bool(include_course_counts):
                enrollments = CourseEnrollment.objects.filter(user__in=users).values('user').order_by().annotate(total=Count('user'))
                enrollments_by_user = {}
                for enrollment in enrollments:
                    enrollments_by_user[enrollment['user']] = enrollment['total']

            # if we only need ids of users in organization return now
            if view == 'ids':
                user_ids = users.values_list('id', flat=True)
                return Response(user_ids)

            response_data = []
            if users:
                for user in users:
                    serializer = SimpleUserSerializer(user)
                    user_data = serializer.data

                    if str2bool(include_course_counts):
                        user_data['course_count'] = enrollments_by_user.get(user.id, 0)

                    if str2bool(include_grades) and course_key:
                        user_grades = {'grade': 0, 'proforma_grade': 0, 'complete_status': False}
                        gradebook = user.studentgradebook_set.all()
                        if gradebook:
                            user_grades['grade'] = gradebook[0].grade
                            user_grades['proforma_grade'] = gradebook[0].proforma_grade
                            user_grades['complete_status'] = True if 0 < gradebook[0].proforma_grade <= \
                                gradebook[0].grade + grade_complete_match_range else False
                        user_data.update(user_grades)

                    response_data.append(user_data)
            return Response(response_data, status=status.HTTP_200_OK)
        elif request.method == 'DELETE':
            user_ids = request.data.get('users')
            if not user_ids:
                return Response({"detail": _('users parameter is missing.')}, status.HTTP_400_BAD_REQUEST)
            try:
                user_ids = [int(user_id) for user_id in filter(None, user_ids.split(','))]
            except (ValueError, AttributeError):
                return Response({
                    "detail": _('users parameter must be comma separated list of integers.')
                }, status.HTTP_400_BAD_REQUEST)

            organization = self.get_object()
            users_to_be_deleted = organization.users.filter(id__in=user_ids)
            total_users = len(users_to_be_deleted)
            if total_users > 0:
                organization.users.remove(*users_to_be_deleted)
                return Response({
                    "detail": _("{users_removed} user(s) removed from organization").format(users_removed=total_users)
                }, status=status.HTTP_200_OK)
            else:
                return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            user_id = request.data.get('id')
            try:
                user = User.objects.get(id=user_id)
            except ObjectDoesNotExist:
                message = 'User {} does not exist'.format(user_id)
                return Response({"detail": message}, status.HTTP_400_BAD_REQUEST)
            organization = self.get_object()
            organization.users.add(user)
            organization.save()
            return Response({}, status=status.HTTP_201_CREATED)

    @detail_route(methods=['get', 'post'])
    def groups(self, request, pk):
        """
        Add a Group to a organization or retrieve list of groups in organization
        - GET: Returns groups in an organization
            * view parameter can be used to get a particular data .i.e. view=ids to
            * get list of group ids

        """
        if request.method == 'GET':
            group_type = request.query_params.get('type', None)
            view = request.query_params.get('view', None)
            groups = Group.objects.filter(organizations=pk)

            if group_type:
                groups = groups.filter(groupprofile__group_type=group_type)

            # if we only need ids of groups in organization return now
            if view == 'ids':
                group_ids = groups.values_list('id', flat=True)
                return Response(group_ids)

            response_data = []
            if groups:
                for group in groups:
                    serializer = GroupSerializer(group, context={'request': request})
                    response_data.append(serializer.data)  # pylint: disable=E1101
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            group_id = request.data.get('id')
            try:
                group = Group.objects.get(id=group_id)
            except ObjectDoesNotExist:
                message = 'Group {} does not exist'.format(group_id)
                return Response({"detail": message}, status.HTTP_400_BAD_REQUEST)
            organization = self.get_object()
            organization.groups.add(group)
            organization.save()
            return Response({}, status=status.HTTP_201_CREATED)

    @detail_route(methods=['get', ])
    def courses(self, request, pk):  # pylint: disable=W0613
        """
        Returns list of courses in an organization
        """
        exclude_admins = str2bool(request.query_params.get('exclude_admins'))
        organization = self.get_object()
        organization_course_ids = []
        roles_to_exclude = []
        if exclude_admins:
            organization_course_ids = CourseEnrollment.objects\
                .filter(user__organizations=organization, is_active=True)\
                .order_by('course_id').distinct().values_list('course_id', flat=True)
            organization_course_ids = map(get_course_key, filter(None, organization_course_ids))
            roles_to_exclude = [CourseInstructorRole.ROLE, CourseStaffRole.ROLE, CourseObserverRole.ROLE, CourseAssistantRole.ROLE]

        enrollment_qs = CourseEnrollment.objects\
            .filter(user__organizations=organization, is_active=True)\
            .exclude(
                user_id__in=CourseAccessRole.objects.filter(
                    course_id__in=organization_course_ids, role__in=roles_to_exclude
                ).values_list('user_id', flat=True)
            ).values_list('course_id', 'user_id')

        enrollments = {}
        course_ids = []
        for (course_id, user_id) in enrollment_qs:
            enrollments.setdefault(course_id, []).append(user_id)
            if course_id not in course_ids:
                course_ids.append(course_id)

        course_keys = map(get_course_key, filter(None, course_ids))
        if request.query_params.get('mobile_available'):
            mobile_available = str2bool(request.query_params.get('mobile_available'))
            courses = CourseOverview.objects.filter(id__in=course_keys, mobile_available=mobile_available)
        else:
            courses = CourseOverview.objects.filter(id__in=course_keys)

        serializer = OrganizationCourseSerializer(courses, many=True, context={'request': request, 'enrollments': enrollments})
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrganizationsGroupsUsersList(SecureListAPIView):
    """
    OrganizationsGroupsUsersList returns a collection of users for a organization group.

    **Example Request**

        GET /api/organizations/{organization_id}/groups/{group_id}/users

        POST /api/organizations/{organization_id}/groups/{group_id}/users

        DELETE /api/organizations/{organization_id}/groups/{group_id}/users

    ### The OrganizationsGroupsUsersList view allows clients to retrieve a list of users for a given organization group
    - URI: ```/api/organizations/{organization_id}/groups/{group_id}/users```
    - GET: Returns a JSON representation (array) of the set of User entities
    - POST: Creates a new relationship between the provided User, Group and Organization
        * users: __required__, The identifier for the User with which we're establishing relationship
    - POST Example:

            {
                "users" : 1,2,3,4,5
            }

    - DELETE: Deletes a relationship between the provided User, Group and Organization
        * users: __required__, The identifier for the User for which we're removing relationship
    - DELETE Example:

            {
                "users" : 1,2,3,4,5
            }
    """

    model = OrganizationGroupUser

    def get(self, request, organization_id, group_id):  # pylint: disable=W0221
        """
        GET /api/organizations/{organization_id}/groups/{group_id}/users
        """
        queryset = User.objects.filter(organizationgroupuser__group_id=group_id,
                                       organizationgroupuser__organization_id=organization_id)

        serializer = SimpleUserSerializer(queryset, many=True)

        return Response(serializer.data, status.HTTP_200_OK)

    def post(self, request, organization_id, group_id):
        """
        GET /api/organizations/{organization_id}/groups/{group_id}/users
        """
        user_ids = request.data.get('users')
        try:
            user_ids = map(int, filter(None, user_ids.split(',')))
        except Exception:
            raise ParseError("Invalid user id value")

        try:
            group = Group.objects.get(id=group_id, organizations=organization_id)
        except ObjectDoesNotExist:
            return Response({
                "detail": 'Group {} does not belong to organization {}'.format(group_id, organization_id)
            }, status.HTTP_404_NOT_FOUND)

        users_added = []
        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                OrganizationGroupUser.objects.create(organization_id=organization_id, group=group, user=user)
            except (ObjectDoesNotExist, IntegrityError):
                continue

            users_added.append(str(user_id))

        if len(users_added) > 0:
            return Response({
                "detail": "user id(s) {users_added} added to organization {org_id}'s group {group_id}"
                          .format(users_added=', '.join(users_added), org_id=organization_id, group_id=group_id)
            }, status=status.HTTP_201_CREATED)
        else:
            return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request, organization_id, group_id):
        """
        DELETE /api/organizations/{organization_id}/groups/{group_id}/users
        """
        user_ids = request.data.get('users')
        try:
            user_ids = map(int, filter(None, user_ids.split(',')))
        except Exception:
            raise ParseError("Invalid user id value")

        try:
            group = Group.objects.get(id=group_id, organizations=organization_id)
        except ObjectDoesNotExist:
            return Response({
                "detail": 'Group {} does not belong to organization {}'.format(group_id, organization_id)
            }, status.HTTP_404_NOT_FOUND)

        organization_group_users_to_delete = OrganizationGroupUser.objects.filter(organization_id=organization_id,
                                                                                  user_id__in=user_ids,
                                                                                  group=group)
        org_group_user_ids = [str(org_group_user.user_id) for org_group_user in organization_group_users_to_delete]
        organization_group_users_to_delete.delete()

        if len(org_group_user_ids) > 0:
            org_group_user_ids = ', '.join(org_group_user_ids)
            message = "user id(s) {org_group_user_ids} removed from organization {org_id}'s group {group_id}"\
                      .format(org_group_user_ids=org_group_user_ids, org_id=organization_id, group_id=group_id)
            return Response({
                "detail": message
            }, status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationAttributesView(MobileAPIView):
    """
    **Use Case**

        Attributes of organization.

    **Example Requests**

        GET /api/organizations/{organization_id}/attributes
        POST /api/organizations/{organization_id}/attributes

        **POST Parameters**

        The body of the POST request must include the following parameters.

        * attribute: organizational field,

        "attribute": {
            "key": "Key",
            "name": "Sample Name"
        }

    **Response Values**

        **GET**

        If the request is successful, the request returns an HTTP 200 "OK" response.

        * id: organization id
        * attribute: organizational field

        **POST**

        If the request is successful, the request returns an HTTP 201 "CREATED" response.
    """

    def get(self, request, organization_id):
        """
        GET /api/organizations/{organization_id}/attributes
        """
        try:
            organization = Organization.objects.get(id=organization_id)
        except ObjectDoesNotExist:
            return Response({
                "detail": 'Organization with {}, does not exists.'.format(organization_id)
            }, status.HTTP_404_NOT_FOUND)

        return Response(organization.get_all_attributes(), status.HTTP_200_OK)

    def post(self, request, organization_id):
        """
        POST /api/organizations/{organization_id}/attributes
        """
        name = request.data.get('name')

        try:
            organization = Organization.objects.get(id=organization_id)
        except ObjectDoesNotExist:
            return Response({
                "detail": 'Organization with {}, does not exists.'.format(organization_id)
            }, status.HTTP_404_NOT_FOUND)

        attributes = json.loads(organization.attributes)
        if organization.is_attribute_exists(name):
            return Response({
                "detail": 'Name {} already exists.'.format(name)
            }, status.HTTP_409_CONFLICT)
        order = generate_key_for_field(attributes)
        key = generate_random_key_for_field(name, order)
        attributes[key] = {'label': name, 'order': order, 'is_active': True}
        organization.attributes = json.dumps(attributes)
        organization.save()

        return Response({}, status=status.HTTP_201_CREATED)

    def put(self, request, organization_id):
        """
        PUT /api/organizations/{organization_id}/attributes
        """
        key = request.data.get('key')
        name = request.data.get('name')

        try:
            organization = Organization.objects.get(id=organization_id)
        except ObjectDoesNotExist:
            return Response({
                "detail": 'Organization with {}, does not exists.'.format(organization_id)
            }, status.HTTP_404_NOT_FOUND)

        attributes = json.loads(organization.attributes)

        if not organization.is_key_exists(key):
            return Response({
                "detail": 'Key {} does not exists.'.format(key)
            }, status.HTTP_404_NOT_FOUND)

        if is_label_exists(name, attributes):
            return Response({
                "detail": 'Name {} already exists.'.format(name)
            }, status.HTTP_409_CONFLICT)

        attributes[key]['label'] = name
        organization.attributes = json.dumps(attributes)
        organization.save()

        return Response({}, status=status.HTTP_200_OK)

    def delete(self, request, organization_id):
        """
        DELETE /api/organizations/{organization_id}/attributes
        """
        key = request.data.get('key')

        try:
            organization = Organization.objects.get(id=organization_id)
        except ObjectDoesNotExist:
            return Response({
                "detail": 'Organization with {}, does not exists.'.format(organization_id)
            }, status.HTTP_404_NOT_FOUND)

        attributes = json.loads(organization.attributes)

        if not organization.is_key_exists(key):
            return Response({
                "detail": 'Key {} does not exists.'.format(key)
            }, status.HTTP_404_NOT_FOUND)

        attributes[key]['is_active'] = False
        organization.attributes = json.dumps(attributes)
        organization.save()

        return Response({}, status=status.HTTP_200_OK)
