from django.db import models
from core.utils.base_model import BaseModel
from accounts.models import TeacherProfile, StudentProfile

# Create your models here.
class Subject(BaseModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True)
    
    department = models.CharField(max_length=255)
    semester = models.IntegerField()
    
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.SET_NULL, null=True, related_name='subjects')
    
    
class Enrollment(BaseModel):
    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    
    class Meta:
        unique_together = ('student', 'subject')
        
    
class ClassSession(BaseModel):
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='class_sessions'
    )
    class_name = models.CharField(max_length=255)
    
    date = models.DateField()
    
    start_time = models.TimeField()
    end_time = models.TimeField()
    