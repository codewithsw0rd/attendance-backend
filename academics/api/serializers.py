from rest_framework import serializers
from ..models import Subject, Enrollment, ClassSession

class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'department', 'semester', 'teacher', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at'] 

class SubjectReadSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField(read_only=True)
    teacher_email = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'department', 'semester', 'teacher', 'teacher_name', 'teacher_email', 'created_at', 'updated_at']
    
    def get_teacher_name(self, obj):
        if not obj.teacher:
            return None
        user = obj.teacher.user
        full_name = f"{user.first_name} {user.last_name}".strip()
        return full_name if full_name else user.email
    
    def get_teacher_email(self, obj):
        if not obj.teacher:
            return None
        return obj.teacher.user.email

class EnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enrollment
        fields = '__all__'

class EnrollmentReadSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_email = serializers.EmailField(source='student.user.email', read_only=True)
    student_roll_number = serializers.CharField(source='student.roll_number', read_only=True)
    student_department = serializers.CharField(source='student.department', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    
    class Meta:
        model = Enrollment
        fields = ['id', 'student', 'student_name', 'student_email', 'student_roll_number', 'student_department', 'subject', 'subject_name', 'subject_code', 'created_at', 'updated_at']
        
class ClassSessionSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    
    class Meta:
        model = ClassSession
        fields = ['id', 'class_name', 'date', 'start_time', 'end_time', 'subject', 'subject_name', 'subject_code', 'created_at', 'updated_at']

class ClassSessionReadSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    teacher_name = serializers.CharField(source='subject.teacher.user.get_full_name', read_only=True)
    teacher_email = serializers.EmailField(source='subject.teacher.user.email', read_only=True)
    
    class Meta:
        model = ClassSession
        fields = ['id', 'class_name', 'date', 'start_time', 'end_time', 'subject', 'subject_name', 'subject_code', 'teacher_name', 'teacher_email', 'created_at', 'updated_at']