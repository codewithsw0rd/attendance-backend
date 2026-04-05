from .serializers import *
from rest_framework.response import Response
from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
from core.utils.custom_perms import IsClientUser
from attendance.models import FaceData, FaceEmbedding
from attendance.ml_client import register_face_embedding, MLServiceError
from drf_spectacular.utils import extend_schema


class StudentViewSet(ModelViewSet):
    queryset = StudentProfile.objects.all()
    serializer_class = StudentProfileSerializer
    permission_classes = [IsClientUser]
    parser_classes = (MultiPartParser, FormParser)
    
    @extend_schema(
        request=StudentCreationRequestSerializer,
        responses={201: StudentCreationResponseSerializer},
        description="Create a new student and register their face photos in a single request.\n\nRequest must be multipart/form-data with email, first_name, last_name, roll_number, and images (1-5 face photos)."
    )
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new student and register their face photos in a single request.
        
        Request (multipart/form-data):
            - email: Student email (required)
            - first_name: Student first name (required)
            - last_name: Student last name (required)
            - roll_number: Student roll number (required)
            - images: List of face photos (upload multiple files with same field name 'images')
                      Minimum 1, Maximum 5 images
        
        Response:
            - Returns student profile + face enrollment status
        """
        request_data = request.data.copy()
        
        if 'user_type' not in request_data:
            request_data['user_type'] = UserType.STUDENT
        else:
            if request_data['user_type'] != UserType.STUDENT:
                return Response(
                    {'error': 'user_type must be STUDENT'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        request_data['is_active'] = True
        
        # Extract face image files list
        face_images = request.FILES.getlist('images')
        
        # At least one face image is required
        if not face_images:
            return Response(
                {'error': 'At least one face image is required. Send multiple files with field name "images"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Maximum 5 images
        if len(face_images) > 5:
            return Response(
                {'error': 'Maximum 5 face images allowed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create user and student profile
        user_serializer = CustomUserSerializer(data=request_data, context={'request': request})
        
        if not user_serializer.is_valid():
            return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user_obj, access_token, refresh_token = user_serializer.save()
        student_profile = user_obj.studentprofile
        
        # Create FaceData record
        face_data, created = FaceData.objects.get_or_create(student=student_profile)
        
        # Process and register each face image
        try:
            for photo_number, image_file in enumerate(face_images, start=1):
                try:
                    # Call ML service to extract embedding and quality score
                    embedding, quality_score = register_face_embedding(image_file)
                    
                    # Create FaceEmbedding record
                    FaceEmbedding.objects.create(
                        face_data=face_data,
                        embedding=embedding,
                        photo_number=photo_number,
                        quality_score=quality_score
                    )
                    
                except MLServiceError as e:
                    return Response(
                        {'error': f'Failed to process image {photo_number}: {str(e)}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Update FaceData with enrollment status
            total_photos = len(face_images)
            face_data.total_photos_registered = total_photos
            
            # Calculate average registration_confidence from all quality scores
            all_embeddings = FaceEmbedding.objects.filter(face_data=face_data)
            embedding_count = all_embeddings.count()
            if embedding_count > 0:
                avg_confidence = sum(e.quality_score for e in all_embeddings) / embedding_count
            else:
                avg_confidence = 0.0
            face_data.registration_confidence = avg_confidence
            
            # Mark as enrolled if 5 photos provided
            if total_photos >= 5:
                face_data.is_enrolled = True
            
            face_data.save()
            
            # Prepare response with student and face data
            student_response = StudentProfileReadSerializer(student_profile).data
            student_response['face_enrollment'] = {
                'total_photos_registered': face_data.total_photos_registered,
                'registration_confidence': round(face_data.registration_confidence, 4),
                'is_enrolled': face_data.is_enrolled,
                'message': 'Face registration completed' if total_photos == 5 else f'Face registration in progress ({total_photos}/5 photos)'
            }
            student_response['access_token'] = access_token
            student_response['refresh_token'] = refresh_token
            
            return Response(
                student_response,
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            return Response(
                {'error': f'Error processing face images: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class TeacherViewSet(ModelViewSet):
    queryset = TeacherProfile.objects.all()
    serializer_class = TeacherProfileSerializer
    permission_classes = [IsClientUser]
    parser_classes = (MultiPartParser, FormParser)
    
    @extend_schema(
        request=TeacherCreationRequestSerializer,
        responses={201: TeacherCreationResponseSerializer},
        description="Create a new teacher account.\n\nRequest fields: email, password, first_name, last_name, employee_id, and optional department, phone_no, address"
    )
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        request_data = request.data.copy()
        
        if 'user_type' not in request_data:
            request_data['user_type'] = UserType.TEACHER
        else:
            if request_data['user_type'] != UserType.TEACHER:
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
            TeacherProfileReadSerializer(user_obj.teacherprofile).data,
            status=status.HTTP_201_CREATED
        )
        
class AdminViewSet(ModelViewSet):
    queryset = AdminProfile.objects.all()
    serializer_class = AdminProfileSerializer
    parser_classes = (MultiPartParser, FormParser)
    
    @extend_schema(
        request=AdminCreationRequestSerializer,
        responses={201: AdminCreationResponseSerializer},
        description="Create a new admin account. Maximum 3 admin users allowed.\n\nRequest fields: email, password, first_name, last_name, and optional phone_no, address"
    )
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
            if request_data['user_type'] != UserType.ADMIN:
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
            AdminProfileReadSerializer(user_obj.adminprofile).data,
            status=status.HTTP_201_CREATED
        )
        
    