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

class AttendanceSession(BaseModel):
    """Real-time attendance session tracking"""
    class_session = models.ForeignKey(
        ClassSession,
        on_delete=models.CASCADE,
        related_name='real_time_sessions',
        help_text="Class session this attendance is for"
    )
    initiated_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='attendance_sessions',
        help_text="Teacher who initiated this session"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    marked_students = models.JSONField(
        default=list,
        help_text="List of student user IDs detected during session"
    )
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['class_session', 'started_at']),
            models.Index(fields=['ended_at']),
        ]
    
    def __str__(self):
        return f"Session for {self.class_session.class_name} ({self.started_at})"
    
    def is_active(self):
        """Check if session is currently active (started but not ended)"""
        return self.ended_at is None
    
    def can_student_mark_attendance(self):
        """Check if session is active and allows student self-marking"""
        return self.is_active()

class Attendance(BaseModel):
    PRESENCE_CHOICES = [
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
    ]
    INITIATED_BY_CHOICES = [
        ('student', 'Student Self-Service'),
        ('teacher', 'Teacher Batch Session'),
        ('manual', 'Admin Manual Override'),
    ]
    
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='attendances')
    class_session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name='attendances')
    attendance_session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name='attendances',
        null=True,
        blank=True,
        help_text="Link to the real-time session during which this attendance was marked"
    )
    status = models.CharField(max_length=10, choices=PRESENCE_CHOICES, default='ABSENT')
    marked_at = models.DateTimeField(auto_now_add=True)

    # NEW: Track who initiated this attendance record
    initiated_by = models.CharField(
        max_length=20,
        choices=INITIATED_BY_CHOICES,
        default='teacher',
        help_text="Whether attendance was self-marked by student or teacher-marked"
    )
    initiated_by_user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_attendance_records',
        help_text="Teacher or admin who initiated this record (if applicable)"
    )

    frame_detected = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when face was detected in video frame"
    )
    detection_confidence = models.FloatField(
        default=0.0,
        help_text="Face recognition confidence score (0-1) from ML service"
    )
    attempt_count = models.IntegerField(
        default=1,
        help_text="Number of attempts student made to mark attendance"
    )
    
    class Meta:
        ordering = ['-marked_at']
        constraints = [
            # Prevent duplicate attendance within same teacher session
            models.UniqueConstraint(
                fields=['student', 'attendance_session'],
                condition=models.Q(attendance_session__isnull=False),
                name='unique_attendance_per_session'
            ),
            # Allow one student-initiated and one teacher-initiated per class_session
            models.UniqueConstraint(
                fields=['student', 'class_session', 'initiated_by'],
                condition=models.Q(initiated_by='student'),
                name='unique_student_initiated_per_class_session'
            ),
            models.UniqueConstraint(
                fields=['student', 'class_session', 'initiated_by'],
                condition=models.Q(initiated_by='manual'),
                name='unique_manual_per_class_session'
            )
        ]
    
    def __str__(self):
        return f"{self.student.user.email} - {self.class_session.class_name} - {self.status} ({self.initiated_by})"


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
