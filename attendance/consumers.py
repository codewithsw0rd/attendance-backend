"""
WebSocket consumer for real-time attendance streaming.
Handles continuous frame processing and face detection.
"""
import json
import logging
from io import BytesIO
import base64
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from uuid import UUID

from attendance.models import AttendanceSession, Attendance, FaceData, FaceEmbedding
from academics.models import Enrollment
from attendance.ml_client import process_continuous_detection, MLServiceError
from academics.models import ClassSession

logger = logging.getLogger(__name__)


class AttendanceStreamConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time attendance streaming.
    
    Flow:
    1. Client connects: ws://host/ws/attendance/stream/{session_id}/
    2. Consumer validates session and sends connection confirmation
    3. Client sends video frames as binary data
    4. Consumer processes frame, detects faces, deduplicates
    5. Consumer sends back detected students
    6. Repeat until client disconnects or session ends
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.session_group_name = f'attendance_session_{self.session_id}'
        user = self.scope['user']

        if not user.is_authenticated:
            logger.warning(f"WebSocket auth failed for session {self.session_id}")
            await self.close(code=4003)
            return

        session_data = await self.get_session_data()
        if not session_data:
            await self.close(code=4004)
            return

        if user.id != session_data['initiated_by_id']:
            logger.warning(
                f"WebSocket user {user.id} is not initiator "
                f"{session_data['initiated_by_id']} for session {self.session_id}"
            )
            await self.close(code=4003)
            return

        try:
            await self.channel_layer.group_add(self.session_group_name, self.channel_name)
        except Exception as e:
            logger.error(f"Channel layer group_add failed: {str(e)}")
            await self.close(code=1011)
            return

        await self.accept()
        
        logger.info(f"WebSocket connected for session {self.session_id}")
        await self.send(json.dumps({
            'type': 'connection_established',
            'session_id': str(self.session_id),
            'status': 'connected',
            'message': 'Ready to receive frames'
        }))
    
    async def receive(self, text_data=None, bytes_data=None):
        """Receive and process video frame
        
        Supports:
        - Binary frames (raw JPEG/PNG bytes)
        - JSON text frames: {"type": "frame", "data": "<data-url or base64>"}
        """
        try:
            frame_io = None

            if text_data:
                try:
                    message = json.loads(text_data)
                    if message.get('type') != 'frame' or 'data' not in message:
                        return
                    data_url = message['data']
                    # Strip 'data:image/jpeg;base64,' prefix if present
                    if isinstance(data_url, str) and ',' in data_url:
                        _, b64_data = data_url.split(',', 1)
                    else:
                        b64_data = data_url
                    frame_bytes = base64.b64decode(b64_data)
                    frame_io = BytesIO(frame_bytes)
                except Exception as e:
                    logger.error(f"Error decoding text frame: {str(e)}")
                    await self.send(json.dumps({
                        'type': 'error',
                        'detail': 'Invalid frame payload'
                    }))
                    return

            elif bytes_data:
                # Frame received as binary; process it directly
                frame_io = BytesIO(bytes_data)

            if frame_io is None:
                return

            detections = await self.process_frame(frame_io)

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
            logger.error(f"Error processing frame: {str(e)}")
            await self.send(json.dumps({
                'type': 'error',
                'detail': str(e)
            }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'session_group_name'):
            try:
                await self.channel_layer.group_discard(
                    self.session_group_name,
                    self.channel_name
                )
            except Exception as e:
                logger.error(f"Channel layer group_discard failed: {str(e)}")
        logger.info(f"WebSocket disconnected for session {self.session_id} with code {close_code}")

    @database_sync_to_async
    def get_session_data(self):
        """Get active session metadata without lazy FK access in async code."""
        try:
            session = AttendanceSession.objects.select_related('initiated_by').get(
                id=UUID(self.session_id),
                ended_at=None
            )
            return {
                'id': str(session.id),
                'initiated_by_id': session.initiated_by_id,
            }
        except AttendanceSession.DoesNotExist:
            logger.error(f"Session not found: {self.session_id}")
            return None
        except Exception as e:
            logger.error(f"Session lookup failed: {str(e)}")
            return None

    @database_sync_to_async
    def get_session(self):
        """Get AttendanceSession, ensuring it's still active"""
        try:
            return AttendanceSession.objects.get(
                id=UUID(self.session_id),
                ended_at=None
            )
        except Exception as e:
            logger.error(f"Session not found: {str(e)}")
            return None
    
    @database_sync_to_async
    def process_frame(self, frame_io):
        """
        Process a single video frame:
        1. Get all enrolled students' embeddings
        2. Call ML service for multi-face detection
        3. Deduplicate: only create Attendance if not already marked
        4. Return newly detected students
        """
        try:
            session = AttendanceSession.objects.get(
                id=UUID(self.session_id),
                ended_at=None
            )
            class_session = session.class_session
            
            # ─── Get all enrolled students' embeddings ────────────────
            enrolled = Enrollment.objects.filter(
                subject=class_session.subject
            ).select_related('student', 'student__user')
            
            stored_embeddings = []
            student_ids = []
            
            for enrollment in enrolled:
                try:
                    face_data = FaceData.objects.get(
                        student=enrollment.student,
                        is_enrolled=True
                    )
                    embeddings = FaceEmbedding.objects.filter(
                        face_data=face_data
                    ).order_by('photo_number')
                    
                    for emb in embeddings:
                        stored_embeddings.append(emb.embedding)
                        student_ids.append(str(enrollment.student.user.id))
                except FaceData.DoesNotExist:
                    # Skip students without completed enrollment
                    pass
            
            if not stored_embeddings:
                logger.warning(f"No enrolled students with registered faces for session {self.session_id}")
                return {
                    'newly_detected': [],
                    'ml_status': 'no_enrolled_faces',
                    'total_faces_detected': 0,
                    'enrolled_embeddings': 0,
                    'faces': [],
                }
            
            # ─── Call ML service for multi-face detection ──────────────
            try:
                ml_result = process_continuous_detection(
                    frame_io,
                    stored_embeddings,
                    student_ids,
                    session_id=str(session.id)
                )
            except MLServiceError as e:
                logger.error(f"ML Service error: {str(e)}")
                raise Exception(f"ML Service Error: {str(e)}")
            
            # ─── Process detections and deduplicate ────────────────────
            newly_detected = []
            marked_student_ids = session.marked_students if session.marked_students else []
            
            for detection in ml_result.get('detections', []):
                student_id = detection.get('student_id')
                confidence = detection.get('confidence', 0.0)
                distance = detection.get('distance', 0.0)
                
                # Check if student already marked in this session
                if student_id and student_id not in marked_student_ids:
                    try:
                        # Get the enrollment to create attendance
                        enrollment = Enrollment.objects.get(
                            subject=class_session.subject,
                            student__user__id=UUID(student_id)
                        )
                        
                        # Create attendance record
                        Attendance.objects.create(
                            student=enrollment.student,
                            class_session=class_session,
                            attendance_session=session,
                            status='PRESENT',
                            frame_detected=timezone.now(),
                            detection_confidence=confidence
                        )
                        
                        # Add to session's marked list
                        marked_student_ids.append(student_id)
                        session.marked_students = marked_student_ids
                        session.save()
                        
                        # Prepare response for WebSocket clients
                        newly_detected.append({
                            'student_id': student_id,
                            'student_email': enrollment.student.user.email,
                            'student_name': f"{enrollment.student.first_name or ''} {enrollment.student.last_name or ''}".strip(),
                            'student_roll_number': enrollment.student.roll_number,
                            'confidence': round(confidence, 4),
                            'distance': round(distance, 6),
                            'marked_at': timezone.now().isoformat()
                        })
                        
                        logger.info(f"Student {student_id} marked present in session {self.session_id}")
                    except Enrollment.DoesNotExist:
                        logger.warning(f"Enrollment not found for student {student_id}")
                        pass
                    except Exception as e:
                        logger.error(f"Error creating attendance: {str(e)}")
                        pass
            
            return {
                'newly_detected': newly_detected,
                'ml_status': ml_result.get('status'),
                'total_faces_detected': ml_result.get('total_faces_detected', 0),
                'enrolled_embeddings': len(stored_embeddings),
                'nearest_distance': ml_result.get('nearest_distance'),
                'faces': ml_result.get('faces', []),
            }
            
        except Exception as e:
            logger.error(f"Frame processing error: {str(e)}")
            raise