import django_filters
from django_filters import rest_framework as filters
from .models import StudentProfile, TeacherProfile, AdminProfile


class StudentProfileFilter(django_filters.FilterSet):
    """
    Filter for StudentProfile model.
    Allows filtering by department, year, roll number, and user email.
    """
    email = django_filters.CharFilter(
        field_name='user__email',
        lookup_expr='icontains',
        label='User email (contains)'
    )
    roll_number = django_filters.CharFilter(
        field_name='roll_number',
        lookup_expr='icontains',
        label='Roll number (contains)'
    )
    department = django_filters.CharFilter(
        field_name='department',
        lookup_expr='icontains',
        label='Department (contains)'
    )
    year = django_filters.NumberFilter(
        field_name='year',
        label='Year'
    )
    year_range = django_filters.RangeFilter(
        field_name='year',
        label='Year range (min,max)'
    )
    first_name = django_filters.CharFilter(
        field_name='first_name',
        lookup_expr='icontains',
        label='First name (contains)'
    )
    last_name = django_filters.CharFilter(
        field_name='last_name',
        lookup_expr='icontains',
        label='Last name (contains)'
    )
    is_active = django_filters.BooleanFilter(
        field_name='user__is_active',
        label='Is active'
    )

    class Meta:
        model = StudentProfile
        fields = ['department', 'year', 'roll_number', 'email']


class TeacherProfileFilter(django_filters.FilterSet):
    """
    Filter for TeacherProfile model.
    Allows filtering by department, employee ID, and user email.
    """
    email = django_filters.CharFilter(
        field_name='user__email',
        lookup_expr='icontains',
        label='User email (contains)'
    )
    employee_id = django_filters.CharFilter(
        field_name='employee_id',
        lookup_expr='icontains',
        label='Employee ID (contains)'
    )
    department = django_filters.CharFilter(
        field_name='department',
        lookup_expr='icontains',
        label='Department (contains)'
    )
    first_name = django_filters.CharFilter(
        field_name='first_name',
        lookup_expr='icontains',
        label='First name (contains)'
    )
    last_name = django_filters.CharFilter(
        field_name='last_name',
        lookup_expr='icontains',
        label='Last name (contains)'
    )
    is_active = django_filters.BooleanFilter(
        field_name='user__is_active',
        label='Is active'
    )

    class Meta:
        model = TeacherProfile
        fields = ['department', 'employee_id', 'email']


class AdminProfileFilter(django_filters.FilterSet):
    """
    Filter for AdminProfile model.
    Allows filtering by user email.
    """
    email = django_filters.CharFilter(
        field_name='user__email',
        lookup_expr='icontains',
        label='User email (contains)'
    )
    first_name = django_filters.CharFilter(
        field_name='first_name',
        lookup_expr='icontains',
        label='First name (contains)'
    )
    last_name = django_filters.CharFilter(
        field_name='last_name',
        lookup_expr='icontains',
        label='Last name (contains)'
    )
    is_active = django_filters.BooleanFilter(
        field_name='user__is_active',
        label='Is active'
    )

    class Meta:
        model = AdminProfile
        fields = ['email']
