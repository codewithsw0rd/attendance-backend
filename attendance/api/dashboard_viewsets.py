from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Count, Q
from accounts.models import UserType, StudentProfile, TeacherProfile
from academics.models import Enrollment, ClassSession, Subject
from ..models import Attendance
from core.utils.custom_perms import IsClientUser

# Attendance status constants
ATTENDANCE_STATUS_PRESENT = 'PRESENT'
ATTENDANCE_STATUS_ABSENT = 'ABSENT'
ATTENDANCE_STATUS_LATE = 'LATE'
ATTENDANCE_STATUS_EXCUSED = 'EXCUSED'
ATTENDANCE_STATUS_PRESENT_ONLINE = 'PRESENT_ONLINE'

# Statuses that count as "attended"
ATTENDED_STATUSES = {ATTENDANCE_STATUS_PRESENT, ATTENDANCE_STATUS_LATE, ATTENDANCE_STATUS_PRESENT_ONLINE}


class DashboardViewSet(viewsets.ViewSet):
    """
    Admin dashboard statistics endpoint.
    Provides pre-calculated stats for efficient dashboard rendering.
    """
    permission_classes = [IsClientUser]  # Admin only

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get all dashboard stats in one call.
        
        Response:
        {
            "totalStudents": 1234,
            "totalTeachers": 56,
            "totalClasses": 24,
            "todayAttendanceRate": 94.2,
            "weeklyAttendance": [
                {"day": "Mon", "date": "2024-01-15", "rate": 88},
                ...
            ],
            "recentActivity": [
                {
                    "id": "uuid",
                    "time": "09:15 AM",
                    "student": "John Doe",
                    "action": "Checked In",
                    "class": "CS101-A",
                    "status": "Present",
                    "timestamp": "2024-01-15T09:15:00Z"
                },
                ...
            ]
        }
        """
        try:
            # 1. Total Students Count
            total_students = StudentProfile.objects.filter(
                user__is_active=True
            ).count()

            # 2. Total Teachers Count
            total_teachers = TeacherProfile.objects.filter(
                user__is_active=True
            ).count()

            # 3. Total Classes Count
            total_classes = ClassSession.objects.all().count()

            # 4. Today's Attendance Rate
            today = timezone.now().date()
            today_attendance = Attendance.objects.filter(
                marked_at__date=today
            )

            today_present = today_attendance.filter(status__in=ATTENDED_STATUSES).count()
            today_total = today_attendance.count()
            today_rate = (today_present / today_total * 100) if today_total > 0 else 0
            today_rate = round(today_rate, 1)

            # 5. Weekly Attendance Trend (last 7 days)
            weekly_attendance = self._calculate_weekly_trend()

            # 6. Recent Activity (last 10 records)
            recent_activity = self._get_recent_activity(limit=10)

            return Response({
                'totalStudents': total_students,
                'totalTeachers': total_teachers,
                'totalClasses': total_classes,
                'todayAttendanceRate': today_rate,
                'weeklyAttendance': weekly_attendance,
                'recentActivity': recent_activity,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'detail': f'Error fetching dashboard stats: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _calculate_weekly_trend(self):
        """Calculate attendance rate for each of the last 7 days"""
        today = timezone.now().date()
        weekly_data = []
        day_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            
            # Get attendance for this day
            day_attendance = Attendance.objects.filter(
                marked_at__date=date
            )

            present_count = day_attendance.filter(status__in=ATTENDED_STATUSES).count()
            total_count = day_attendance.count()

            # Calculate rate
            rate = (present_count / total_count * 100) if total_count > 0 else 0
            rate = round(rate, 0)  # Round to nearest integer for chart

            # Get day label
            day_index = date.weekday()
            day_label = day_labels[(day_index + 1) % 7]  # Adjust for Mon start

            weekly_data.append({
                'day': day_label,
                'date': date.isoformat(),
                'rate': int(rate)
            })

        return weekly_data

    def _get_recent_activity(self, limit=10):
        """Get recent attendance activity with nested details"""
        from django.core.paginator import Paginator

        attendances = (
            Attendance.objects
            .select_related(
                'student',
                'student__user',
                'class_session',
                'class_session__subject'
            )
            .order_by('-marked_at')[:limit]
        )

        activity_list = []
        for attendance in attendances:
            marked_at = attendance.marked_at
            time_str = marked_at.strftime('%I:%M %p')  # 09:15 AM format

            # Determine action based on status
            if attendance.status == 'PRESENT':
                action = 'Checked In'
            elif attendance.status == 'ABSENT':
                action = 'Absent'
            else:  # LATE or other
                action = 'Late Arrival'

            # Get student name
            student_name = f"{attendance.student.user.first_name or ''} {attendance.student.user.last_name or ''}".strip()
            if not student_name:
                student_name = attendance.student.user.email

            activity_list.append({
                'id': str(attendance.id),
                'time': time_str,
                'student': student_name,
                'action': action,
                'class': attendance.class_session.class_name or 'N/A',
                'status': 'Present' if attendance.status == 'PRESENT' else 'Late' if attendance.status == 'LATE' else 'Absent',
                'timestamp': attendance.marked_at.isoformat()
            })

        return activity_list
