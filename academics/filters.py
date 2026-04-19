import django_filters
from django_filters import rest_framework as filters
from .models import Subject, Enrollment, ClassSession
from django.db.models import Q


class SubjectFilter(django_filters.FilterSet):
    """
    Filter for Subject model.
    Allows filtering by name, code, department, semester, and teacher.
    """
    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
        label='Subject name (contains)'
    )
    code = django_filters.CharFilter(
        field_name='code',
        lookup_expr='iexact',
        label='Subject code'
    )
    department = django_filters.CharFilter(
        field_name='department',
        lookup_expr='icontains',
        label='Department (contains)'
    )
    semester = django_filters.NumberFilter(
        field_name='semester',
        label='Semester'
    )
    semester_range = django_filters.RangeFilter(
        field_name='semester',
        label='Semester range (min,max)'
    )
    teacher = django_filters.UUIDFilter(
        field_name='teacher__id',
        label='Teacher ID'
    )
    teacher_name = django_filters.CharFilter(
        field_name='teacher__first_name',
        lookup_expr='icontains',
        label='Teacher first name (contains)'
    )

    class Meta:
        model = Subject
        fields = ['name', 'code', 'department', 'semester', 'teacher']


class EnrollmentFilter(django_filters.FilterSet):
    """
    Filter for Enrollment model.
    Allows filtering by student, subject, and enrollment status.
    """
    student = django_filters.UUIDFilter(
        field_name='student__id',
        label='Student ID'
    )
    student_roll_number = django_filters.CharFilter(
        field_name='student__roll_number',
        lookup_expr='icontains',
        label='Student roll number (contains)'
    )
    student_department = django_filters.CharFilter(
        field_name='student__department',
        lookup_expr='icontains',
        label='Student department (contains)'
    )
    student_year = django_filters.NumberFilter(
        field_name='student__year',
        label='Student year'
    )
    subject = django_filters.UUIDFilter(
        field_name='subject__id',
        label='Subject ID'
    )
    subject_code = django_filters.CharFilter(
        field_name='subject__code',
        lookup_expr='iexact',
        label='Subject code'
    )
    subject_name = django_filters.CharFilter(
        field_name='subject__name',
        lookup_expr='icontains',
        label='Subject name (contains)'
    )

    class Meta:
        model = Enrollment
        fields = ['student', 'subject']


class ClassSessionFilter(django_filters.FilterSet):
    """
    Filter for ClassSession model.
    Allows filtering by subject, class name, date range, and time.
    """
    subject = django_filters.UUIDFilter(
        field_name='subject__id',
        label='Subject ID'
    )
    subject_name = django_filters.CharFilter(
        field_name='subject__name',
        lookup_expr='icontains',
        label='Subject name (contains)'
    )
    subject_code = django_filters.CharFilter(
        field_name='subject__code',
        lookup_expr='iexact',
        label='Subject code'
    )
    class_name = django_filters.CharFilter(
        field_name='class_name',
        lookup_expr='icontains',
        label='Class name (contains)'
    )
    date = django_filters.DateFilter(
        field_name='date',
        label='Exact date (YYYY-MM-DD)'
    )
    date_after = django_filters.DateFilter(
        field_name='date',
        lookup_expr='gte',
        label='Date from (YYYY-MM-DD)'
    )
    date_before = django_filters.DateFilter(
        field_name='date',
        lookup_expr='lte',
        label='Date until (YYYY-MM-DD)'
    )
    date_range = django_filters.DateFromToRangeFilter(
        field_name='date',
        label='Date range'
    )
    start_time = django_filters.TimeFilter(
        field_name='start_time',
        label='Start time (HH:MM:SS)'
    )
    end_time = django_filters.TimeFilter(
        field_name='end_time',
        label='End time (HH:MM:SS)'
    )

    class Meta:
        model = ClassSession
        fields = ['subject', 'class_name', 'date']
