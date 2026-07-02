from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q, F, Case, When, IntegerField
from datetime import datetime, timedelta
from accounts.models import UserType
from academics.models import Enrollment, ClassSession
from ..models import Attendance
from core.utils.custom_perms import IsClientUser


class StudentDashboardViewSet(viewsets.ViewSet):
    """
    Student-specific dashboard endpoints.
    Provides personalized attendance analytics and course data.
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def overall_stats(self, request):
        """
        Get overall attendance statistics for current student.
        
        Returns:
            - semester_attendance_rate: Overall attendance percentage
            - total_classes: Total classes the student is enrolled in
            - classes_attended: Number of classes attended (PRESENT)
            - classes_missed: Number of classes missed (ABSENT)
            - streak: Current consecutive present days
        """
        try:
            if request.user.user_type != UserType.STUDENT:
                return Response(
                    {'detail': 'Only students can access their dashboard'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get student attendance records
            attendance_records = Attendance.objects.filter(
                student__user=request.user
            )
            
            total_classes = attendance_records.count()
            classes_attended = attendance_records.filter(status='PRESENT').count()
            classes_missed = attendance_records.filter(status='ABSENT').count()
            
            # Calculate attendance rate
            attendance_rate = (classes_attended / total_classes * 100) if total_classes > 0 else 0
            
            # Calculate streak (consecutive present days)
            streak = 0
            recent_records = attendance_records.order_by('-marked_at')[:30]
            current_date = None
            
            for record in recent_records:
                record_date = record.marked_at.date()
                if current_date is None:
                    current_date = record_date
                
                if record_date != current_date:
                    # New date, check if streak continues
                    if record.status != 'PRESENT':
                        break
                    streak += 1
                    current_date = record_date
                elif record.status == 'PRESENT':
                    # Same date, mark as present
                    if current_date == record_date and streak == 0:
                        streak = 1
            
            return Response({
                'semester_attendance_rate': round(attendance_rate, 2),
                'total_classes': total_classes,
                'classes_attended': classes_attended,
                'classes_missed': classes_missed,
                'streak': streak,
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'detail': f'Error fetching overall stats: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def course_attendance(self, request):
        """
        Get per-course attendance breakdown.
        
        Returns array of:
            - subject_name: Subject name
            - subject_code: Subject code
            - teacher_name: Teacher name
            - total_classes: Total classes in this course
            - classes_attended: Classes attended in this course
            - classes_missed: Classes missed in this course
            - attendance_rate: Attendance percentage for this course
        """
        try:
            if request.user.user_type != UserType.STUDENT:
                return Response(
                    {'detail': 'Only students can access their dashboard'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get student's enrollments
            enrollments = Enrollment.objects.filter(
                student__user=request.user
            ).select_related('subject', 'subject__teacher', 'subject__teacher__user')
            
            course_data = []
            
            for enrollment in enrollments:
                subject = enrollment.subject
                
                # Get attendance records for this subject
                subject_attendance = Attendance.objects.filter(
                    student__user=request.user,
                    class_session__subject=subject
                )
                
                total = subject_attendance.count()
                attended = subject_attendance.filter(status='PRESENT').count()
                missed = subject_attendance.filter(status='ABSENT').count()
                rate = (attended / total * 100) if total > 0 else 0
                
                # Get teacher name
                teacher_name = ''
                if subject.teacher and subject.teacher.user:
                    teacher_name = f"{subject.teacher.user.first_name} {subject.teacher.user.last_name}".strip()
                    if not teacher_name:
                        teacher_name = subject.teacher.user.email
                
                course_data.append({
                    'subject_id': str(subject.id),
                    'subject_name': subject.name,
                    'subject_code': subject.code,
                    'teacher_name': teacher_name,
                    'total_classes': total,
                    'classes_attended': attended,
                    'classes_missed': missed,
                    'attendance_rate': round(rate, 2),
                })
            
            return Response(course_data, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'detail': f'Error fetching course attendance: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def upcoming_classes(self, request):
        """
        Get upcoming class sessions for current student.
        
        Query Parameters:
            - days: Number of days to look ahead (default: 7)
        
        Returns array of:
            - class_session_id: Session ID
            - class_name: Class name
            - subject_name: Subject name
            - subject_code: Subject code
            - date: Session date
            - start_time: Start time
            - end_time: End time
            - teacher_name: Teacher name
            - room: Room number/name
        """
        try:
            if request.user.user_type != UserType.STUDENT:
                return Response(
                    {'detail': 'Only students can access their dashboard'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            days_ahead = int(request.query_params.get('days', 7))
            today = datetime.now().date()
            future_date = today + timedelta(days=days_ahead)
            
            # Get student's enrolled subjects
            enrolled_subjects = Enrollment.objects.filter(
                student__user=request.user
            ).values_list('subject_id', flat=True)
            
            # Get upcoming class sessions
            upcoming = ClassSession.objects.filter(
                subject_id__in=enrolled_subjects,
                date__gte=today,
                date__lte=future_date
            ).select_related(
                'subject',
                'subject__teacher',
                'subject__teacher__user'
            ).order_by('date', 'start_time')
            
            classes_data = []
            
            for session in upcoming:
                subject = session.subject
                teacher_name = ''
                
                if subject.teacher and subject.teacher.user:
                    teacher_name = f"{subject.teacher.user.first_name} {subject.teacher.user.last_name}".strip()
                    if not teacher_name:
                        teacher_name = subject.teacher.user.email
                
                classes_data.append({
                    'class_session_id': str(session.id),
                    'class_name': session.class_name,
                    'subject_name': subject.name,
                    'subject_code': subject.code,
                    'date': session.date.isoformat(),
                    'start_time': session.start_time.isoformat(),
                    'end_time': session.end_time.isoformat(),
                    'teacher_name': teacher_name,
                    'room': session.class_name,  # Using class_name as room identifier
                })
            
            return Response(classes_data, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'detail': f'Error fetching upcoming classes: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def attendance_history(self, request):
        """
        Get student's attendance history with filtering and pagination.
        
        Query Parameters:
            - search: Search by subject name or code (optional)
            - subject_id: Filter by specific subject (optional)
            - status: Filter by PRESENT or ABSENT (optional)
            - start_date: Filter from date YYYY-MM-DD (optional)
            - end_date: Filter to date YYYY-MM-DD (optional)
            - sort_by: subject|date|status (default: date)
            - sort_order: asc|desc (default: desc)
            - page: Page number (default: 1)
            - page_size: Items per page (default: 10)
        
        Returns: Paginated attendance records with details
        """
        try:
            if request.user.user_type != UserType.STUDENT:
                return Response(
                    {'detail': 'Only students can access their history'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get query parameters
            search_query = request.query_params.get('search', '').strip()
            subject_id = request.query_params.get('subject_id', '').strip()
            status_filter = request.query_params.get('status', '').strip()
            start_date_str = request.query_params.get('start_date', '').strip()
            end_date_str = request.query_params.get('end_date', '').strip()
            sort_by = request.query_params.get('sort_by', 'date')
            sort_order = request.query_params.get('sort_order', 'desc')
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 10))
            
            # Build queryset
            queryset = Attendance.objects.filter(
                student__user=request.user
            ).select_related(
                'class_session',
                'class_session__subject',
                'class_session__subject__teacher',
                'class_session__subject__teacher__user'
            )
            
            # Apply search filter
            if search_query:
                queryset = queryset.filter(
                    Q(class_session__subject__name__icontains=search_query) |
                    Q(class_session__subject__code__icontains=search_query)
                )
            
            # Apply subject filter
            if subject_id:
                queryset = queryset.filter(class_session__subject_id=subject_id)
            
            # Apply status filter
            if status_filter and status_filter in ['PRESENT', 'ABSENT']:
                queryset = queryset.filter(status=status_filter)
            
            # Apply date range filters
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    queryset = queryset.filter(marked_at__date__gte=start_date)
                except ValueError:
                    pass
            
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                    queryset = queryset.filter(marked_at__date__lte=end_date)
                except ValueError:
                    pass
            
            # Apply sorting
            reverse_sort = sort_order.lower() == 'desc'
            
            if sort_by == 'subject':
                queryset = queryset.order_by(
                    f"{'-' if reverse_sort else ''}class_session__subject__name"
                )
            elif sort_by == 'status':
                queryset = queryset.order_by(
                    f"{'-' if reverse_sort else ''}status"
                )
            else:  # date (default)
                queryset = queryset.order_by(
                    f"{'-' if reverse_sort else ''}marked_at"
                )
            
            # Get total count before pagination
            total_count = queryset.count()
            
            # Apply pagination
            total_pages = (total_count + page_size - 1) // page_size
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_records = queryset[start_idx:end_idx]
            
            # Build response data
            records_data = []
            
            for attendance in paginated_records:
                subject = attendance.class_session.subject
                teacher_name = ''
                
                if subject.teacher and subject.teacher.user:
                    teacher_name = f"{subject.teacher.user.first_name} {subject.teacher.user.last_name}".strip()
                    if not teacher_name:
                        teacher_name = subject.teacher.user.email
                
                records_data.append({
                    'id': str(attendance.id),
                    'date': attendance.marked_at.date().isoformat(),
                    'time': attendance.marked_at.time().isoformat(),
                    'subject_name': subject.name,
                    'subject_code': subject.code,
                    'class_name': attendance.class_session.class_name,
                    'teacher_name': teacher_name,
                    'status': attendance.status,
                    'detection_confidence': round(attendance.detection_confidence, 3),
                })
            
            return Response({
                'records': records_data,
                'pagination': {
                    'current_page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': total_pages,
                },
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'detail': f'Error fetching attendance history: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
