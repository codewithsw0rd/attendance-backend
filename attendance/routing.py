"""
WebSocket URL routing for attendance module.
Maps WebSocket paths to consumers.
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Teacher attendance streaming
    re_path(
        r'ws/attendance/stream/(?P<session_id>[\w-]+)/$',
        consumers.AttendanceStreamConsumer.as_asgi(),
        name='attendance_stream'
    ),
    
    # Student real-time notifications
    re_path(
        r'ws/notifications/$',
        consumers.StudentNotificationConsumer.as_asgi(),
        name='student_notifications'
    ),
]