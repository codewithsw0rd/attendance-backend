from django.contrib import admin
from .models import FaceData, Attendance, AttendanceLog


@admin.register(FaceData)
class FaceDataAdmin(admin.ModelAdmin):
    list_display = ['student', 'is_enrolled', 'created_at']
    list_filter = ['is_enrolled', 'created_at']
    search_fields = ['student__user__email', 'student__roll_number']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'class_session', 'status', 'marked_at']
    list_filter = ['status', 'marked_at', 'class_session']
    search_fields = ['student__user__email', 'student__roll_number', 'class_session__class_name']
    readonly_fields = ['created_at', 'updated_at', 'marked_at']


@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ['attendance', 'face_confidence', 'liveness_passed', 'is_suspicious', 'created_at']
    list_filter = ['liveness_passed', 'is_suspicious', 'created_at']
    search_fields = ['attendance__student__user__email']
    readonly_fields = ['created_at', 'updated_at']
