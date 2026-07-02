from rest_framework import serializers
from ..models import FaceData, Attendance, AttendanceLog, FaceEmbedding, AttendanceSession, ClassSessionTemplate

class FaceEmbeddingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FaceEmbedding
        fields = ['id', 'photo_number', 'embedding', 'quality_score', 'created_at']
        read_only_fields = ['id', 'embedding', 'created_at']

class FaceDataSerializer(serializers.ModelSerializer):
    student_email = serializers.EmailField(source='student.user.email', read_only=True)
    student_roll_number = serializers.CharField(source='student.roll_number', read_only=True)
    embeddings = FaceEmbeddingSerializer(many=True, read_only=True)

    class Meta:
        model = FaceData
        fields = ['id', 'student', 'student_email', 'student_roll_number', 'is_enrolled', 'embeddings', 'created_at', 'updated_at']
        read_only_fields = ['id', 'embeddings', 'image_path', 'created_at', 'updated_at']


class AttendanceLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceLog
        fields = [
            'id', 'attendance', 'face_confidence', 'distance_to_nearest',
            'latitude', 'longitude', 'distance_from_classroom',
            'liveness_passed', 'face_image_path', 'is_suspicious',
            'timestamp_signed', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AttendanceSerializer(serializers.ModelSerializer):
    student_email = serializers.EmailField(source='student.user.email', read_only=True)
    student_name = serializers.CharField(source='student.first_name', read_only=True)
    verification_log = serializers.SerializerMethodField()
    
    class Meta:
        model = Attendance
        fields = ['id', 'student', 'student_email', 'student_name', 'class_session', 'status', 'marked_at', 'verification_log']
        read_only_fields = ['id', 'marked_at', 'verification_log']

    def get_verification_log(self, obj):
        latest_log = obj.verification_log.order_by('-created_at').first()
        if not latest_log:
            return None
        return AttendanceLogSerializer(latest_log).data


class AttendanceReadSerializer(serializers.ModelSerializer):
    student_detail = serializers.SerializerMethodField()
    class_session_detail = serializers.SerializerMethodField()
    verification_log = serializers.SerializerMethodField()
    
    class Meta:
        model = Attendance
        fields = ['id', 'student', 'student_detail', 'class_session', 'class_session_detail', 'status', 'marked_at', 'verification_log']
    
    def get_student_detail(self, obj):
        return {
            'email': obj.student.user.email,
            'name': obj.student.first_name,
            'roll_number': obj.student.roll_number,
        }
    
    def get_class_session_detail(self, obj):
        return {
            'id': str(obj.class_session.id),
            'class_name': obj.class_session.class_name,
            'subject': obj.class_session.subject.name,
            'date': obj.class_session.date,
            'start_time': obj.class_session.start_time,
        }

    def get_verification_log(self, obj):
        latest_log = obj.verification_log.order_by('-created_at').first()
        if not latest_log:
            return None
        return AttendanceLogSerializer(latest_log).data


# Request/Response Serializers for Schema Documentation

class AttendanceMarkRequestSerializer(serializers.Serializer):
    """Request schema for marking attendance via face recognition"""
    image = serializers.FileField(required=True, help_text="Face image file for recognition")
    class_session_id = serializers.UUIDField(required=True, help_text="UUID of the class session")
    latitude = serializers.FloatField(required=False, allow_null=True, help_text="GPS latitude (optional)")
    longitude = serializers.FloatField(required=False, allow_null=True, help_text="GPS longitude (optional)")
    distance_from_classroom = serializers.FloatField(required=False, allow_null=True, help_text="Distance from classroom in meters (optional)")
    liveness_passed = serializers.CharField(
        required=False, 
        allow_null=True,
        help_text="Liveness detection result: 'PASS', 'FAIL', or 'UNKNOWN' (optional)"
    )
    timestamp_signed = serializers.CharField(
        required=False, 
        allow_null=True,
        help_text="Digitally signed timestamp from client (optional)"
    )


class AttendanceSelfMarkRequestSerializer(serializers.Serializer):
    """Request schema for student self-marking attendance"""
    image = serializers.FileField(required=True, help_text="Face image file for recognition")
    class_session_id = serializers.UUIDField(required=True, help_text="UUID of the class session")
    latitude = serializers.FloatField(required=False, allow_null=True, help_text="GPS latitude")
    longitude = serializers.FloatField(required=False, allow_null=True, help_text="GPS longitude")
    distance_from_classroom = serializers.FloatField(required=False, allow_null=True, help_text="Distance from classroom")
    liveness_passed = serializers.CharField(required=False, allow_null=True, help_text="Liveness check: PASS/FAIL/UNKNOWN")
    timestamp_signed = serializers.CharField(required=False, allow_null=True, help_text="Signed timestamp")


class AttendanceMarkResponseSerializer(serializers.Serializer):
    """Response schema for marking attendance"""
    attendance_id = serializers.UUIDField(help_text="Unique attendance record ID")
    status = serializers.CharField(help_text="Attendance status: 'PRESENT' or 'ABSENT'")
    marked_at = serializers.DateTimeField(help_text="Timestamp when attendance was recorded")
    face_matched = serializers.BooleanField(help_text="Whether face was identified")
    confidence = serializers.FloatField(help_text="Face recognition confidence score (0-1)")
    distance_to_nearest = serializers.FloatField(help_text="Distance to nearest embedding in feature space")
    is_suspicious = serializers.BooleanField(help_text="Flag indicating suspicious attendance patterns")
    message = serializers.CharField(help_text="Status message")


class SessionSummarySerializer(serializers.Serializer):
    """Response schema for attendance session summary"""
    session_id = serializers.UUIDField(help_text="Class session ID")
    class_name = serializers.CharField(help_text="Class name")
    date = serializers.DateField(help_text="Class session date")
    total_students = serializers.IntegerField(help_text="Total enrolled students")
    present = serializers.IntegerField(help_text="Number of present students")
    absent = serializers.IntegerField(help_text="Number of absent students")
    attendance_rate = serializers.FloatField(help_text="Attendance percentage (0-100)")


class AttendanceSessionSerializer(serializers.ModelSerializer):
    """Serializer for real-time attendance sessions"""
    class_session_detail = serializers.SerializerMethodField()
    initiated_by_email = serializers.EmailField(source='initiated_by.email', read_only=True)
    marked_students_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AttendanceSession
        fields = [
            'id', 'class_session', 'class_session_detail', 'initiated_by', 
            'initiated_by_email', 'started_at', 'ended_at', 'marked_students', 
            'marked_students_count'
        ]
        read_only_fields = ['id', 'started_at', 'ended_at', 'marked_students']
    
    def get_class_session_detail(self, obj):
        return {
            'id': str(obj.class_session.id),
            'class_name': obj.class_session.class_name,
            'date': str(obj.class_session.date),
        }
    
    def get_marked_students_count(self, obj):
        return len(obj.marked_students) if obj.marked_students else 0


class FrameDetectionResponseSerializer(serializers.Serializer):
    """Response schema for frame detection via WebSocket"""
    newly_detected = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of newly detected students with confidence and timestamp"
    )
    already_marked = serializers.ListField(
        child=serializers.CharField(),
        help_text="Student IDs already marked in this session"
    )
    total_detected_so_far = serializers.IntegerField()
    timestamp = serializers.DateTimeField()


class SessionEndResponseSerializer(serializers.Serializer):
    """Response schema for ending a session"""
    session_id = serializers.UUIDField()
    status = serializers.CharField()
    marked_present = serializers.IntegerField()
    marked_absent = serializers.IntegerField()
    ended_at = serializers.DateTimeField()

class StartSessionRequestSerializer(serializers.Serializer):
    """Request schema for starting a real-time attendance session"""
    class_session_id = serializers.UUIDField(required=True)


class EndSessionRequestSerializer(serializers.Serializer):
    """Request schema for ending a real-time attendance session"""
    session_id = serializers.UUIDField(required=True)


class ClassSessionTemplateSerializer(serializers.ModelSerializer):
    """Serializer for recurring class session templates"""
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    teacher_name = serializers.CharField(source='subject.teacher.user.first_name', read_only=True)
    day_of_week_display = serializers.CharField(source='get_day_of_week_display', read_only=True)
    
    class Meta:
        model = ClassSessionTemplate
        fields = [
            'id', 'subject', 'subject_name', 'subject_code', 'teacher_name',
            'day_of_week', 'day_of_week_display', 'start_time', 'end_time',
            'max_attendance_marking_minutes', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CreateClassSessionTemplateSerializer(serializers.ModelSerializer):
    """Serializer for creating recurring class session templates"""
    class Meta:
        model = ClassSessionTemplate
        fields = [
            'subject', 'day_of_week', 'start_time', 'end_time',
            'max_attendance_marking_minutes', 'is_active'
        ]
        extra_kwargs = {
            'max_attendance_marking_minutes': {'required': False},
            'is_active': {'required': False, 'default': True}
        }