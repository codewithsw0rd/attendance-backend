from rest_framework import serializers
from ..models import FaceData, Attendance, AttendanceLog, FaceEmbedding

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
    verification_log = AttendanceLogSerializer(read_only=True)
    
    class Meta:
        model = Attendance
        fields = ['id', 'student', 'student_email', 'student_name', 'class_session', 'status', 'marked_at', 'verification_log']
        read_only_fields = ['id', 'marked_at', 'verification_log']


class AttendanceReadSerializer(serializers.ModelSerializer):
    student_detail = serializers.SerializerMethodField()
    class_session_detail = serializers.SerializerMethodField()
    verification_log = AttendanceLogSerializer(read_only=True)
    
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
