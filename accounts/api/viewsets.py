from .serializers import *
from rest_framework.response import Response
from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from django.db import transaction
from core.utils.custom_perms import IsClientUser


class StudentViewSet(ModelViewSet):
    queryset = StudentProfile.objects.all()
    serializer_class = StudentProfileSerializer
    permission_classes = [IsClientUser]
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        request_data = request.data.copy()
        
        if 'user_type' not in request_data:
            request_data['user_type'] = UserType.STUDENT
        else:
            if not request_data['user_type'] != UserType.STUDENT:
                return Response(
                    {'error': 'user_type must be STUDENT'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        request_data['is_active'] = True
        user_serializer = CustomUserSerializer(data=request_data, context={'request': request})
        
        if not user_serializer.is_valid():
            return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user_obj, access_token, refresh_token = user_serializer.save()
        
        return Response(
            ProfileSerializer(user_obj.profile).data,
            status=status.HTTP_201_CREATED
        )
        
class TeacherViewSet(ModelViewSet):
    queryset = TeacherProfile.objects.all()
    serializer_class = TeacherProfileSerializer
    permission_classes = [IsClientUser]
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        request_data = request.data.copy()
        
        if 'user_type' not in request_data:
            request_data['user_type'] = UserType.TEACHER
        else:
            if not request_data['user_type'] != UserType.TEACHER:
                return Response(
                    {'error': 'user_type must be TEACHER'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        request_data['is_active'] = True
        user_serializer = CustomUserSerializer(data=request_data, context={'request': request})
        
        if not user_serializer.is_valid():
            return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user_obj, access_token, refresh_token = user_serializer.save()
        
        return Response(
            ProfileSerializer(user_obj.profile).data,
            status=status.HTTP_201_CREATED
        )
        
class AdminViewSet(ModelViewSet):
    queryset = AdminProfile.objects.all()
    serializer_class = AdminProfileSerializer
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        request_data = request.data.copy()
        
        if CustomUser.objects.filter(user_type=UserType.ADMIN).count() >= 3:
            return Response(
                {'error': 'Only 3 admin users are allowed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if 'user_type' not in request_data:
            request_data['user_type'] = UserType.ADMIN
        else:
            if not request_data['user_type'] != UserType.ADMIN:
                return Response(
                    {'error': 'user_type must be ADMIN'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        request_data['is_active'] = True
        user_serializer = CustomUserSerializer(data=request_data, context={'request': request})
        
        if not user_serializer.is_valid():
            return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user_obj, _, _ = user_serializer.save()
        
        return Response(
            ProfileSerializer(user_obj.profile).data,
            status=status.HTTP_201_CREATED
        )
        
    