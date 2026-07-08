"""
Celery tasks for the attendance app.
Handles async operations like automatic session starting.
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from datetime import datetime, timedelta

from .models import ClassSessionTemplate, AttendanceSession, ClassSession

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def auto_start_sessions(self):
    """
    Automatically start attendance sessions for active templates
    whose scheduled day and time match the current time.
    
    This task runs every minute and checks:
    1. Active templates
    2. Matching day of week
    3. Current time matches template start time (within 1 minute)
    4. No active session already running for this template
    
    Returns:
        dict: Task result with started_sessions count and details
    """
    try:
        logger.info("🔄 Auto-start sessions task started")
        
        now = timezone.now()
        current_date = now.date()
        current_time = now.time()
        current_day = now.weekday()  # 0=Monday, 6=Sunday
        
        logger.info(f"📅 Current time: {now} | Day: {current_day} | Time: {current_time}")
        
        # Get all active templates
        active_templates = ClassSessionTemplate.objects.filter(
            is_active=True,
            day_of_week=current_day,
        )
        
        logger.info(f"🔍 Found {active_templates.count()} active templates for today ({['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][current_day]})")
        
        started_count = 0
        started_sessions = []
        
        for template in active_templates:
            # Check if current time is within ±1 minute of template start time
            # This allows the scheduler to catch the session start even if it missed the exact minute
            template_start = template.start_time
            time_diff = _get_time_difference_minutes(current_time, template_start)
            
            logger.debug(f"📋 Template {template.id}: {template.subject.code} | Start: {template_start} | Time diff: {time_diff}min")
            
            # Only start if current time is within the start minute (±30 seconds buffer)
            if time_diff <= 0.5 and time_diff >= -0.5:  # ±30 seconds buffer
                logger.info(f"⏰ Template {template.id} ({template.subject.code}) matches current time")
                
                # Check if session already exists for today
                existing_session = AttendanceSession.objects.filter(
                    template=template,
                    session_date=current_date,
                    is_active=True,
                ).first()
                
                if existing_session:
                    logger.warning(f"⚠️  Session already exists for template {template.id} today")
                    continue
                
                try:
                    # Get or create ClassSession for today
                    class_session, created = ClassSession.objects.get_or_create(
                        subject=template.subject,
                        date=current_date,
                        defaults={
                            'class_name': f"{template.subject.code} - {template.get_day_of_week_display()}",
                            'start_time': template.start_time,
                            'end_time': template.end_time,
                        }
                    )
                    
                    logger.info(f"{'✨ Created' if created else '📌 Got'} ClassSession {class_session.id}")
                    
                    # Create attendance session
                    attendance_session = AttendanceSession.objects.create(
                        template=template,
                        class_session=class_session,
                        initiated_by=None,  # System-initiated (not by a teacher)
                        marked_students=[],
                        session_date=current_date,
                        session_time=template.start_time,
                        is_active=True,
                    )
                    
                    logger.info(f"✅ Created AttendanceSession {attendance_session.id}")
                    
                    # Broadcast session started notification to all enrolled students
                    try:
                        _broadcast_session_started(class_session, attendance_session)
                        logger.info(f"📢 Broadcasted session_started for class_session {class_session.id}")
                    except Exception as e:
                        logger.error(f"❌ Error broadcasting session: {str(e)}", exc_info=True)
                    
                    started_count += 1
                    started_sessions.append({
                        'template_id': template.id,
                        'session_id': str(attendance_session.id),
                        'subject': template.subject.code,
                        'start_time': str(template.start_time),
                    })
                    
                except Exception as e:
                    logger.error(f"❌ Error creating session for template {template.id}: {str(e)}", exc_info=True)
                    # Continue with next template instead of failing the entire task
                    continue
        
        result = {
            'started_sessions': started_count,
            'sessions': started_sessions,
            'timestamp': str(now),
        }
        
        logger.info(f"✅ Auto-start sessions completed: Started {started_count} sessions")
        return result
        
    except Exception as e:
        logger.error(f"❌ Critical error in auto_start_sessions: {str(e)}", exc_info=True)
        # Retry with exponential backoff
        retry_delay = min(2 ** self.request.retries, 600)  # Max 10 minutes
        raise self.retry(exc=e, countdown=retry_delay)


def _get_time_difference_minutes(time1, time2):
    """
    Calculate the difference between two time objects in minutes.
    Returns positive if time1 > time2, negative if time1 < time2.
    
    Args:
        time1: datetime.time object
        time2: datetime.time object
    
    Returns:
        float: Difference in minutes
    """
    # Convert times to minutes since midnight
    minutes1 = time1.hour * 60 + time1.minute + time1.second / 60
    minutes2 = time2.hour * 60 + time2.minute + time2.second / 60
    return minutes1 - minutes2


def _broadcast_session_started(class_session, attendance_session):
    """
    Broadcast session started notification to all enrolled students via WebSocket.
    
    Args:
        class_session: ClassSession object
        attendance_session: AttendanceSession object
    """
    try:
        channel_layer = get_channel_layer()
        group_name = f'session_students_{class_session.id}'
        
        message_data = {
            'type': 'session.started',
            'session_id': str(attendance_session.id),
            'class_session_id': str(class_session.id),
            'subject_code': class_session.subject.code,
            'subject_name': class_session.subject.name,
            'template_id': str(attendance_session.template.id) if attendance_session.template else None,
            'auto_started': True,  # Flag to indicate system-initiated
        }
        
        logger.debug(f"🔌 Broadcasting to group '{group_name}': {message_data}")
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            message_data
        )
        
        logger.debug(f"✅ Message broadcast successful")
        
    except Exception as e:
        logger.error(f"❌ Error in _broadcast_session_started: {str(e)}", exc_info=True)
        raise
