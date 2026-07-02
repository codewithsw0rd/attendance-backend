from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Count, Q, Avg
from academics.models import ClassSession
from ..models import Attendance, AttendanceLog
from core.utils.custom_perms import IsClientUser


class AnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [IsClientUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            return Response({
                'recognitionStats': self._get_recognition_stats(),
                'attendanceTrends': self._get_attendance_trends(),
                'departmentComparison': self._get_department_comparison(),
                'timeSlotDistribution': self._get_time_slot_distribution(),
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'detail': f'Error fetching analytics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def recognition_stats(self, request):
        try:
            stats = self._get_recognition_stats()
            stats['timeSeriesData'] = self._get_recognition_time_series(days=30)
            return Response(stats, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'detail': f'Error fetching recognition stats: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def attendance_trends(self, request):
        try:
            days = int(request.query_params.get('days', 180))
            interval = request.query_params.get('interval', 'daily')

            return Response({
                'trends': self._get_attendance_trends(days=days, interval=interval),
                'daysAnalyzed': days,
                'interval': interval,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'detail': f'Error fetching attendance trends: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_recognition_stats(self):
        successful = AttendanceLog.objects.filter(
            liveness_passed='PASS',
            face_confidence__gte=0.8
        ).count()

        low_confidence = AttendanceLog.objects.filter(
            liveness_passed='PASS',
            face_confidence__lt=0.8
        ).count()

        failed = AttendanceLog.objects.filter(
            liveness_passed__in=['FAIL', 'UNKNOWN']
        ).count()

        total = successful + low_confidence + failed
        success_rate = round((successful / total * 100) if total > 0 else 0, 1)

        avg_confidence = AttendanceLog.objects.filter(
            liveness_passed='PASS'
        ).aggregate(avg=Avg('face_confidence'))['avg'] or 0

        return {
            'successfulRecognitions': successful,
            'lowConfidence': low_confidence,
            'failedRecognitions': failed,
            'totalAttempts': total,
            'successRate': success_rate,
            'averageConfidence': round(avg_confidence, 3),
        }

    def _get_recognition_time_series(self, days=30):
        today = timezone.now().date()
        time_series = []

        for i in range(days - 1, -1, -1):
            date_obj = today - timedelta(days=i)

            successful = AttendanceLog.objects.filter(
                liveness_passed='PASS',
                face_confidence__gte=0.8,
                created_at__date=date_obj
            ).count()

            low_confidence = AttendanceLog.objects.filter(
                liveness_passed='PASS',
                face_confidence__lt=0.8,
                created_at__date=date_obj
            ).count()

            failed = AttendanceLog.objects.filter(
                liveness_passed__in=['FAIL', 'UNKNOWN'],
                created_at__date=date_obj
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
        today = timezone.now().date()
        trends = []
        step = 1 if interval == 'daily' else (7 if interval == 'weekly' else 30)

        for i in range(days - 1, -1, -step):
            date_obj = today - timedelta(days=i)

            if interval == 'daily':
                attendances = Attendance.objects.filter(marked_at__date=date_obj)
            else:
                end_date = date_obj + timedelta(days=step - 1)
                attendances = Attendance.objects.filter(
                    marked_at__date__gte=date_obj,
                    marked_at__date__lte=end_date
                )

            present = attendances.filter(status='PRESENT').count()
            total = attendances.count()
            rate = round((present / total * 100) if total > 0 else 0, 1)

            if total > 0:
                trends.append({
                    'date': date_obj.isoformat(),
                    'rate': rate,
                    'present': present,
                    'total': total,
                })

        return trends

    def _get_department_comparison(self):
        from accounts.models import StudentProfile

        departments = {}

        students = StudentProfile.objects.values('department').annotate(
            count=Count('id'),
            total_attendance=Count('attendances'),
            present_count=Count('attendances', filter=Q(attendances__status='PRESENT'))
        )

        for dept in students:
            department_name = dept['department'] or 'Unknown'
            total = dept['total_attendance']
            present = dept['present_count']
            rate = round((present / total * 100) if total > 0 else 0, 1)

            departments[department_name] = {
                'name': department_name,
                'rate': rate,
                'present': present,
                'total': total,
                'studentCount': dept['count'],
            }

        return sorted(
            departments.values(),
            key=lambda x: x['rate'],
            reverse=True
        )[:5]

    def _get_time_slot_distribution(self):
        today = timezone.now().date()
        slots = []

        time_slots = [
            ('08:00', '09:00', '8:00 - 9:00 AM'),
            ('09:00', '10:00', '9:00 - 10:00 AM'),
            ('10:00', '11:00', '10:00 - 11:00 AM'),
            ('11:00', '12:00', '11:00 - 12:00 PM'),
            ('13:00', '14:00', '1:00 - 2:00 PM'),
            ('14:00', '15:00', '2:00 - 3:00 PM'),
        ]

        for start, end, label in time_slots:
            start_hour, start_min = int(start.split(':')[0]), int(start.split(':')[1])
            end_hour, end_min = int(end.split(':')[0]), int(end.split(':')[1])

            start_dt = timezone.make_aware(
                datetime(today.year, today.month, today.day, start_hour, start_min)
            )
            end_dt = timezone.make_aware(
                datetime(today.year, today.month, today.day, end_hour, end_min)
            )

            slot_attendance = Attendance.objects.filter(
                marked_at__gte=start_dt,
                marked_at__lt=end_dt
            )

            present = slot_attendance.filter(status='PRESENT').count()
            total = slot_attendance.count()
            rate = int(round((present / total * 100) if total > 0 else 0))

            slots.append({
                'time': label,
                'rate': rate,
                'count': total,
                'present': present,
            })

        return slots
