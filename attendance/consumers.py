"""
WebSocket consumer for real-time attendance streaming.
Handles continuous frame processing and face detection.
"""
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

logger = logging.getLogger(__name__)

# Maximum number of frames to wait before refreshing the embedding cache.
# Handles the edge case where a student enrolls mid-session.
_CACHE_REFRESH_INTERVAL = 300

# If the ML service (Render) takes longer than this many seconds, abort and
# immediately return empty detections so the stream recovers quickly when
# processing is too slow (cold start, network lag, etc.).
# Set to 8 seconds: Render cold start usually takes 5-8 seconds, we give it
# a bit of buffer but not too much to avoid user frustration.
_PROCESSING_TIMEOUT = 8.0

# Number of times to retry a frame if it times out
# (helps handle transient Render cold-starts)
_MAX_RETRIES = 1


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

        # ── Per-session embedding cache ────────────────────────────────────
        # Fetched once here and refreshed every _CACHE_REFRESH_INTERVAL frames
        # instead of being re-queried and re-serialised on every video frame.
        self._embeddings_cache: list[list[float]] = []
        self._student_ids_cache: list[str] = []
        self._cache_frame_count: int = 0
        # asyncio.Lock prevents concurrent ML calls without permanently locking
        # on Render timeouts (unlike a plain boolean flag).
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
        """Receive and process video frame

        Supports:
        - Binary frames (raw JPEG/PNG bytes)
        - JSON text frames: {"type": "frame", "data": "<data-url or base64>"}

        Uses a lock to prevent concurrent ML calls. If the ML service times out,
        we immediately return empty detections so the stream doesn't freeze.
        The next frame will be processed normally.
        """
        # Drop frame if still processing previous frame — prevents queue buildup
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
                frame_io = BytesIO(bytes_data)

            if frame_io is None:
                return

            # Process frame with retry logic for timeouts
            detections = None
            retry_count = 0

            while retry_count <= _MAX_RETRIES:
                try:
                    async with self._frame_lock:
                        detections = await asyncio.wait_for(
                            self.process_frame(frame_io),
                            timeout=_PROCESSING_TIMEOUT
                        )
                    break  # Success, exit retry loop
                except asyncio.TimeoutError:
                    retry_count += 1
                    if retry_count <= _MAX_RETRIES:
                        logger.warning(
                            f"ML timeout (attempt {retry_count}/{_MAX_RETRIES + 1}) "
                            f"for session {self.session_id}, retrying..."
                        )
                        # Reset stream position for retry
                        frame_io.seek(0)
                        # Brief delay before retry to let ML service recover
                        await asyncio.sleep(0.5)
                    else:
                        logger.warning(
                            f"ML frame timed out after {_MAX_RETRIES + 1} attempts "
                            f"for session {self.session_id}"
                        )
                        # Send empty faces so the frontend continues smoothly
                        # instead of showing stale boxes for 2 more seconds
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

            if detections is None:
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
    def _load_embeddings(self):
        """
        Batch-fetch all enrolled students' embeddings for this session's subject
        in exactly TWO DB queries (one for enrollments, one for embeddings via
        prefetch_related) instead of one query per student.
        """
        try:
            session = AttendanceSession.objects.select_related(
                'class_session__subject'
            ).get(id=UUID(self.session_id), ended_at=None)
        except AttendanceSession.DoesNotExist:
            return [], []

        # Single query: all enrolled FaceData objects with their embeddings.
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

        for face_data in face_data_qs:
            for emb in face_data.embeddings.all():
                stored_embeddings.append(emb.embedding)
                student_ids.append(str(face_data.student.user.id))

        return stored_embeddings, student_ids

    async def _refresh_embedding_cache(self):
        """Reload the embedding cache from the database."""
        embeddings, student_ids = await self._load_embeddings()
        self._embeddings_cache = embeddings
        self._student_ids_cache = student_ids
        self._cache_frame_count = 0
        logger.debug(
            f"Embedding cache refreshed for session {self.session_id}: "
            f"{len(embeddings)} vectors across {len(set(student_ids))} students"
        )

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
    
    async def process_frame(self, frame_io):
        """
        Process a single video frame:
        1. Use cached embeddings (refreshed periodically)
        2. Call ML service for multi-face detection
        3. Deduplicate: only create Attendance if not already marked
        4. Return newly detected students
        """
        # ─── Periodic cache refresh ───────────────────────────────────────
        self._cache_frame_count += 1
        if self._cache_frame_count >= _CACHE_REFRESH_INTERVAL:
            await self._refresh_embedding_cache()

        stored_embeddings = self._embeddings_cache
        student_ids = self._student_ids_cache

        if not stored_embeddings:
            logger.warning(f"No enrolled students with registered faces for session {self.session_id}")
            return {
                'newly_detected': [],
                'ml_status': 'no_enrolled_faces',
                'total_faces_detected': 0,
                'enrolled_embeddings': 0,
                'faces': [],
            }

        try:
            session = await database_sync_to_async(
                AttendanceSession.objects.select_related(
                    'class_session', 'class_session__subject'
                ).get
            )(id=UUID(self.session_id), ended_at=None)
        except AttendanceSession.DoesNotExist:
            logger.error(f"Session {self.session_id} not found or already ended")
            raise Exception("Session not found or already ended")
            
        # ─── Call ML service for multi-face detection ──────────────────
        try:
            ml_result = await database_sync_to_async(process_continuous_detection)(
                frame_io,
                stored_embeddings,
                student_ids,
                session_id=str(session.id)
            )
        except MLServiceError as e:
            logger.error(f"ML Service error: {str(e)}")
            raise Exception(f"ML Service Error: {str(e)}")

        # ─── Process detections and deduplicate ────────────────────────
        newly_detected = []

        for detection in ml_result.get('detections', []):
            student_id = detection.get('student_id')
            confidence = detection.get('confidence', 0.0)
            distance = detection.get('distance', 0.0)

            if not student_id:
                continue

            # Use get_or_create guarded by the UniqueConstraint — avoids the
            # race condition of checking marked_students in memory.
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
                # Refresh cache so the newly-marked student is included
                # in session.marked_students on future frames.
                await self._refresh_embedding_cache()

        return {
            'newly_detected': newly_detected,
            'ml_status': ml_result.get('status'),
            'total_faces_detected': ml_result.get('total_faces_detected', 0),
            'enrolled_embeddings': len(stored_embeddings),
            'nearest_distance': ml_result.get('nearest_distance'),
            'faces': ml_result.get('faces', []),
        }

    def _mark_student_present(self, session, student_id: str, confidence: float) -> dict | None:
        """
        Atomically create an Attendance record for the student if not already marked.
        Returns student info dict on first mark, None if already marked this session.
        Uses DB-level get_or_create to be race-condition-safe.
        """
        try:
            enrollment = Enrollment.objects.select_related(
                'student__user'
            ).get(
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
            # Already marked in a previous frame
            return None

        # Keep marked_students in sync (best-effort, informational only —
        # the UniqueConstraint is the real guard against duplicates).
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