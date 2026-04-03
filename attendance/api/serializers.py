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
