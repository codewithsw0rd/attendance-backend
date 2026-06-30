from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from accounts.models import UserType
from academics.models import Enrollment, ClassSession
from ..models import FaceData, FaceEmbedding, Attendance, AttendanceLog, AttendanceSession
from ..filters import FaceDataFilter, FaceEmbeddingFilter, AttendanceFilter, AttendanceLogFilter
from rest_framework import serializers
from .serializers import (
    FaceDataSerializer, AttendanceSerializer, AttendanceReadSerializer, AttendanceLogSerializer,
    AttendanceMarkRequestSerializer, AttendanceMarkResponseSerializer, SessionSummarySerializer, 
    SessionEndResponseSerializer, AttendanceSessionSerializer,
    StartSessionRequestSerializer, EndSessionRequestSerializer
)
from core.utils.custom_perms import IsClientUser
from core.utils.sort import apply_sorting
from ..ml_client import process_attendance, MLServiceError
from django.utils import timezone
import json
from drf_spectacular.utils import extend_schema


class FaceDataViewSet(viewsets.ModelViewSet):
    """
    Manage student face enrollment data.
    Only returns enrollment status (actual embeddings are never exposed via API).
    """
    queryset = FaceData.objects.all()
    serializer_class = FaceDataSerializer
    permission_classes = [IsClientUser]
    filterset_class = FaceDataFilter
    search_fields = ['student__user__email', 'student__roll_number']
    
    # Sorting configuration
    ordering_fields = ['id', 'student__user__email', 'student__roll_number', 'is_enrolled', 'total_photos_registered', 'registration_confidence', 'created_at', 'updated_at']
    ordering = ['-created_at']
    SORT_MAPPING = {
        'id': 'id',
        'student_id': 'student__id',
        'student_email': 'student__user__email',
        'student_roll_number': 'student__roll_number',
        'is_enrolled': 'is_enrolled',
        'total_photos_registered': 'total_photos_registered',
        'registration_confidence': 'registration_confidence',
        'created_at': 'created_at',
        'updated_at': 'updated_at',
    }
    
    def list(self, request, *args, **kwargs):
        self.queryset = apply_sorting(request, self.get_queryset(), self)
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        responses={200: FaceDataSerializer},
        description="Get current user's face enrollment status including registered photos count, registration confidence, and enrollment completion status."
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_enrollment_status(self, request):
        """Get current user's face enrollment status"""
        try:
            face_data = FaceData.objects.get(student__user=request.user)
            serializer = self.get_serializer(face_data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except FaceData.DoesNotExist:
            return Response(
                {'detail': 'Face data not found for this user'},
                status=status.HTTP_404_NOT_FOUND
            )



class AttendanceViewSet(viewsets.ModelViewSet):
    """
    Handle attendance records. Supports:
    - Viewing attendance history
    - Filtering by student, class session, date range
    - Admin viewing all attendance
    - Students viewing their own attendance
    - Marking attendance via face recognition
    """
    permission_classes = [IsAuthenticated]
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    filterset_class = AttendanceFilter
    search_fields = ['student__user__email', 'student__roll_number', 'class_session__class_name']
    
    # Sorting configuration
    ordering_fields = ['id', 'student__user__email', 'student__roll_number', 'class_session__class_name', 'class_session__date', 'status', 'marked_at', 'created_at', 'updated_at']
    ordering = ['-marked_at']
    SORT_MAPPING = {
        'id': 'id',
        'student_id': 'student__id',
        'student_email': 'student__user__email',
        'student_roll_number': 'student__roll_number',
        'class_session_id': 'class_session__id',
        'class_session_name': 'class_session__class_name',
        'class_date': 'class_session__date',
        'status': 'status',
        'marked_at': 'marked_at',
        'created_at': 'created_at',
        'updated_at': 'updated_at',
    }
    
    def list(self, request, *args, **kwargs):
        self.queryset = apply_sorting(request, self.get_queryset(), self)
        return super().list(request, *args, **kwargs)
    
    def get_queryset(self):
        """Filter attendance based on user role"""
        user = self.request.user
        if user.user_type == UserType.ADMIN:
            return Attendance.objects.all()
        elif user.user_type == UserType.STUDENT:
            return Attendance.objects.filter(student__user=user)
        elif user.user_type == UserType.TEACHER:
            # Teachers can see attendance for their subjects
            return Attendance.objects.filter(
                class_session__subject__teacher__user=user
            )
        return Attendance.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'list' or self.action == 'retrieve':
            return AttendanceReadSerializer
        return AttendanceSerializer
    
    @extend_schema(
        request=AttendanceMarkRequestSerializer,
        responses={201: AttendanceMarkResponseSerializer, 200: AttendanceMarkResponseSerializer},
        description="Mark attendance using face recognition.\n\nProcess:\n1. Validates student has registered face\n2. Gets all enrolled students' embeddings\n3. Calls ML service to match face\n4. Creates Attendance record\n5. Creates AttendanceLog with verification metadata"
    )
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], parser_classes=[MultiPartParser, FormParser])
    def mark(self, request):
        """
        Mark attendance using face recognition.
        
        Request (multipart/form-data):
            - image: Face image file
            - class_session_id: UUID of the class session
            - latitude: GPS latitude (optional, but recommended)
            - longitude: GPS longitude (optional, but recommended)
            - liveness_passed: 'PASS', 'FAIL', or 'UNKNOWN'
            - timestamp_signed: Digitally signed timestamp from client
        
        Process:
            1. Validates student has registered face
            2. Gets all enrolled students' embeddings
            3. Calls ML service to match face
            4. Creates Attendance record
            5. Creates AttendanceLog with verification metadata
            6. Returns attendance result
        """
        if request.user.user_type != UserType.STUDENT:
            return Response(
                {'detail': 'Only students can mark attendance'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate required fields
        if 'image' not in request.FILES:
            return Response(
                {'detail': 'Image file is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        class_session_id = request.data.get('class_session_id')
        if not class_session_id:
            return Response(
                {'detail': 'class_session_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get the class session
            class_session = ClassSession.objects.get(id=class_session_id)
        except ClassSession.DoesNotExist:
            return Response(
                {'detail': 'Class session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if student is enrolled in this subject
        student_profile = request.user.studentprofile
        is_enrolled = Enrollment.objects.filter(
            student=student_profile,
            subject=class_session.subject
        ).exists()
        
        if not is_enrolled:
            return Response(
                {'detail': 'You are not enrolled in this subject'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if student has registered face
        try:
            student_face_data = FaceData.objects.get(student=student_profile)
            if not student_face_data.is_enrolled:
                return Response(
                    {'detail': 'You have not completed face registration yet. Please register first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except FaceData.DoesNotExist:
            return Response(
                {'detail': 'You have not registered your face yet. Please register first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get all enrolled students' face embeddings in this subject
        enrolled_students = Enrollment.objects.filter(
            subject=class_session.subject
        ).select_related('student')
        
        stored_embeddings = []
        student_ids = []
        
        for enrollment in enrolled_students:
            try:
                face_data = FaceData.objects.get(student=enrollment.student, is_enrolled=True)
                # Get all photo embeddings for this student
                embeddings = FaceEmbedding.objects.filter(face_data=face_data).order_by('photo_number')
                for embedding_record in embeddings:
                    stored_embeddings.append(embedding_record.embedding)
                    student_ids.append(str(enrollment.student.user.id))
            except FaceData.DoesNotExist:
                # Skip students who haven't completed registration
                pass
        
        if not stored_embeddings:
            return Response(
                {'detail': 'No enrolled students with registered faces found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Call ML service for face matching
        image_file = request.FILES['image']
        
        try:
            ml_result = process_attendance(
                image_file,
                stored_embeddings,
                student_ids,
                session_id=str(class_session.id)
            )
        except MLServiceError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Extract ML result
        identified_student_id = ml_result.get('student_id')
        confidence = ml_result.get('confidence', 0.0)
        distance = ml_result.get('distance_to_nearest', float('inf'))
        ml_status = ml_result.get('status', 'unknown')
        
        # Determine attendance status based on face match
        if ml_status == 'identified' and identified_student_id:
            # Face was identified as current student
            attendance_status = 'PRESENT'
        else:
            # Face not identified or too far from database
            attendance_status = 'ABSENT'
        
        # Create or update Attendance record
        attendance, created = Attendance.objects.update_or_create(
            student=student_profile,
            class_session=class_session,
            defaults={'status': attendance_status}
        )
        
        # Extract optional verification data
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        distance_from_classroom = request.data.get('distance_from_classroom')
        liveness_passed = request.data.get('liveness_passed', 'UNKNOWN')
        timestamp_signed = request.data.get('timestamp_signed')
        
        # Determine if attendance is suspicious
        is_suspicious = (
            ml_status != 'identified' or  # Face not recognized
            confidence < 0.3 or  # Low confidence match
            distance > 0.55  # High distance from stored embedding
        )
        
        # Create AttendanceLog for verification layer
        AttendanceLog.objects.create(
            attendance=attendance,
            face_confidence=confidence,
            distance_to_nearest=distance,
            latitude=float(latitude) if latitude else None,
            longitude=float(longitude) if longitude else None,
            distance_from_classroom=float(distance_from_classroom) if distance_from_classroom else None,
            liveness_passed=liveness_passed,
            face_image_path=f"attendance/{student_profile.user.email}_{timezone.now().isoformat()}.jpg",
            is_suspicious=is_suspicious,
            timestamp_signed=timestamp_signed
        )
        
        return Response(
            {
                'attendance_id': str(attendance.id),
                'status': attendance_status,
                'marked_at': attendance.marked_at.isoformat(),
                'face_matched': ml_status == 'identified',
                'confidence': round(confidence, 4),
                'distance_to_nearest': round(distance, 6),
                'is_suspicious': is_suspicious,
                'message': f'Attendance marked as {attendance_status}'
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
    
    @extend_schema(
        responses={200: AttendanceReadSerializer(many=True)},
        description="Get current student's attendance history. Only accessible to students. Returns list of attendance records with student, class session, and verification details."
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_attendance(self, request):
        """Get current student's attendance history"""
        if request.user.user_type != UserType.STUDENT:
            return Response(
                {'detail': 'Only students can access their attendance'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        attendances = Attendance.objects.filter(
            student__user=request.user
        ).order_by('-marked_at')
        
        serializer = AttendanceReadSerializer(attendances, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        responses={200: AttendanceReadSerializer(many=True)},
        description="Get attendance records for a specific class session. Teacher only. Requires 'session_id' query parameter."
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def class_attendance(self, request):
        """Get attendance for a specific class session (teacher only)"""
        if request.user.user_type != UserType.TEACHER:
            return Response(
                {'detail': 'Only teachers can access class attendance'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        session_id = request.query_params.get('session_id')
        if not session_id:
            return Response(
                {'detail': 'session_id query parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            session = ClassSession.objects.get(
                id=session_id,
                subject__teacher__user=request.user
            )
            attendances = Attendance.objects.filter(
                class_session=session
            ).order_by('student__roll_number')
            
            serializer = AttendanceReadSerializer(attendances, many=True)
            return Response(serializer.data)
        except ClassSession.DoesNotExist:
            return Response(
                {'detail': 'Class session not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        responses={200: SessionSummarySerializer},
        description="Get attendance summary for a class session including total students, present/absent counts, and attendance rate. Teacher only. Requires 'session_id' query parameter."
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def session_summary(self, request):
        """Get attendance summary for a class session (teacher only)"""
        if request.user.user_type != UserType.TEACHER:
            return Response(
                {'detail': 'Only teachers can access class attendance'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        session_id = request.query_params.get('session_id')
        if not session_id:
            return Response(
                {'detail': 'session_id query parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            session = ClassSession.objects.get(
                id=session_id,
                subject__teacher__user=request.user
            )
            
            total_students = Enrollment.objects.filter(
                subject=session.subject
            ).count()
            
            present_count = Attendance.objects.filter(
                class_session=session,
                status='PRESENT'
            ).count()
            
            absent_count = Attendance.objects.filter(
                class_session=session,
                status='ABSENT'
            ).count()
            
            return Response({
                'session_id': str(session.id),
                'class_name': session.class_name,
                'date': session.date,
                'total_students': total_students,
                'present': present_count,
                'absent': absent_count,
                'attendance_rate': (present_count / total_students * 100) if total_students > 0 else 0
            })
        except ClassSession.DoesNotExist:
            return Response(
                {'detail': 'Class session not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )

    @extend_schema(
        request=StartSessionRequestSerializer,
        responses={201: AttendanceSessionSerializer},
        description="Start real-time attendance session. Teacher initiates camera streaming for continuous face detection."
    )
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def start_session(self, request, *args, **kwargs):
        """
        Start a new real-time attendance session.
        Only teachers can initiate sessions for their classes.
        
        Request (JSON):
            - class_session_id: UUID of the class session
        
        Response: AttendanceSession details with session ID for WebSocket connection
        """
        if request.user.user_type != UserType.TEACHER:
            return Response(
                {'detail': 'Only teachers can start attendance sessions'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        class_session_id = request.data.get('class_session_id')
        if not class_session_id:
            return Response(
                {'detail': 'class_session_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            class_session = ClassSession.objects.get(id=class_session_id)
            # Verify teacher teaches this class
            if class_session.subject.teacher.user != request.user:
                return Response(
                    {'detail': 'You do not teach this class'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except ClassSession.DoesNotExist:
            return Response(
                {'detail': 'Class session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create new session
        from ..models import AttendanceSession
        session = AttendanceSession.objects.create(
            class_session=class_session,
            initiated_by=request.user,
            marked_students=[]
        )
        
        serializer = AttendanceSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=EndSessionRequestSerializer,
        responses={200: SessionEndResponseSerializer},
        description="End attendance session and auto-mark absent students"
    )
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def end_session(self, request, *args, **kwargs):
        """
        End real-time attendance session and auto-mark absent students.
        
        Process:
            1. Closes the attendance session
            2. Gets all students enrolled in the class
            3. Marks as ABSENT any student NOT detected during session
            4. Returns summary statistics
        
        Request (JSON):
            - session_id: UUID of the AttendanceSession to close
        
        Response: Session summary with present/absent counts
        """
        session_id = request.data.get('session_id')
        if not session_id:
            return Response(
                {'detail': 'session_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from ..models import AttendanceSession
        try:
            session = AttendanceSession.objects.get(id=session_id, ended_at=None)
        except AttendanceSession.DoesNotExist:
            return Response(
                {'detail': 'Session not found or already ended'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify requester is the teacher who started the session
        if session.initiated_by != request.user:
            return Response(
                {'detail': 'Only session initiator can end session'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get all enrolled students in this class
        enrolled = Enrollment.objects.filter(subject=session.class_session.subject)
        
        # Mark as ABSENT if not detected
        marked_student_ids = session.marked_students
        for enrollment in enrolled:
            student_user_id = str(enrollment.student.user.id)
            if student_user_id not in marked_student_ids:
                Attendance.objects.get_or_create(
                    student=enrollment.student,
                    class_session=session.class_session,
                    attendance_session=session,
                    defaults={
                        'status': 'ABSENT',
                        'frame_detected': timezone.now(),
                        'detection_confidence': 0.0
                    }
                )
        
        # Close session
        session.ended_at = timezone.now()
        session.save()
        
        # Return summary
        present_count = Attendance.objects.filter(
            attendance_session=session,
            status='PRESENT'
        ).count()
        absent_count = Attendance.objects.filter(
            attendance_session=session,
            status='ABSENT'
        ).count()
        
        return Response({
            'session_id': str(session.id),
            'status': 'ended',
            'marked_present': present_count,
            'marked_absent': absent_count,
            'ended_at': session.ended_at.isoformat()
        }, status=status.HTTP_200_OK)


    @extend_schema(
    responses={200: serializers.Serializer()},
    description="WebSocket endpoint for real-time attendance streaming (Not a REST endpoint).\n\n"
                "WEBSOCKET PROTOCOL:\n"
                "Connection URL: ws://host/ws/attendance/stream/{session_id}/\n\n"
                "Flow:\n"
                "1. Teacher starts a session via POST /attendance/start_session/\n"
                "2. Connect to WebSocket with the returned session_id\n"
                "3. Send video frames continuously (binary data)\n"
                "4. Receive detection results in real-time\n"
                "5. End session via POST /attendance/end_session/\n\n"
                "Message Formats:\n"
                "INCOMING (Server → Client):\n"
                "{\n"
                "  'type': 'connection_established',\n"
                "  'status': 'connected',\n"
                "  'session_id': 'uuid',\n"
                "  'message': 'Ready to receive frames'\n"
                "}\n"
                "OR\n"
                "{\n"
                "  'type': 'frame_processed',\n"
                "  'newly_detected': [\n"
                "    {'student_id': 'uuid', 'student_email': 'email@example.com', "
                "'confidence': 0.92, 'detected_at': 'timestamp'}\n"
                "  ],\n"
                "  'timestamp': 'timestamp'\n"
                "}\n\n"
                "OUTGOING (Client → Server):\n"
                "Binary frame data (JPEG/PNG image bytes)\n\n"
                "Only the teacher who initiated the session can connect. "
                "Authentication is required via AuthMiddlewareStack.",
    tags=['Real-Time Attendance'],
    exclude=True  # Exclude from REST schema as it's WebSocket, not REST
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def websocket_stream(self, request):
        """WebSocket documentation endpoint (for schema only)"""
        pass

    
class AttendanceLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Verification logs for attendance. Read-only for auditing purposes.
    Admins can view all logs, teachers can view logs for their class sessions.
    """
    serializer_class = AttendanceLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = AttendanceLogFilter
    search_fields = ['attendance__student__user__email', 'attendance__student__roll_number']
    
    # Sorting configuration
    ordering_fields = ['id', 'attendance__student__user__email', 'attendance__student__roll_number', 'attendance__class_session__class_name', 'face_confidence', 'distance_to_nearest', 'liveness_passed', 'created_at', 'updated_at']
    ordering = ['-created_at']
    SORT_MAPPING = {
        'id': 'id',
        'attendance_id': 'attendance__id',
        'student_id': 'attendance__student__id',
        'student_email': 'attendance__student__user__email',
        'student_roll_number': 'attendance__student__roll_number',
        'class_session_id': 'attendance__class_session__id',
        'class_session_name': 'attendance__class_session__class_name',
        'face_confidence': 'face_confidence',
        'distance_to_nearest': 'distance_to_nearest',
        'liveness_passed': 'liveness_passed',
        'created_at': 'created_at',
        'updated_at': 'updated_at',
    }
    
    def list(self, request, *args, **kwargs):
        self.queryset = apply_sorting(request, self.get_queryset(), self)
        return super().list(request, *args, **kwargs)
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == UserType.ADMIN:
            return AttendanceLog.objects.all()
        elif user.user_type == UserType.TEACHER:
            return AttendanceLog.objects.filter(
                attendance__class_session__subject__teacher__user=user
            )
        return AttendanceLog.objects.none()
    
    @extend_schema(
        responses={200: AttendanceLogSerializer(many=True)},
        description="Get all suspicious attendance records (admin only). Identifies attendance patterns flagged as suspicious based on face confidence, distance, and other metrics."
    )
    @action(detail=False, methods=['get'])
    def suspicious_activity(self, request):
        """Get all suspicious attendance logs (admin only)"""
        if request.user.user_type != UserType.ADMIN:
            return Response(
                {'detail': 'Only admins can view suspicious activity'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        logs = AttendanceLog.objects.filter(is_suspicious=True).order_by('-created_at')
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)
