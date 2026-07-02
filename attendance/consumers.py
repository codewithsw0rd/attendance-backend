"""WebSocket handler for real-time attendance."""
import asyncio
import json
import logging
from io import BytesIO
import base64
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from uuid import UUID

from attendance.models import AttendanceSession, Attendance, FaceData
from academics.models import Enrollment
from attendance.ml_client import process_continuous_detection, MLServiceError
from accounts.models import UserType

logger = logging.getLogger(__name__)

_CACHE_REFRESH_INTERVAL = 30
_PROCESSING_TIMEOUT = 8.0  # Reduced from 12s to 8s for faster failure detection


class AttendanceStreamConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time face detection and attendance marking."""
    
    async def connect(self):
        """Handle WebSocket connection and authentication."""
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.session_group_name = f'attendance_session_{self.session_id}'
        user = self.scope['user']

        if not user.is_authenticated:
            logger.warning(f"WebSocket auth failed for session {self.session_id}")
            await self.close(code=4003)
            return

        session_data = await self.get_session_data()
        if not session_data or user.id != session_data['initiated_by_id']:
            await self.close(code=4003)
            return

        try:
            await self.channel_layer.group_add(self.session_group_name, self.channel_name)
        except Exception as e:
            logger.error(f"Channel layer error: {str(e)}")
            await self.close(code=1011)
            return

        self._embeddings_cache: list[list[float]] = []
        self._student_ids_cache: list[str] = []
        self._student_names_map: dict[str, str] = {}
        self._cache_frame_count: int = 0
        self._frame_lock = asyncio.Lock()
        
        await self._refresh_embedding_cache()
        await self.accept()
        
        logger.info(f"WebSocket connected for session {self.session_id}")
        await self.send(json.dumps({
            'type': 'connection_established',
            'session_id': str(self.session_id),
            'status': 'connected',
            'message': 'Ready to receive frames'
        }))
    
    async def receive(self, text_data=None, bytes_data=None):
        """Receive and process video frame."""
        if self._frame_lock.locked():
            return

        try:
            frame_io = None

            if text_data:
                try:
                    message = json.loads(text_data)
                    if message.get('type') != 'frame' or 'data' not in message:
                        return
                    data_url = message['data']
                    if isinstance(data_url, str) and ',' in data_url:
                        _, b64_data = data_url.split(',', 1)
                    else:
                        b64_data = data_url
                    frame_bytes = base64.b64decode(b64_data)
                    frame_io = BytesIO(frame_bytes)
                except Exception as e:
                    logger.error(f"Frame decode error: {str(e)}")
                    await self.send(json.dumps({'type': 'error', 'detail': 'Invalid frame'}))
                    return

            elif bytes_data:
                frame_io = BytesIO(bytes_data)

            if frame_io is None:
                return

            try:
                async with self._frame_lock:
                    detections = await asyncio.wait_for(
                        self.process_frame(frame_io),
                        timeout=_PROCESSING_TIMEOUT
                    )
            except asyncio.TimeoutError:
                logger.warning(f"ML timeout for session {self.session_id}")
                await self.send(json.dumps({
                    'type': 'frame_processed',
                    'newly_detected': [],
                    'ml_status': 'timeout',
                    'total_faces_detected': 0,
                    'enrolled_embeddings': len(self._embeddings_cache),
                    'nearest_distance': None,
                    'faces': [],
                    'timestamp': timezone.now().isoformat()
                }))
                return

            await self.send(json.dumps({
                'type': 'frame_processed',
                'newly_detected': detections['newly_detected'],
                'ml_status': detections.get('ml_status'),
                'total_faces_detected': detections.get('total_faces_detected', 0),
                'enrolled_embeddings': detections.get('enrolled_embeddings', 0),
                'nearest_distance': detections.get('nearest_distance'),
                'faces': detections.get('faces', []),
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            logger.error(f"Frame processing error: {str(e)}")
            await self.send(json.dumps({'type': 'error', 'detail': str(e)}))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'session_group_name'):
            try:
                await self.channel_layer.group_discard(self.session_group_name, self.channel_name)
            except Exception as e:
                logger.error(f"Disconnect error: {str(e)}")
        logger.info(f"WebSocket disconnected for session {self.session_id}")

    @database_sync_to_async
    def get_session_data(self):
        """Get active session metadata."""
        try:
            session = AttendanceSession.objects.select_related('initiated_by').get(
                id=UUID(self.session_id),
                ended_at=None
            )
            return {'id': str(session.id), 'initiated_by_id': session.initiated_by_id}
        except Exception as e:
            logger.error(f"Session lookup error: {str(e)}")
            return None

    @database_sync_to_async
    def _load_embeddings(self):
        """Load enrolled students' embeddings for this session's subject."""
        try:
            session = AttendanceSession.objects.select_related('class_session__subject').get(
                id=UUID(self.session_id),
                ended_at=None
            )
        except AttendanceSession.DoesNotExist:
            return [], [], {}

        face_data_qs = (
            FaceData.objects
            .filter(
                student__enrollments__subject=session.class_session.subject,
                is_enrolled=True,
            )
            .select_related('student__user')
            .prefetch_related('embeddings')
        )

        stored_embeddings: list[list[float]] = []
        student_ids: list[str] = []
        student_names: dict[str, str] = {}

        for face_data in face_data_qs:
            student_id = str(face_data.student.user.id)
            student_name = f"{face_data.student.first_name or ''} {face_data.student.last_name or ''}".strip()
            student_names[student_id] = student_name
            
            for emb in face_data.embeddings.all():
                stored_embeddings.append(emb.embedding)
                student_ids.append(student_id)

        return stored_embeddings, student_ids, student_names

    async def _refresh_embedding_cache(self):
        """Refresh embedding cache from database."""
        embeddings, student_ids, student_names = await self._load_embeddings()
        self._embeddings_cache = embeddings
        self._student_ids_cache = student_ids
        self._student_names_map = student_names
        self._cache_frame_count = 0
        logger.debug(
            f"Cache refreshed for session {self.session_id}: "
            f"{len(embeddings)} embeddings for {len(set(student_ids))} students"
        )
    
    async def process_frame(self, frame_io):
        """Process video frame and detect faces."""
        self._cache_frame_count += 1
        if self._cache_frame_count >= _CACHE_REFRESH_INTERVAL:
            await self._refresh_embedding_cache()

        if not self._embeddings_cache:
            logger.warning(f"No enrolled faces for session {self.session_id}")
            return {
                'newly_detected': [],
                'ml_status': 'no_enrolled_faces',
                'total_faces_detected': 0,
                'enrolled_embeddings': 0,
                'faces': [],
            }

        try:
            session = await database_sync_to_async(
                AttendanceSession.objects.select_related('class_session', 'class_session__subject').get
            )(id=UUID(self.session_id), ended_at=None)
        except AttendanceSession.DoesNotExist:
            logger.error(f"Session {self.session_id} not found")
            raise Exception("Session not found")

        ml_result = await database_sync_to_async(process_continuous_detection)(
            frame_io,
            self._embeddings_cache,
            self._student_ids_cache,
            str(self.session_id)
        )

        # Add student names to face boxes
        for face in ml_result.get('faces', []):
            if face.get('student_id') and face['student_id'] in self._student_names_map:
                face['student_name'] = self._student_names_map[face['student_id']]

        newly_detected = []
        for detection in ml_result.get('detections', []):
            student_id = detection.get('student_id')
            confidence = detection.get('confidence', 0.0)
            distance = detection.get('distance', 0.0)

            if not student_id:
                continue

            result = await database_sync_to_async(self._mark_student_present)(
                session, student_id, confidence
            )
            if result:
                newly_detected.append({
                    **result,
                    'confidence': round(confidence, 4),
                    'distance': round(distance, 6),
                    'marked_at': timezone.now().isoformat()
                })
                await self._refresh_embedding_cache()

        return {
            'newly_detected': newly_detected,
            'ml_status': ml_result.get('status'),
            'total_faces_detected': ml_result.get('total_faces_detected', 0),
            'enrolled_embeddings': len(self._embeddings_cache),
            'nearest_distance': ml_result.get('nearest_distance'),
            'faces': ml_result.get('faces', []),
        }

    def _mark_student_present(self, session, student_id: str, confidence: float) -> dict | None:
        """Mark student as present if not already marked in this session."""
        try:
            enrollment = Enrollment.objects.select_related('student__user').get(
                subject=session.class_session.subject,
                student__user__id=UUID(student_id)
            )
        except Enrollment.DoesNotExist:
            logger.warning(f"Enrollment not found for student {student_id}")
            return None

        attendance, created = Attendance.objects.get_or_create(
            student=enrollment.student,
            attendance_session=session,
            defaults={
                'class_session': session.class_session,
                'status': 'PRESENT',
                'frame_detected': timezone.now(),
                'detection_confidence': confidence,
            }
        )

        if not created:
            return None

        marked = list(session.marked_students or [])
        if student_id not in marked:
            marked.append(student_id)
            AttendanceSession.objects.filter(pk=session.pk).update(marked_students=marked)

        logger.info(f"Student {student_id} marked present in session {self.session_id}")
        student = enrollment.student
        return {
            'student_id': student_id,
            'student_email': student.user.email,
            'student_name': f"{student.first_name or ''} {student.last_name or ''}".strip(),
            'student_roll_number': student.roll_number,
        }


class StudentAttendanceStreamConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for student-initiated face detection and attendance marking.
    Student streams frames from their device camera, ML detects their face and marks attendance.
    
    Flow:
    1. Student opens running session
    2. Connects to WebSocket with attendance_session_id
    3. Streams video frames continuously
    4. ML detects student's face
    5. Attendance auto-marked when recognized
    """
    
    async def connect(self):
        """Handle WebSocket connection for student attendance streaming."""
        try:
            self.attendance_session_id = self.scope['url_route']['kwargs']['session_id']
            self.session_group_name = f'student_attendance_{self.attendance_session_id}'
            logger.info(f"📡 Connect attempt for session: {self.attendance_session_id}")
            
            user = self.scope['user']
            logger.info(f"User authenticated: {user.is_authenticated}, type: {getattr(user, 'user_type', 'N/A')}")
            
            if not user.is_authenticated:
                logger.warning(f"❌ WebSocket auth failed for student attendance {self.attendance_session_id}")
                await self.close(code=4003)
                return
            
            if user.user_type != UserType.STUDENT:
                logger.warning(f"❌ Non-student {user.id} tried to stream attendance")
                await self.close(code=4003)
                return
            
            # Verify attendance session exists and is active
            logger.info(f"🔍 Verifying attendance session...")
            session_data = await self.get_session_data()
            if not session_data:
                logger.warning(f"❌ Session data not found or session already ended")
                await self.close(code=4004)
                return
            
            self.user_id = str(user.id)
            logger.info(f"✅ User ID set: {self.user_id}")
            
            # Get student profile safely
            try:
                self.student_profile = user.studentprofile
                logger.info(f"✅ Student profile loaded")
            except AttributeError:
                logger.error(f"❌ Student {self.user_id} has no StudentProfile")
                await self.close(code=4004)
                return
            
            self.attendance_session = session_data
            
            try:
                await self.channel_layer.group_add(self.session_group_name, self.channel_name)
                logger.info(f"✅ Joined channel group")
            except Exception as e:
                logger.error(f"❌ Channel layer error: {str(e)}")
                await self.close(code=1011)
                return
            
            # Load student's own face embeddings
            logger.info(f"🔍 Loading student face embeddings...")
            self._student_embedding = await self._load_student_embedding()
            logger.info(f"Face embedding loaded: {self._student_embedding is not None}")
            
            self._frame_count = 0
            self._frame_lock = asyncio.Lock()
            
            await self.accept()
            logger.info(f"✅ Connection accepted")
            
            logger.info(f"✅ Student {self.user_id} connected to attendance stream for session {self.attendance_session_id}")
            await self.send(json.dumps({
                'type': 'connection_established',
                'session_id': str(self.attendance_session_id),
                'message': 'Connected. Streaming frames for attendance detection...',
                'has_face_registered': self._student_embedding is not None
            }))
        except Exception as e:
            logger.error(f"❌ Error in StudentAttendanceStreamConsumer.connect: {str(e)}", exc_info=True)
            await self.close(code=1011)
    
    async def receive(self, text_data=None, bytes_data=None):
        """Receive and process video frame from student."""
        try:
            if not hasattr(self, '_frame_lock') or self._frame_lock.locked():
                return
            
            frame_io = None
            
            if text_data:
                try:
                    message = json.loads(text_data)
                    if message.get('type') != 'frame' or 'data' not in message:
                        return
                    data_url = message['data']
                    if isinstance(data_url, str) and ',' in data_url:
                        _, b64_data = data_url.split(',', 1)
                    else:
                        b64_data = data_url
                    frame_bytes = base64.b64decode(b64_data)
                    frame_io = BytesIO(frame_bytes)
                except Exception as e:
                    logger.error(f"Frame decode error for student {self.user_id}: {str(e)}")
                    return
            
            elif bytes_data:
                frame_io = BytesIO(bytes_data)
            
            if frame_io is None:
                return
            
            # Check if student already marked attendance
            already_marked = await self._check_already_marked()
            if already_marked:
                # Stop processing if already marked
                await self.send(json.dumps({
                    'type': 'frame_processed',
                    'status': 'already_marked',
                    'message': 'You have already marked attendance for this session',
                    'timestamp': timezone.now().isoformat()
                }))
                return
            
            try:
                async with self._frame_lock:
                    result = await asyncio.wait_for(
                        self.process_frame(frame_io),
                        timeout=8.0
                    )
            except asyncio.TimeoutError:
                logger.warning(f"ML timeout for student {self.user_id}")
                await self.send(json.dumps({
                    'type': 'frame_processed',
                    'status': 'timeout',
                    'message': 'Processing timeout',
                    'timestamp': timezone.now().isoformat()
                }))
                return
            
            await self.send(json.dumps({
                'type': 'frame_processed',
                'status': result['status'],
                'face_detected': result.get('face_detected', False),
                'confidence': result.get('confidence'),
                'attendance_marked': result.get('attendance_marked', False),
                'message': result.get('message'),
                'timestamp': timezone.now().isoformat()
            }))
        
        except Exception as e:
            logger.error(f"Frame processing error for student {getattr(self, 'user_id', 'unknown')}: {str(e)}", exc_info=True)
            await self.send(json.dumps({'type': 'error', 'detail': str(e)}))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'session_group_name'):
            try:
                await self.channel_layer.group_discard(self.session_group_name, self.channel_name)
            except Exception as e:
                logger.error(f"Disconnect error: {str(e)}")
        logger.info(f"Student {self.user_id} disconnected from attendance stream")
    
    @database_sync_to_async
    def get_session_data(self):
        """Verify attendance session exists and is active."""
        try:
            from attendance.models import AttendanceSession
            logger.info(f"Looking up attendance session: {self.attendance_session_id}")
            session = AttendanceSession.objects.select_related('class_session__subject').get(
                id=UUID(self.attendance_session_id),
                ended_at=None  # Session must still be active
            )
            logger.info(f"✅ Session found: {session.id}")
            return {
                'id': str(session.id),
                'class_session_id': str(session.class_session.id),
                'subject_id': str(session.class_session.subject.id),
            }
        except AttendanceSession.DoesNotExist:
            logger.error(f"Attendance session not found: {self.attendance_session_id}")
            return None
        except Exception as e:
            logger.error(f"Session lookup error for {self.attendance_session_id}: {str(e)}", exc_info=True)
            return None
    
    @database_sync_to_async
    def _load_student_embedding(self):
        """Load this student's face embedding for recognition."""
        try:
            face_data = FaceData.objects.prefetch_related('embeddings').get(
                student=self.student_profile,
                is_enrolled=True
            )
            # Get average embedding or first one
            embeddings = list(face_data.embeddings.all())
            if embeddings:
                logger.info(f"✅ Found {len(embeddings)} enrollments for student {self.user_id}")
                return embeddings[0].embedding  # Use first enrolled embedding
            logger.warning(f"⚠️ No embeddings found for student {self.user_id}")
            return None
        except FaceData.DoesNotExist:
            logger.warning(f"⚠️ No face data registered for student {self.user_id}")
            return None
        except Exception as e:
            logger.error(f"Error loading student embedding for {self.user_id}: {str(e)}", exc_info=True)
            return None
    
    @database_sync_to_async
    def _check_already_marked(self):
        """Check if student already marked attendance for this session."""
        try:
            from attendance.models import Attendance, AttendanceSession
            session = AttendanceSession.objects.get(id=UUID(self.attendance_session_id))
            return Attendance.objects.filter(
                student=self.student_profile,
                attendance_session=session
            ).exists()
        except Exception as e:
            logger.error(f"Error checking marked status: {str(e)}")
            return False
    
    async def process_frame(self, frame_io):
        """Process student's video frame and detect their face."""
        self._frame_count += 1
        
        if not self._student_embedding:
            return {
                'status': 'no_face_registered',
                'face_detected': False,
                'message': 'Face not registered. Please complete face enrollment first.',
                'confidence': 0
            }
        
        try:
            ml_result = await database_sync_to_async(process_continuous_detection)(
                frame_io,
                [self._student_embedding],  # Only check against student's own embedding
                [self.user_id],  # Only looking for this student
                str(self.attendance_session_id)
            )
        except MLServiceError as e:
            logger.error(f"ML service error for student {self.user_id}: {str(e)}")
            return {
                'status': 'ml_error',
                'face_detected': False,
                'message': f'ML service error: {str(e)}',
                'confidence': 0
            }
        
        # Check if student's face was detected
        detections = ml_result.get('detections', [])
        if not detections:
            return {
                'status': 'no_face_detected',
                'face_detected': False,
                'message': 'No face detected. Please position your face in the camera.',
                'confidence': 0
            }
        
        # Get best detection
        best_detection = max(detections, key=lambda x: x.get('confidence', 0))
        confidence = best_detection.get('confidence', 0)
        
        # Mark attendance if confidence is high enough (e.g., > 0.7)
        CONFIDENCE_THRESHOLD = 0.7
        if confidence >= CONFIDENCE_THRESHOLD:
            marked = await self._mark_student_present(confidence)
            if marked:
                return {
                    'status': 'attendance_marked',
                    'face_detected': True,
                    'confidence': round(confidence, 4),
                    'attendance_marked': True,
                    'message': f'✅ Attendance marked! (Confidence: {confidence*100:.0f}%)'
                }
        
        return {
            'status': 'face_detected_low_confidence',
            'face_detected': True,
            'confidence': round(confidence, 4),
            'attendance_marked': False,
            'message': f'Face detected but confidence too low ({confidence*100:.0f}%). Please move closer.'
        }
    
    @database_sync_to_async
    def _mark_student_present(self, confidence: float) -> bool:
        """Mark student as present in attendance session."""
        try:
            from attendance.models import AttendanceSession, Attendance
            
            session = AttendanceSession.objects.get(id=UUID(self.attendance_session_id))
            
            # Create attendance record (will fail if already exists due to unique constraint)
            attendance, created = Attendance.objects.get_or_create(
                student=self.student_profile,
                attendance_session=session,
                defaults={
                    'class_session': session.class_session,
                    'status': 'PRESENT',
                    'frame_detected': timezone.now(),
                    'detection_confidence': confidence,
                    'initiated_by': 'student',  # Student-initiated via WebSocket
                }
            )
            
            if created:
                # Update marked_students list
                marked = list(session.marked_students or [])
                if self.user_id not in marked:
                    marked.append(self.user_id)
                    AttendanceSession.objects.filter(pk=session.pk).update(marked_students=marked)
                
                logger.info(f"Student {self.user_id} marked present in session {self.attendance_session_id}")
                return True
            else:
                logger.info(f"Student {self.user_id} already marked in session {self.attendance_session_id}")
                return False
        except Exception as e:
            logger.error(f"Error marking attendance for student {self.user_id}: {str(e)}")
            return False


class StudentNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time student notifications.
    Handles session start/end and attendance marking notifications.
    
    Events:
    - session_started: Teacher started attendance session
    - session_ended: Teacher ended attendance session
    - attendance_marked: Student's attendance has been marked
    """
    
    async def connect(self):
        """Handle WebSocket connection for student notifications."""
        try:
            user = self.scope['user']
            
            # Check authentication
            if not user.is_authenticated:
                logger.warning("WebSocket auth failed for notifications")
                await self.close(code=4003)
                return
            
            # Check user type
            if user.user_type != UserType.STUDENT:
                logger.warning(f"Non-student user {user.id} tried to connect to notifications")
                await self.close(code=4003)
                return
            
            self.user_id = str(user.id)
            self.student_group = f'student_notifications_{self.user_id}'
            self.session_groups = []
            
            # Join personal notification group
            try:
                await self.channel_layer.group_add(self.student_group, self.channel_name)
            except Exception as e:
                logger.error(f"Error joining personal group: {str(e)}")
                await self.close(code=1011)
                return
            
            # Join groups for all enrolled classes
            await self._join_enrolled_class_groups()
            
            await self.accept()
            
            logger.info(f"Student {self.user_id} connected to notifications. "
                       f"Joined {len(self.session_groups)} session groups")
            
            await self.send(json.dumps({
                'type': 'connection_established',
                'message': 'Connected to real-time notifications',
                'enrolled_classes': len(self.session_groups)
            }))
        except Exception as e:
            logger.error(f"Error in StudentNotificationConsumer.connect: {str(e)}", exc_info=True)
            await self.close(code=1011)
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave personal group
        if hasattr(self, 'student_group'):
            try:
                await self.channel_layer.group_discard(self.student_group, self.channel_name)
            except Exception as e:
                logger.error(f"Error leaving personal group: {str(e)}")
        
        # Leave all session groups
        if hasattr(self, 'session_groups'):
            for session_group in self.session_groups:
                try:
                    await self.channel_layer.group_discard(session_group, self.channel_name)
                except Exception as e:
                    logger.error(f"Error leaving session group {session_group}: {str(e)}")
        
        logger.info(f"Student {self.user_id} disconnected from notifications")
    
    async def _join_enrolled_class_groups(self):
        """Join groups for all enrolled classes."""
        try:
            groups = await self._get_enrolled_class_groups()
            
            # Actually join each group
            for group_name in groups:
                try:
                    await self.channel_layer.group_add(group_name, self.channel_name)
                except Exception as e:
                    logger.error(f"Error joining session group {group_name}: {str(e)}")
            
            self.session_groups = groups
            logger.info(f"Student {self.user_id} joined {len(groups)} session groups: {groups}")
        except Exception as e:
            logger.error(f"Error joining enrolled class groups: {str(e)}")
            self.session_groups = []
    
    @database_sync_to_async
    def _get_enrolled_class_groups(self):
        """Get list of groups for all enrolled classes."""
        try:
            from academics.models import ClassSession
            from attendance.models import ClassSessionTemplate
            
            student = self.scope['user'].studentprofile
            today = timezone.now().date()
            today_weekday = today.weekday()
            
            # Get enrolled subjects
            enrollments = Enrollment.objects.filter(
                student=student
            ).values_list('subject_id', flat=True)
            
            # Get today's and future class sessions (next 7 days)
            future_date = today + timezone.timedelta(days=7)
            sessions = ClassSession.objects.filter(
                subject_id__in=enrollments,
                date__gte=today,
                date__lte=future_date
            )
            
            groups = []
            for session in sessions:
                group_name = f'session_students_{session.id}'
                groups.append(group_name)
            
            # ALSO JOIN: Groups for templates scheduled for today
            # Proactively create ClassSession for templates to ensure the group exists
            templates = ClassSessionTemplate.objects.filter(
                subject_id__in=enrollments,
                day_of_week=today_weekday,
                is_active=True
            )
            
            for template in templates:
                # Create or get ClassSession for today based on template
                class_session = ClassSession.objects.filter(
                    subject=template.subject,
                    date=today
                ).first()
                
                if not class_session:
                    class_session = ClassSession.objects.create(
                        subject=template.subject,
                        date=today,
                        class_name=f"{template.subject.code} - {template.get_day_of_week_display()}",
                        start_time=template.start_time,
                        end_time=template.end_time,
                    )
                
                group_name = f'session_students_{class_session.id}'
                if group_name not in groups:
                    groups.append(group_name)
            
            logger.info(f"Student {self.user_id} joined {len(groups)} session groups")
            return groups
        except Exception as e:
            logger.error(f"Error getting enrolled class groups: {str(e)}")
            return []
    
    async def session_started(self, event):
        """
        Handle session_started event from channel layer.
        Called when teacher starts attendance session.
        
        Event structure:
        {
            "type": "session.started",
            "session_id": "...",
            "class_session_id": "...",
            "subject_code": "CS101",
            "subject_name": "Intro to CS",
            "template_id": "..."
        }
        """
        try:
            logger.info(f"✅ Consumer.session_started() called for student {self.user_id}")
            await self.send(json.dumps({
                'type': 'session_started',
                'session_id': event.get('session_id'),
                'class_session_id': event.get('class_session_id'),
                'subject_code': event.get('subject_code'),
                'subject_name': event.get('subject_name', ''),
                'template_id': event.get('template_id'),
                'message': f"🔴 {event.get('subject_code')} session started! Click to mark attendance.",
                'timestamp': timezone.now().isoformat()
            }))
            logger.info(f"✅ Sent session_started notification to student {self.user_id}")
        except Exception as e:
            logger.error(f"Error sending session_started notification: {str(e)}")
    
    async def session_ended(self, event):
        """
        Handle session_ended event from channel layer.
        Called when teacher ends attendance session.
        
        Event structure:
        {
            "type": "session.ended",
            "session_id": "...",
            "class_session_id": "...",
            "subject_code": "CS101",
            "marked_count": 25,
            "absent_count": 10
        }
        """
        try:
            await self.send(json.dumps({
                'type': 'session_ended',
                'session_id': event.get('session_id'),
                'class_session_id': event.get('class_session_id'),
                'subject_code': event.get('subject_code'),
                'marked_count': event.get('marked_count', 0),
                'absent_count': event.get('absent_count', 0),
                'message': f"✅ {event.get('subject_code')} session ended.",
                'timestamp': timezone.now().isoformat()
            }))
            logger.debug(f"Sent session_ended notification to {self.user_id}")
        except Exception as e:
            logger.error(f"Error sending session_ended notification: {str(e)}")
    
    async def attendance_marked(self, event):
        """
        Handle attendance_marked event.
        Called when student's attendance has been marked (self or ML).
        
        Event structure:
        {
            "type": "attendance.marked",
            "session_id": "...",
            "class_session_id": "...",
            "subject_code": "CS101",
            "status": "PRESENT",
            "confidence": 0.92
        }
        """
        try:
            await self.send(json.dumps({
                'type': 'attendance_marked',
                'session_id': event.get('session_id'),
                'class_session_id': event.get('class_session_id'),
                'subject_code': event.get('subject_code'),
                'status': event.get('status', 'UNKNOWN'),
                'confidence': round(event.get('confidence', 0.0), 3),
                'message': f"✅ {event.get('subject_code')} marked as {event.get('status')} ({round(event.get('confidence', 0.0) * 100, 0):.0f}%)",
                'timestamp': timezone.now().isoformat()
            }))
            logger.debug(f"Sent attendance_marked notification to {self.user_id}")
        except Exception as e:
            logger.error(f"Error sending attendance_marked notification: {str(e)}")
