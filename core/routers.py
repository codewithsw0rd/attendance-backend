from rest_framework.routers import DefaultRouter
from accounts.api.viewsets import *
from academics.api.viewsets import *

router = DefaultRouter()

#-----------------------------------ACCOUNTS-----------------------------------------------------
router.register('students', StudentViewSet, basename='students')
router.register('teachers', TeacherViewSet, basename='teachers')
router.register('admins', AdminViewSet, basename='admins')

#-----------------------------------ACADEMICS-----------------------------------------------------
router.register('subjects', SubjectViewSet, basename='subjects')
router.register('enrollments', EnrollmentViewSet, basename='enrollments')
router.register('class-sessions', ClassSessionViewSet, basename='class-sessions')