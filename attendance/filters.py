import django_filters
from django_filters import rest_framework as filters
from .models import FaceData, FaceEmbedding, Attendance, AttendanceLog


class FaceDataFilter(django_filters.FilterSet):
    """
    Filter for FaceData model.
    Allows filtering by enrollment status and student details.
    """
    student = django_filters.UUIDFilter(
        field_name='student__id',
        label='Student ID'
    )
    student_email = django_filters.CharFilter(
        field_name='student__user__email',
        lookup_expr='icontains',
        label='Student email (contains)'
    )
    student_roll_number = django_filters.CharFilter(
        field_name='student__roll_number',
        lookup_expr='icontains',
        label='Student roll number (contains)'
    )
    is_enrolled = django_filters.BooleanFilter(
        field_name='is_enrolled',
        label='Is enrolled'
    )
    total_photos_registered = django_filters.NumberFilter(
        field_name='total_photos_registered',
        label='Total photos registered'
    )
    total_photos_registered_min = django_filters.NumberFilter(
        field_name='total_photos_registered',
        lookup_expr='gte',
        label='Minimum photos registered'
    )
    total_photos_registered_max = django_filters.NumberFilter(
        field_name='total_photos_registered',
        lookup_expr='lte',
        label='Maximum photos registered'
    )
    registration_confidence = django_filters.NumberFilter(
        field_name='registration_confidence',
        label='Registration confidence (exact)'
    )
    registration_confidence_min = django_filters.NumberFilter(
        field_name='registration_confidence',
        lookup_expr='gte',
        label='Minimum registration confidence'
    )
    registration_confidence_max = django_filters.NumberFilter(
        field_name='registration_confidence',
        lookup_expr='lte',
        label='Maximum registration confidence'
    )

    class Meta:
        model = FaceData
        fields = ['student', 'is_enrolled']


class FaceEmbeddingFilter(django_filters.FilterSet):
    """
    Filter for FaceEmbedding model.
    Allows filtering by face data, photo number, and quality score.
    """
    face_data = django_filters.UUIDFilter(
        field_name='face_data__id',
        label='Face data ID'
    )
    student = django_filters.UUIDFilter(
        field_name='face_data__student__id',
        label='Student ID'
    )
    photo_number = django_filters.NumberFilter(
        field_name='photo_number',
        label='Photo number'
    )
    photo_number_min = django_filters.NumberFilter(
        field_name='photo_number',
        lookup_expr='gte',
        label='Minimum photo number'
    )
    photo_number_max = django_filters.NumberFilter(
        field_name='photo_number',
        lookup_expr='lte',
        label='Maximum photo number'
    )
    quality_score = django_filters.NumberFilter(
        field_name='quality_score',
        label='Quality score (exact)'
    )
    quality_score_min = django_filters.NumberFilter(
        field_name='quality_score',
        lookup_expr='gte',
        label='Minimum quality score'
    )
    quality_score_max = django_filters.NumberFilter(
        field_name='quality_score',
        lookup_expr='lte',
        label='Maximum quality score'
    )

    class Meta:
        model = FaceEmbedding
        fields = ['face_data', 'photo_number']


class AttendanceFilter(django_filters.FilterSet):
    """
    Filter for Attendance model.
    Allows filtering by student, class session, status, and date range.
    """
    student = django_filters.UUIDFilter(
        field_name='student__id',
        label='Student ID'
    )
    student_email = django_filters.CharFilter(
        field_name='student__user__email',
        lookup_expr='icontains',
        label='Student email (contains)'
    )
    student_roll_number = django_filters.CharFilter(
        field_name='student__roll_number',
        lookup_expr='icontains',
        label='Student roll number (contains)'
    )
    class_session = django_filters.UUIDFilter(
        field_name='class_session__id',
        label='Class session ID'
    )
    class_session_name = django_filters.CharFilter(
        field_name='class_session__class_name',
        lookup_expr='icontains',
        label='Class session name (contains)'
    )
    subject = django_filters.UUIDFilter(
        field_name='class_session__subject__id',
        label='Subject ID'
    )
    subject_code = django_filters.CharFilter(
        field_name='class_session__subject__code',
        lookup_expr='iexact',
        label='Subject code'
    )
    status = django_filters.ChoiceFilter(
        field_name='status',
        choices=[('PRESENT', 'Present'), ('ABSENT', 'Absent')],
        label='Attendance status'
    )
    marked_at = django_filters.DateTimeFilter(
        field_name='marked_at',
        label='Exact marked time'
    )
    marked_at_after = django_filters.DateTimeFilter(
        field_name='marked_at',
        lookup_expr='gte',
        label='Marked from (datetime)'
    )
    marked_at_before = django_filters.DateTimeFilter(
        field_name='marked_at',
        lookup_expr='lte',
        label='Marked until (datetime)'
    )
    marked_at_range = django_filters.DateFromToRangeFilter(
        field_name='marked_at',
        label='Marked date range'
    )
    class_date = django_filters.DateFilter(
        field_name='class_session__date',
        label='Class date (YYYY-MM-DD)'
    )
    class_date_after = django_filters.DateFilter(
        field_name='class_session__date',
        lookup_expr='gte',
        label='Class date from (YYYY-MM-DD)'
    )
    class_date_before = django_filters.DateFilter(
        field_name='class_session__date',
        lookup_expr='lte',
        label='Class date until (YYYY-MM-DD)'
    )
    class_date_range = django_filters.DateFromToRangeFilter(
        field_name='class_session__date',
        label='Class date range'
    )

    class Meta:
        model = Attendance
        fields = ['student', 'class_session', 'status']


class AttendanceLogFilter(django_filters.FilterSet):
    """
    Filter for AttendanceLog model.
    Allows filtering by attendance, liveness status, and face confidence.
    """
    attendance = django_filters.UUIDFilter(
        field_name='attendance__id',
        label='Attendance ID'
    )
    student = django_filters.UUIDFilter(
        field_name='attendance__student__id',
        label='Student ID'
    )
    student_email = django_filters.CharFilter(
        field_name='attendance__student__user__email',
        lookup_expr='icontains',
        label='Student email (contains)'
    )
    class_session = django_filters.UUIDFilter(
        field_name='attendance__class_session__id',
        label='Class session ID'
    )
    liveness_passed = django_filters.ChoiceFilter(
        field_name='liveness_passed',
        choices=[('PASS', 'Liveness Check Passed'), ('FAIL', 'Liveness Check Failed'), ('UNKNOWN', 'Liveness Check Not Performed')],
        label='Liveness status'
    )
    face_confidence = django_filters.NumberFilter(
        field_name='face_confidence',
        label='Face confidence (exact)'
    )
    face_confidence_min = django_filters.NumberFilter(
        field_name='face_confidence',
        lookup_expr='gte',
        label='Minimum face confidence'
    )
    face_confidence_max = django_filters.NumberFilter(
        field_name='face_confidence',
        lookup_expr='lte',
        label='Maximum face confidence'
    )
    distance_to_nearest = django_filters.NumberFilter(
        field_name='distance_to_nearest',
        label='Distance to nearest (exact)'
    )
    distance_to_nearest_min = django_filters.NumberFilter(
        field_name='distance_to_nearest',
        lookup_expr='gte',
        label='Minimum distance to nearest'
    )
    distance_to_nearest_max = django_filters.NumberFilter(
        field_name='distance_to_nearest',
        lookup_expr='lte',
        label='Maximum distance to nearest'
    )
    best_matching_photo_number = django_filters.NumberFilter(
        field_name='best_matching_photo_number',
        label='Best matching photo number'
    )
    distance_from_classroom = django_filters.NumberFilter(
        field_name='distance_from_classroom',
        label='Distance from classroom (exact)'
    )
    distance_from_classroom_min = django_filters.NumberFilter(
        field_name='distance_from_classroom',
        lookup_expr='gte',
        label='Minimum distance from classroom'
    )
    distance_from_classroom_max = django_filters.NumberFilter(
        field_name='distance_from_classroom',
        lookup_expr='lte',
        label='Maximum distance from classroom'
    )

    class Meta:
        model = AttendanceLog
        fields = ['attendance', 'liveness_passed']
