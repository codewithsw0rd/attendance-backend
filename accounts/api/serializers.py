from rest_framework import serializers
from ..models import *
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import Group
import re


def validate_password(password: str):
    """
    Validates a password using a custom regex.
    Requirements:
    - At least one lowercase letter
    - At least one uppercase letter
    - At least one digit
    - At least one special character (@$!%*?&)
    - Minimum 8 characters long
    """
    pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'

    if not re.match(pattern, password):
        raise ValidationError(
            "Password must be at least 8 characters long, include at least one uppercase letter, "
            "one lowercase letter, one number, and one special character (@$!%*?&)."
        )

class CustomUserSerializer(serializers.ModelSerializer):
    user_type = serializers.CharField(write_only=True, required=True, allow_null=False)
    
    first_name = serializers.CharField(max_length=150, required=False, allow_null=True, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_null=True, allow_blank=True)
    phone_no = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)
    address = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    
    # StudentProfile fields
    year = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    roll_number = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True, write_only=True)
    department = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True, write_only=True)
    
    # TeacherProfile fields
    employee_id = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True, write_only=True)
    
    class Meta:
        model = CustomUser
        fields = ['email', 'password', 'user_type', 'first_name', 'last_name', 'phone_no', 'address', 'is_active', 'year', 'roll_number', 'department', 'employee_id']
        extra_kwargs = {
            'password': {'write_only': True},
            'is_active': {'read_only': True}
        }
    
    def _create_user_profile(self, user_type: str, user_obj, profile_info) -> None:
        if user_type == UserType.STUDENT:
            StudentProfile.objects.create(
                user=user_obj,
                **profile_info
            )
        elif user_type == UserType.TEACHER:
            TeacherProfile.objects.create(
                user=user_obj,
                **profile_info
            )
        elif user_type == UserType.ADMIN:
            AdminProfile.objects.create(
                user=user_obj,
                **profile_info
            )
    
    def create(self, validated_data):
        if validated_data.get('user_type') == UserType.ADMIN:
            if CustomUser.objects.filter(user_type=UserType.ADMIN).count() >= 3:
                raise DRFValidationError({'user_type': 'Cannot create more than 3 admin users.'})
        
        password = validated_data.pop('password', None)
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                raise DRFValidationError({"password": e.messages})
        
        user_type = validated_data.get('user_type')
        
        validated_data['is_active'] = True
        extra_fields = {
            'first_name': validated_data.pop('first_name', None),
            'last_name': validated_data.pop('last_name', None),
            'phone_no': validated_data.pop('phone_no', None),
            'address': validated_data.pop('address', None),
        }
        
        # Add profile-specific fields
        if user_type == UserType.STUDENT:
            extra_fields['year'] = validated_data.pop('year', None)
            extra_fields['roll_number'] = validated_data.pop('roll_number', None)
            extra_fields['department'] = validated_data.pop('department', None)
        elif user_type == UserType.TEACHER:
            extra_fields['employee_id'] = validated_data.pop('employee_id', None)
            extra_fields['department'] = validated_data.pop('department', None)
        
        # Remove unused fields
        validated_data.pop('year', None)
        validated_data.pop('roll_number', None)
        validated_data.pop('department', None)
        validated_data.pop('employee_id', None)
        
        user = CustomUser(**validated_data)
        user.save()
        user.set_password(password)
        user.save()
        
        self._create_user_profile(
            user_type=user_type,
            user_obj=user,
            profile_info=extra_fields
        )
        
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        return user, access_token, refresh_token
        
# class ProfileSerializer(serializers.ModelSerializer):
#     email = serializers.EmailField(source='user.email', read_only=True)
#     is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    
#     class Meta:
#         model = Profile
#         fields = '__all__' 
    
class StudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = '__all__'
        
class TeacherProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherProfile
        fields = '__all__'
        
class AdminProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminProfile
        fields = '__all__'
        
class StudentProfileReadSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    user_type = serializers.CharField(source='user.user_type', read_only=True)
    
    
    class Meta:
        model = StudentProfile
        fields = '__all__'
        
class TeacherProfileReadSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    user_type = serializers.CharField(source='user.user_type', read_only=True)
    
    
    class Meta:
        model = TeacherProfile
        fields = '__all__'
        
class AdminProfileReadSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    user_type = serializers.CharField(source='user.user_type', read_only=True)
    
    class Meta:
        model = AdminProfile
        fields = '__all__'