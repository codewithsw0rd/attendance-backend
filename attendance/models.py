from django.db import models
from core.utils.base_model import BaseModel
from accounts.models import StudentProfile
from academics.models import ClassSession, Subject


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


class ClassSessionTemplate(models.Model):
    """
    Reusable template for recurring classes.
    Allows the same attendance session to be used across multiple dates.
    Example: CS101 every Monday 9:00 AM - 10:00 AM
    
    Note: Uses BigAutoField (integer ID) not UUID, to align with migration 0004.
    """
    # Explicitly define ID as BigAutoField (not UUID from BaseModel)
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    DAY_OF_WEEK_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='session_templates',
        help_text="Subject this template is for"
    )
    
    day_of_week = models.IntegerField(
        choices=DAY_OF_WEEK_CHOICES,
        help_text="Day of week (0=Monday, 6=Sunday)"
    )
    
    start_time = models.TimeField(
        help_text="Class start time"
    )
    
    end_time = models.TimeField(
        help_text="Class end time"
    )
    
    max_attendance_marking_minutes = models.IntegerField(
        default=15,
        help_text="Maximum minutes after class start that students can mark attendance"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this template is active"
    )
    
    class Meta:
        unique_together = ('subject', 'day_of_week', 'start_time')
        indexes = [
            models.Index(fields=['subject', 'day_of_week']),
            models.Index(fields=['is_active']),
        ]
        ordering = ['day_of_week', 'start_time']
    
    def __str__(self):
        day_name = self.get_day_of_week_display()
        return f"{self.subject.code} - {day_name} {self.start_time}"

class AttendanceSession(BaseModel):
    """Real-time attendance session tracking (reusable across dates via template)"""
    
    # Link to template for recurring session tracking
    template = models.ForeignKey(
        ClassSessionTemplate,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='attendance_sessions',
        help_text="Template this session is based on (for recurring sessions)"
    )
    
    # Specific class session instance
    class_session = models.ForeignKey(
        ClassSession,
        on_delete=models.CASCADE,
        related_name='real_time_sessions',
        help_text="Class session this attendance is for"
    )
    
    # Teacher who initiated
    initiated_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='attendance_sessions',
        help_text="Teacher who initiated this session"
    )
    
    # Session date tracking (for template-based queries)
    session_date = models.DateField(
        auto_now_add=True,
        help_text="Date this session occurred"
    )
    
    # Session time tracking (reusable key for recurring sessions)
    session_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Time of session (e.g., 09:00 for Monday 9 AM class)"
    )
    
    # Session timing
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    # Students marked present
    marked_students = models.JSONField(
        default=list,
        help_text="List of student user IDs detected during session"
    )
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['template', 'session_date']),  # For recurring sessions
            models.Index(fields=['class_session', 'started_at']),
            models.Index(fields=['session_date', 'session_time']),  # Time-based lookup
            models.Index(fields=['ended_at']),
        ]
    
    def __str__(self):
        if self.template:
            return f"Session {self.template.get_day_of_week_display()} {self.session_time} ({self.session_date})"
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
            # ONE per attendance_session (prevents duplicate marks in same session)
            models.UniqueConstraint(
                fields=['student', 'attendance_session'],
                name='unique_attendance_per_session'
            ),
            # ONE student-initiated per class_session (prevents double self-marking)
            models.UniqueConstraint(
                fields=['student', 'class_session', 'initiated_by'],
                condition=models.Q(initiated_by='student'),
                name='unique_student_initiated_per_class_session'
            ),
            # ONE manual per class_session (prevents duplicate admin overrides)
            models.UniqueConstraint(
                fields=['student', 'class_session', 'initiated_by'],
                condition=models.Q(initiated_by='manual'),
                name='unique_manual_per_class_session'
            ),
            # ONE teacher per class_session (can be overridden by student)
            models.UniqueConstraint(
                fields=['student', 'class_session', 'initiated_by'],
                condition=models.Q(initiated_by='teacher'),
                name='unique_teacher_per_class_session'
            ),
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
