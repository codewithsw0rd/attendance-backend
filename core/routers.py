from rest_framework.routers import DefaultRouter
from accounts.api.viewsets import *
from academics.api.viewsets import *
from attendance.api.viewsets import *
from attendance.api.dashboard_viewsets import DashboardViewSet
from attendance.api.analytics_viewsets import AnalyticsViewSet
from attendance.api.admin_reports_viewsets import AdminReportsViewSet
from attendance.api.student_dashboard_viewsets import StudentDashboardViewSet

router = DefaultRouter()

#-----------------------------------ACCOUNTS-----------------------------------------------------
router.register('students', StudentViewSet, basename='students')
router.register('teachers', TeacherViewSet, basename='teachers')
router.register('admins', AdminViewSet, basename='admins')

#-----------------------------------ACADEMICS-----------------------------------------------------
router.register('subjects', SubjectViewSet, basename='subjects')
router.register('enrollments', EnrollmentViewSet, basename='enrollments')
router.register('class-sessions', ClassSessionViewSet, basename='class-sessions')

#-----------------------------------FACE RECOGNITION & ATTENDANCE-----------------------------------------------------
router.register('face-data', FaceDataViewSet, basename='face-data')
router.register('class-session-templates', ClassSessionTemplateViewSet, basename='class-session-templates')
router.register('attendance', AttendanceViewSet, basename='attendance')
router.register('attendance-logs', AttendanceLogViewSet, basename='attendance-logs')

#-----------------------------------DASHBOARD-----------------------------------------------------
router.register('dashboard', DashboardViewSet, basename='dashboard')

#-----------------------------------ANALYTICS-----------------------------------------------------
router.register('analytics', AnalyticsViewSet, basename='analytics')

#-----------------------------------ADMIN REPORTS-----------------------------------------------------
router.register('admin-reports', AdminReportsViewSet, basename='admin-reports')

#-----------------------------------STUDENT DASHBOARD-----------------------------------------------------
router.register('student-dashboard', StudentDashboardViewSet, basename='student-dashboard')