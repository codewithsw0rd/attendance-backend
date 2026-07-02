from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import datetime, timedelta, date
from django.db.models import Count, Q, Avg, F
from accounts.models import StudentProfile, TeacherProfile
from academics.models import ClassSession
from ..models import Attendance, AttendanceLog
from core.utils.custom_perms import IsClientUser


class AnalyticsViewSet(viewsets.ViewSet):
    """
    Analytics and reporting endpoints.
    Provides aggregated data for analytics dashboards.
    """
    permission_classes = [IsClientUser]  # Admin only

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """
        Get comprehensive analytics overview including:
        - Recognition statistics
        - Attendance trends
        - Time slot distribution
        - Department breakdown
        """
        try:
            # 1. Recognition Statistics
            recognition_stats = self._get_recognition_stats()

            # 2. Attendance Trends (last 6 months for line chart)
            attendance_trends = self._get_attendance_trends()

            # 3. Department Comparison
            department_comparison = self._get_department_comparison()

            # 4. Attendance by Time Slot (today)
            time_slot_distribution = self._get_time_slot_distribution()

            return Response({
                'recognitionStats': recognition_stats,
                'attendanceTrends': attendance_trends,
                'departmentComparison': department_comparison,
                'timeSlotDistribution': time_slot_distribution,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'detail': f'Error fetching analytics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def recognition_stats(self, request):
        """
        Get face recognition performance statistics.
        
        Returns:
        {
            "successfulRecognitions": 12847,
            "lowConfidence": 284,
            "failedRecognitions": 146,
            "totalAttempts": 13277,
            "successRate": 96.8,
            "averageConfidence": 0.948,
            "timeSeriesData": [
                {"date": "2024-01-15", "successful": 145, "lowConfidence": 4, "failed": 2}
            ]
        }
        """
        try:
            stats = self._get_recognition_stats()
            
            # Add time series data
            time_series = self._get_recognition_time_series(days=30)
            stats['timeSeriesData'] = time_series

            return Response(stats, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'detail': f'Error fetching recognition stats: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def attendance_trends(self, request):
        """
        Get detailed attendance trends.
        
        Query params:
        - days: number of days to analyze (default: 180)
        - interval: 'daily', 'weekly', or 'monthly' (default: daily)
        """
        try:
            days = int(request.query_params.get('days', 180))
            interval = request.query_params.get('interval', 'daily')

            trends = self._get_attendance_trends(days=days, interval=interval)

            return Response({
                'trends': trends,
                'daysAnalyzed': days,
                'interval': interval,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'detail': f'Error fetching attendance trends: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_recognition_stats(self):
        """Calculate face recognition performance statistics"""
        # Count successful recognitions (with high confidence)
        successful = AttendanceLog.objects.filter(
            liveness_status='PASS',
            confidence_score__gte=0.8
        ).count()

        # Count low confidence (pass but low score)
        low_confidence = AttendanceLog.objects.filter(
            liveness_status='PASS',
            confidence_score__lt=0.8
        ).count()

        # Count failed recognitions
        failed = AttendanceLog.objects.filter(
            liveness_status__in=['FAIL', 'REJECTED']
        ).count()

        total = successful + low_confidence + failed
        success_rate = (successful / total * 100) if total > 0 else 0
        success_rate = round(success_rate, 1)

        # Get average confidence
        avg_confidence = AttendanceLog.objects.filter(
            liveness_status='PASS'
        ).aggregate(avg=Avg('confidence_score'))['avg'] or 0
        avg_confidence = round(avg_confidence, 3)

        return {
            'successfulRecognitions': successful,
            'lowConfidence': low_confidence,
            'failedRecognitions': failed,
            'totalAttempts': total,
            'successRate': success_rate,
            'averageConfidence': avg_confidence,
        }

    def _get_recognition_time_series(self, days=30):
        """Get recognition stats per day for the last N days"""
        today = timezone.now().date()
        time_series = []

        for i in range(days - 1, -1, -1):
            date_obj = today - timedelta(days=i)

            successful = AttendanceLog.objects.filter(
                liveness_status='PASS',
                confidence_score__gte=0.8,
                timestamp__date=date_obj
            ).count()

            low_confidence = AttendanceLog.objects.filter(
                liveness_status='PASS',
                confidence_score__lt=0.8,
                timestamp__date=date_obj
            ).count()

            failed = AttendanceLog.objects.filter(
                liveness_status__in=['FAIL', 'REJECTED'],
                timestamp__date=date_obj
            ).count()

            if successful + low_confidence + failed > 0:
                time_series.append({
                    'date': date_obj.isoformat(),
                    'successful': successful,
                    'lowConfidence': low_confidence,
                    'failed': failed,
                })

        return time_series

    def _get_attendance_trends(self, days=180, interval='daily'):
        """Calculate attendance trends"""
        today = timezone.now().date()
        trends = []

        if interval == 'daily':
            step = 1
        elif interval == 'weekly':
            step = 7
        elif interval == 'monthly':
            step = 30
        else:
            step = 1

        for i in range(days - 1, -1, -step):
            date_obj = today - timedelta(days=i)

            # Get attendance for this period
            if interval == 'daily':
                attendances = Attendance.objects.filter(
                    marked_at__date=date_obj
                )
            else:
                end_date = date_obj + timedelta(days=step - 1)
                attendances = Attendance.objects.filter(
                    marked_at__date__gte=date_obj,
                    marked_at__date__lte=end_date
                )

            present = attendances.filter(status='PRESENT').count()
            total = attendances.count()

            rate = (present / total * 100) if total > 0 else 0
            rate = round(rate, 1)

            if total > 0:  # Only include days with data
                trends.append({
                    'date': date_obj.isoformat(),
                    'rate': rate,
                    'present': present,
                    'total': total,
                })

        return trends

    def _get_department_comparison(self):
        """Get average attendance rate by department"""
        from accounts.models import StudentProfile

        departments = {}

        # Get all students grouped by department
        students = StudentProfile.objects.values('department').annotate(
            count=Count('id'),
            total_attendance=Count('attendances'),
            present_count=Count('attendances', filter=Q(attendances__status='PRESENT'))
        )

        for dept in students:
            department_name = dept['department'] or 'Unknown'
            total = dept['total_attendance']
            present = dept['present_count']

            rate = (present / total * 100) if total > 0 else 0
            rate = round(rate, 1)

            departments[department_name] = {
                'name': department_name,
                'rate': rate,
                'present': present,
                'total': total,
                'studentCount': dept['count'],
            }

        # Convert to sorted list
        dept_list = sorted(
            departments.values(),
            key=lambda x: x['rate'],
            reverse=True
        )[:5]  # Top 5 departments

        return dept_list

    def _get_time_slot_distribution(self):
        """Get attendance distribution by time of day"""
        today = timezone.now().date()
        slots = []

        # Define time slots
        time_slots = [
            ('08:00', '09:00', '8:00 - 9:00 AM'),
            ('09:00', '10:00', '9:00 - 10:00 AM'),
            ('10:00', '11:00', '10:00 - 11:00 AM'),
            ('11:00', '12:00', '11:00 - 12:00 PM'),
            ('13:00', '14:00', '1:00 - 2:00 PM'),
            ('14:00', '15:00', '2:00 - 3:00 PM'),
        ]

        for start, end, label in time_slots:
            # Parse time
            start_hour = int(start.split(':')[0])
            start_min = int(start.split(':')[1])
            end_hour = int(end.split(':')[0])
            end_min = int(end.split(':')[1])

            # Create datetime objects for today
            start_dt = timezone.make_aware(
                datetime(today.year, today.month, today.day, start_hour, start_min)
            )
            end_dt = timezone.make_aware(
                datetime(today.year, today.month, today.day, end_hour, end_min)
            )

            # Get attendance for this slot
            slot_attendance = Attendance.objects.filter(
                marked_at__gte=start_dt,
                marked_at__lt=end_dt
            )

            present = slot_attendance.filter(status='PRESENT').count()
            total = slot_attendance.count()

            rate = (present / total * 100) if total > 0 else 0
            rate = round(rate, 0)

            slots.append({
                'time': label,
                'rate': int(rate),
                'count': total,
                'present': present,
            })

        return slots
