from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from accounts.models import CustomUser, UserType
from accounts.api.serializers import StudentProfileReadSerializer, TeacherProfileReadSerializer, AdminProfileReadSerializer

class GetProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        user = request.user
        if isinstance(user, CustomUser):
            if user.user_type == UserType.ADMIN:
                return Response(
                    {
                        **AdminProfileReadSerializer(user.adminprofile, context = {'request':request}).data
                    },
                    status=status.HTTP_200_OK
                )
            
            if user.user_type == UserType.STUDENT:
                return Response(
                    StudentProfileReadSerializer(user.studentprofile, context = {'request':request}).data,
                    status=status.HTTP_200_OK
                )
            
            if user.user_type == UserType.TEACHER:
                return Response(
                    TeacherProfileReadSerializer(user.teacherprofile, context = {'request':request}).data,
                    status=status.HTTP_200_OK
                )