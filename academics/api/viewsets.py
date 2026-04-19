from .serializers import *
from rest_framework import viewsets
from ..models import Subject, Enrollment, ClassSession
from ..filters import SubjectFilter, EnrollmentFilter, ClassSessionFilter
from core.utils.custom_perms import IsClientUser
from core.utils.sort import apply_sorting


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsClientUser]
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
    permission_classes = [IsClientUser]
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
    
    def list(self, request, *args, **kwargs):
        self.queryset = apply_sorting(request, self.get_queryset(), self)
        return super().list(request, *args, **kwargs)