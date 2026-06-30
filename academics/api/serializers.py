from rest_framework import serializers
from ..models import Subject, Enrollment, ClassSession

class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = '__all__' 
        
class EnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enrollment
        fields = '__all__'
        
class ClassSessionSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    
    class Meta:
        model = ClassSession
        fields = ['id', 'class_name', 'date', 'start_time', 'end_time', 'subject', 'subject_name', 'subject_code', 'created_at', 'updated_at']