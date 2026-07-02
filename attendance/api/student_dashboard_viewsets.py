from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from datetime import datetime, timedelta
from django.utils import timezone
from accounts.models import UserType
from academics.models import Enrollment, ClassSession
from ..models import Attendance, AttendanceSession


class StudentDashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _check_student(self, request):
        return request.user.user_type == UserType.STUDENT

    def _get_teacher_name(self, teacher):
        if not teacher or not teacher.user:
            return ''
        first_name = (teacher.user.first_name or '').strip()
        last_name = (teacher.user.last_name or '').strip()
        full_name = f"{first_name} {last_name}".strip()
        return full_name if full_name else teacher.user.email

    def _parse_date(self, date_str):
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return None

    @action(detail=False, methods=['get'])
    def overall_stats(self, request):
        try:
            if not self._check_student(request):
                return Response(
                    {'detail': 'Only students can access their dashboard'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            attendance_records = Attendance.objects.filter(
                student__user=request.user
            )
            
            total_classes = attendance_records.count()
            classes_attended = attendance_records.filter(status='PRESENT').count()
            classes_missed = attendance_records.filter(status='ABSENT').count()
            attendance_rate = (classes_attended / total_classes * 100) if total_classes > 0 else 0
            
            streak = 0
            recent_records = attendance_records.order_by('-marked_at')[:30]
            current_date = None
            
            for record in recent_records:
                record_date = record.marked_at.date()
                if current_date is None:
                    current_date = record_date
                
                if record_date != current_date:
                    if record.status != 'PRESENT':
                        break
                    streak += 1
                    current_date = record_date
                elif record.status == 'PRESENT':
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
        try:
            if not self._check_student(request):
                return Response(
                    {'detail': 'Only students can access their dashboard'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            enrollments = Enrollment.objects.filter(
                student__user=request.user
            ).select_related('subject', 'subject__teacher', 'subject__teacher__user')
            
            course_data = []
            
            for enrollment in enrollments:
                subject = enrollment.subject
                
                subject_attendance = Attendance.objects.filter(
                    student__user=request.user,
                    class_session__subject=subject
                )
                
                total = subject_attendance.count()
                attended = subject_attendance.filter(status='PRESENT').count()
                missed = subject_attendance.filter(status='ABSENT').count()
                rate = (attended / total * 100) if total > 0 else 0
                
                course_data.append({
                    'subject_id': str(subject.id),
                    'subject_name': subject.name,
                    'subject_code': subject.code,
                    'teacher_name': self._get_teacher_name(subject.teacher),
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
        try:
            if not self._check_student(request):
                return Response(
                    {'detail': 'Only students can access their dashboard'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            days_ahead = int(request.query_params.get('days', 7))
            today = datetime.now().date()
            future_date = today + timedelta(days=days_ahead)
            
            enrolled_subjects = Enrollment.objects.filter(
                student__user=request.user
            ).values_list('subject_id', flat=True)
            
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
                
                classes_data.append({
                    'class_session_id': str(session.id),
                    'class_name': session.class_name,
                    'subject_name': subject.name,
                    'subject_code': subject.code,
                    'date': session.date.isoformat(),
                    'start_time': session.start_time.isoformat(),
                    'end_time': session.end_time.isoformat(),
                    'teacher_name': self._get_teacher_name(subject.teacher),
                    'room': session.class_name,
                })
            
            return Response(classes_data, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'detail': f'Error fetching upcoming classes: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def attendance_history(self, request):
        try:
            if not self._check_student(request):
                return Response(
                    {'detail': 'Only students can access their history'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            search_query = request.query_params.get('search', '').strip()
            subject_id = request.query_params.get('subject_id', '').strip()
            status_filter = request.query_params.get('status', '').strip()
            start_date_str = request.query_params.get('start_date', '').strip()
            end_date_str = request.query_params.get('end_date', '').strip()
            sort_by = request.query_params.get('sort_by', 'date')
            sort_order = request.query_params.get('sort_order', 'desc')
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 10))
            
            queryset = Attendance.objects.filter(
                student__user=request.user
            ).select_related(
                'class_session',
                'class_session__subject',
                'class_session__subject__teacher',
                'class_session__subject__teacher__user'
            )
            
            if search_query:
                queryset = queryset.filter(
                    Q(class_session__subject__name__icontains=search_query) |
                    Q(class_session__subject__code__icontains=search_query)
                )
            
            if subject_id:
                queryset = queryset.filter(class_session__subject_id=subject_id)
            
            if status_filter and status_filter in ['PRESENT', 'ABSENT']:
                queryset = queryset.filter(status=status_filter)
            
            start_date = self._parse_date(start_date_str)
            if start_date:
                queryset = queryset.filter(marked_at__date__gte=start_date)
            
            end_date = self._parse_date(end_date_str)
            if end_date:
                queryset = queryset.filter(marked_at__date__lte=end_date)
            
            reverse_sort = sort_order.lower() == 'desc'
            
            if sort_by == 'subject':
                queryset = queryset.order_by(
                    f"{'-' if reverse_sort else ''}class_session__subject__name"
                )
            elif sort_by == 'status':
                queryset = queryset.order_by(
                    f"{'-' if reverse_sort else ''}status"
                )
            else:
                queryset = queryset.order_by(
                    f"{'-' if reverse_sort else ''}marked_at"
                )
            
            total_count = queryset.count()
            total_present = queryset.filter(status='PRESENT').count()
            total_absent = queryset.filter(status='ABSENT').count()
            
            total_pages = (total_count + page_size - 1) // page_size
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_records = queryset[start_idx:end_idx]
            
            records_data = []
            
            for attendance in paginated_records:
                subject = attendance.class_session.subject
                
                records_data.append({
                    'id': str(attendance.id),
                    'date': attendance.marked_at.date().isoformat(),
                    'time': attendance.marked_at.time().isoformat(),
                    'subject_name': subject.name,
                    'subject_code': subject.code,
                    'class_name': attendance.class_session.class_name,
                    'teacher_name': self._get_teacher_name(subject.teacher),
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
                'summary': {
                    'total_present': total_present,
                    'total_absent': total_absent,
                },
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'detail': f'Error fetching attendance history: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def enrolled_subjects(self, request):
        try:
            if not self._check_student(request):
                return Response(
                    {'detail': 'Only students can access their subjects'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            search_query = request.query_params.get('search', '').strip()
            sort_by = request.query_params.get('sort_by', 'name')
            sort_order = request.query_params.get('sort_order', 'asc')
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 10))
            
            enrollments = Enrollment.objects.filter(
                student__user=request.user
            ).select_related('subject', 'subject__teacher', 'subject__teacher__user')
            
            subjects_data = []
            
            for enrollment in enrollments:
                subject = enrollment.subject
                
                subject_attendance = Attendance.objects.filter(
                    student__user=request.user,
                    class_session__subject=subject
                )
                
                total = subject_attendance.count()
                attended = subject_attendance.filter(status='PRESENT').count()
                missed = subject_attendance.filter(status='ABSENT').count()
                rate = (attended / total * 100) if total > 0 else 0
                
                teacher_name = self._get_teacher_name(subject.teacher)
                teacher_email = subject.teacher.user.email if subject.teacher and subject.teacher.user else ''
                
                subjects_data.append({
                    'subject_id': str(subject.id),
                    'subject_name': subject.name,
                    'subject_code': subject.code,
                    'teacher_name': teacher_name,
                    'teacher_email': teacher_email,
                    'department': subject.department,
                    'semester': subject.semester,
                    'total_classes': total,
                    'classes_attended': attended,
                    'classes_missed': missed,
                    'attendance_rate': round(rate, 2),
                })
            
            if search_query:
                subjects_data = [
                    s for s in subjects_data
                    if search_query.lower() in s['subject_name'].lower() or
                       search_query.lower() in s['subject_code'].lower() or
                       search_query.lower() in s['teacher_name'].lower()
                ]
            
            reverse_sort = sort_order.lower() == 'desc'
            
            if sort_by == 'code':
                subjects_data.sort(key=lambda x: x['subject_code'], reverse=reverse_sort)
            elif sort_by == 'rate':
                subjects_data.sort(key=lambda x: x['attendance_rate'], reverse=reverse_sort)
            elif sort_by == 'department':
                subjects_data.sort(key=lambda x: x['department'], reverse=reverse_sort)
            else:
                subjects_data.sort(key=lambda x: x['subject_name'], reverse=reverse_sort)
            
            total_count = len(subjects_data)
            total_pages = (total_count + page_size - 1) // page_size
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_subjects = subjects_data[start_idx:end_idx]
            
            return Response({
                'subjects': paginated_subjects,
                'pagination': {
                    'current_page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': total_pages,
                },
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'detail': f'Error fetching enrolled subjects: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def subject_detail(self, request):
        try:
            if not self._check_student(request):
                return Response(
                    {'detail': 'Only students can access subject details'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            subject_id = request.query_params.get('subject_id', '').strip()
            if not subject_id:
                return Response(
                    {'detail': 'subject_id parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            search_query = request.query_params.get('search', '').strip()
            status_filter = request.query_params.get('status', '').strip()
            sort_by = request.query_params.get('sort_by', 'date')
            sort_order = request.query_params.get('sort_order', 'desc')
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 10))
            
            enrollment = Enrollment.objects.filter(
                student__user=request.user,
                subject_id=subject_id
            ).select_related('subject', 'subject__teacher', 'subject__teacher__user').first()
            
            if not enrollment:
                return Response(
                    {'detail': 'You are not enrolled in this subject'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            subject = enrollment.subject
            
            subject_attendance = Attendance.objects.filter(
                student__user=request.user,
                class_session__subject=subject
            ).select_related('class_session')
            
            total = subject_attendance.count()
            attended = subject_attendance.filter(status='PRESENT').count()
            missed = subject_attendance.filter(status='ABSENT').count()
            rate = (attended / total * 100) if total > 0 else 0
            
            queryset = subject_attendance
            
            if search_query:
                queryset = queryset.filter(
                    Q(class_session__class_name__icontains=search_query)
                )
            
            if status_filter and status_filter in ['PRESENT', 'ABSENT']:
                queryset = queryset.filter(status=status_filter)
            
            reverse_sort = sort_order.lower() == 'desc'
            
            if sort_by == 'status':
                queryset = queryset.order_by(
                    f"{'-' if reverse_sort else ''}status"
                )
            else:
                queryset = queryset.order_by(
                    f"{'-' if reverse_sort else ''}marked_at"
                )
            
            total_count = queryset.count()
            total_pages = (total_count + page_size - 1) // page_size
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_sessions = queryset[start_idx:end_idx]
            
            sessions_data = []
            for attendance in paginated_sessions:
                sessions_data.append({
                    'date': attendance.marked_at.date().isoformat(),
                    'class_name': attendance.class_session.class_name,
                    'status': attendance.status,
                    'detection_confidence': round(attendance.detection_confidence, 3),
                })
            
            return Response({
                'subject': {
                    'id': str(subject.id),
                    'name': subject.name,
                    'code': subject.code,
                    'teacher_name': self._get_teacher_name(subject.teacher),
                    'department': subject.department,
                    'semester': subject.semester,
                },
                'stats': {
                    'total_classes': total,
                    'classes_attended': attended,
                    'classes_missed': missed,
                    'attendance_rate': round(rate, 2),
                },
                'sessions': sessions_data,
                'pagination': {
                    'current_page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': total_pages,
                },
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'detail': f'Error fetching subject details: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def profile(self, request):
        try:
            if not self._check_student(request):
                return Response(
                    {'detail': 'Only students can access their profile'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            student = request.user.studentprofile
            
            enrollment_count = Enrollment.objects.filter(
                student=student
            ).count()
            
            face_data = getattr(student, 'face_data', None)
            face_enrolled = face_data.is_enrolled if face_data else False
            face_photos = face_data.total_photos_registered if face_data else 0
            face_confidence = face_data.registration_confidence if face_data else 0
            
            return Response({
                'id': str(request.user.id),
                'email': request.user.email,
                'first_name': request.user.first_name or '',
                'last_name': request.user.last_name or '',
                'phone_no': student.phone_no or '',
                'address': student.address or '',
                'roll_number': student.roll_number,
                'department': student.department or '',
                'year': student.year,
                'is_active': request.user.is_active,
                'enrollment_count': enrollment_count,
                'face_enrolled': face_enrolled,
                'face_photos': face_photos,
                'face_confidence': round(face_confidence, 3),
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'detail': f'Error fetching profile: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def todays_classes(self, request):
        """
        Get today's classes with session status for student.
        
        Status meanings:
        - 'upcoming': Class hasn't started yet (start_time > now)
        - 'running': Time window is during class (between start and end+5min), AND teacher must have started session
        - 'completed': Class time has ended
        
        Returns list with detailed session info and attendance status.
        """
        try:
            if not self._check_student(request):
                return Response(
                    {'detail': 'Only students can access this'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            today = timezone.now().date()
            now = timezone.now()
            student = request.user.studentprofile
            
            # Get student's enrolled subjects
            enrolled_subjects = Enrollment.objects.filter(
                student=student
            ).values_list('subject_id', flat=True)
            
            # Get today's classes for enrolled subjects
            todays_sessions = ClassSession.objects.filter(
                subject_id__in=enrolled_subjects,
                date=today
            ).select_related(
                'subject',
                'subject__teacher',
                'subject__teacher__user'
            ).order_by('start_time')
            
            classes_data = []
            
            for session in todays_sessions:
                subject = session.subject
                
                # Check if teacher has active session
                active_session = AttendanceSession.objects.filter(
                    class_session=session,
                    ended_at__isnull=True
                ).first()
                
                # Check if student already marked attendance
                student_attendance = Attendance.objects.filter(
                    student=student,
                    class_session=session,
                    initiated_by='student'
                ).first()
                
                # Determine session status based on time windows
                class_start = timezone.datetime.combine(today, session.start_time)
                class_end = timezone.datetime.combine(today, session.end_time)
                
                # Convert to timezone-aware if needed
                if timezone.is_naive(class_start):
                    class_start = timezone.make_aware(class_start)
                if timezone.is_naive(class_end):
                    class_end = timezone.make_aware(class_end)
                
                # Add 5 min grace period to end time
                class_end_with_grace = class_end + timezone.timedelta(minutes=5)
                
                # Determine session_status purely on time
                if now < class_start:
                    session_status = 'upcoming'
                elif now > class_end_with_grace:
                    session_status = 'completed'
                else:
                    session_status = 'running'
                
                # can_mark_attendance = TRUE only if time window is 'running' AND teacher started session
                can_mark_attendance = (session_status == 'running' and active_session is not None)
                
                classes_data.append({
                    'id': str(session.id),
                    'class_name': session.class_name,
                    'subject_id': str(subject.id),
                    'subject_name': subject.name,
                    'subject_code': subject.code,
                    'date': session.date.isoformat(),
                    'start_time': session.start_time.isoformat(),
                    'end_time': session.end_time.isoformat(),
                    'teacher_name': self._get_teacher_name(subject.teacher),
                    'teacher_id': str(subject.teacher.user.id) if subject.teacher else '',
                    'session_status': session_status,  # 'upcoming', 'running', 'completed'
                    'is_session_active': active_session is not None,  # Teacher started?
                    'can_mark_attendance': can_mark_attendance,  # Can student mark NOW?
                    'has_marked_attendance': student_attendance is not None,
                    'attendance_id': str(student_attendance.id) if student_attendance else None,
                    'attendance_confidence': round(student_attendance.detection_confidence, 3) if student_attendance else None,
                    'attendance_status': student_attendance.status if student_attendance else None,
                })
            
            return Response(classes_data, status=status.HTTP_200_OK)
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'detail': f'Error fetching today\'s classes: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
