from django.db import models
from core.utils.base_model import BaseModel
from accounts.models import StudentProfile
from academics.models import ClassSession


class FaceData(BaseModel):
    student = models.OneToOneField(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name='face_data'
    )
    is_enrolled = models.BooleanField(default=False)
    total_photos_registered = models.IntegerField(
        default=0,
        help_text="Number of photos used for enrollment (target: 5)"
    )
    registration_confidence = models.FloatField(
        default=0.0,
        help_text="Average quality score across all enrolled photos (0-1)"
    )
    
    def __str__(self):
        return f"Face data for {self.student.user.email}"
    
class FaceEmbedding(BaseModel):
    face_data = models.ForeignKey(
        FaceData,
        on_delete=models.CASCADE,
        related_name='embeddings'
    )
    embedding = models.JSONField()
    photo_number = models.IntegerField()
    quality_score = models.FloatField(
        default=0.0,
        help_text="Face detection confidence (0-1). Higher is better."
    )

    class Meta:
        unique_together = ('face_data', 'photo_number')
        ordering = ['photo_number']


class Attendance(BaseModel):
    PRESENCE_CHOICES = [
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
    ]
    
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='attendances')
    class_session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name='attendances')
    status = models.CharField(max_length=10, choices=PRESENCE_CHOICES, default='ABSENT')
    marked_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('student', 'class_session')
        ordering = ['-marked_at']
    
    def __str__(self):
        return f"{self.student.user.email} - {self.class_session.class_name} - {self.status}"


class AttendanceLog(BaseModel):
    LIVENESS_STATUS_CHOICES = [
        ('PASS', 'Liveness Check Passed'),
        ('FAIL', 'Liveness Check Failed'),
        ('UNKNOWN', 'Liveness Check Not Performed'),
    ]
    
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name='verification_log')
    face_confidence = models.FloatField(help_text="KNN confidence score (0.0 to 1.0)")
    distance_to_nearest = models.FloatField(help_text="Euclidean distance to nearest stored embedding")
    best_matching_photo_number = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Photo number of the best matching embedding used for attendance marking"
    )
    
    latitude = models.FloatField(null=True, blank=True, help_text="Client-captured GPS latitude")
    longitude = models.FloatField(null=True, blank=True, help_text="Client-captured GPS longitude")
    
    distance_from_classroom = models.FloatField(
        null=True, 
        blank=True, 
        help_text="Distance in meters from classroom location"
    )
    
    liveness_passed = models.CharField(
        max_length=10,
        choices=LIVENESS_STATUS_CHOICES,
        default='UNKNOWN',
        help_text="Result of liveness detection"
    )
    
    face_image_path = models.TextField(
        null=True,
        blank=True,
        help_text="Path to the captured face image used for matching"
    )
    
    is_suspicious = models.BooleanField(
        default=False,
        help_text="Set to True if admin reviewing finds suspicious activity"
    )
    
    timestamp_signed = models.TextField(
        null=True,
        blank=True,
        help_text="Digitally signed timestamp from client for audit trail"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['attendance']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Log for Attendance ID {self.attendance.id}"
