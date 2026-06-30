from .serializers import *
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from ..models import Subject, Enrollment, ClassSession
from ..filters import SubjectFilter, EnrollmentFilter, ClassSessionFilter
from core.utils.custom_perms import IsClientUser, IsAdminOrTeacher
from core.utils.sort import apply_sorting
from accounts.models import UserType


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    filterset_class = SubjectFilter
    search_fields = ['name', 'code', 'department']
    
    # Sorting configuration
    ordering_fields = ['id', 'name', 'code', 'department', 'semester', 'teacher__first_name', 'created_at', 'updated_at']
    ordering = ['created_at']
    SORT_MAPPING = {
        'id': 'id',
        'name': 'name',
        'code': 'code',
        'department': 'department',
        'semester': 'semester',
        'teacher_name': 'teacher__first_name',
        'created_at': 'created_at',
        'updated_at': 'updated_at',
    }

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsClientUser()]
        return [IsAdminOrTeacher()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Subject.objects.none()
        if user.user_type == UserType.ADMIN:
            return Subject.objects.all()
        if user.user_type == UserType.TEACHER:
            return Subject.objects.filter(teacher__user=user)
        return Subject.objects.none()
    
    def list(self, request, *args, **kwargs):
        self.queryset = apply_sorting(request, self.get_queryset(), self)
        return super().list(request, *args, **kwargs)
    
class EnrollmentViewSet(viewsets.ModelViewSet):
    queryset = Enrollment.objects.all()
    serializer_class = EnrollmentSerializer
    permission_classes = [IsClientUser]
    filterset_class = EnrollmentFilter
    search_fields = ['student__roll_number', 'subject__name', 'subject__code']
    
    # Sorting configuration
    ordering_fields = ['id', 'student__roll_number', 'student__department', 'student__year', 'subject__name', 'subject__code', 'created_at', 'updated_at']
    ordering = ['created_at']
    SORT_MAPPING = {
        'id': 'id',
        'student_id': 'student__id',
        'student_roll_number': 'student__roll_number',
        'student_department': 'student__department',
        'student_year': 'student__year',
        'subject_id': 'subject__id',
        'subject_name': 'subject__name',
        'subject_code': 'subject__code',
        'created_at': 'created_at',
        'updated_at': 'updated_at',
    }
    
    def list(self, request, *args, **kwargs):
        self.queryset = apply_sorting(request, self.get_queryset(), self)
        return super().list(request, *args, **kwargs)
    
class ClassSessionViewSet(viewsets.ModelViewSet):
    queryset = ClassSession.objects.all()
    serializer_class = ClassSessionSerializer
    filterset_class = ClassSessionFilter
    search_fields = ['class_name', 'subject__name', 'subject__code']
    
    # Sorting configuration
    ordering_fields = ['id', 'subject__name', 'subject__code', 'class_name', 'date', 'start_time', 'end_time', 'created_at', 'updated_at']
    ordering = ['-date', 'start_time']
    SORT_MAPPING = {
        'id': 'id',
        'subject_id': 'subject__id',
        'subject_name': 'subject__name',
        'subject_code': 'subject__code',
        'class_name': 'class_name',
        'date': 'date',
        'start_time': 'start_time',
        'end_time': 'end_time',
        'created_at': 'created_at',
        'updated_at': 'updated_at',
    }

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsClientUser()]
        return [IsAdminOrTeacher()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return ClassSession.objects.none()
        if user.user_type == UserType.ADMIN:
            return ClassSession.objects.all()
        if user.user_type == UserType.TEACHER:
            return ClassSession.objects.filter(subject__teacher__user=user)
        return ClassSession.objects.none()

    def _ensure_teacher_owns_subject(self, subject):
        user = self.request.user
        if user.user_type == UserType.TEACHER and subject.teacher.user != user:
            raise PermissionDenied('You can only manage sessions for your own subjects.')

    def perform_create(self, serializer):
        self._ensure_teacher_owns_subject(serializer.validated_data['subject'])
        serializer.save()

    def perform_update(self, serializer):
        self._ensure_teacher_owns_subject(
            serializer.validated_data.get('subject', serializer.instance.subject)
        )
        serializer.save()
    
    def list(self, request, *args, **kwargs):
        self.queryset = apply_sorting(request, self.get_queryset(), self)
        return super().list(request, *args, **kwargs)
