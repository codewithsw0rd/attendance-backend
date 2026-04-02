from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from accounts.models import UserType
from academics.models import Enrollment, ClassSession
from ..models import FaceData, FaceEmbedding, Attendance, AttendanceLog
from .serializers import (
    FaceDataSerializer, AttendanceSerializer, AttendanceReadSerializer, AttendanceLogSerializer
)
from core.utils.custom_perms import IsClientUser
from ..ml_client import process_attendance, MLServiceError
from django.utils import timezone
import json


class FaceDataViewSet(viewsets.ModelViewSet):
    """
    Manage student face enrollment data.
    Only returns enrollment status (actual embeddings are never exposed via API).
    """
    queryset = FaceData.objects.all()
    serializer_class = FaceDataSerializer
    permission_classes = [IsClientUser]
    
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
    parser_classes = (MultiPartParser, FormParser)
    
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


class AttendanceLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Verification logs for attendance. Read-only for auditing purposes.
    Admins can view all logs, teachers can view logs for their class sessions.
    """
    serializer_class = AttendanceLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == UserType.ADMIN:
            return AttendanceLog.objects.all()
        elif user.user_type == UserType.TEACHER:
            return AttendanceLog.objects.filter(
                attendance__class_session__subject__teacher__user=user
            )
        return AttendanceLog.objects.none()
    
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


class FaceDataViewSet(viewsets.ModelViewSet):
    """
    Manage student face enrollment data.
    Only returns enrollment status (actual embeddings are never exposed via API).
    """
    queryset = FaceData.objects.all()
    serializer_class = FaceDataSerializer
    permission_classes = [IsClientUser]
    
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
    """
    permission_classes = [IsAuthenticated]
    
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


class AttendanceLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Verification logs for attendance. Read-only for auditing purposes.
    Admins can view all logs, teachers can view logs for their class sessions.
    """
    serializer_class = AttendanceLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == UserType.ADMIN:
            return AttendanceLog.objects.all()
        elif user.user_type == UserType.TEACHER:
            return AttendanceLog.objects.filter(
                attendance__class_session__subject__teacher__user=user
            )
        return AttendanceLog.objects.none()
    
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
