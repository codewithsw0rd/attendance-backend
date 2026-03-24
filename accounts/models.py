from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models, transaction
from core.utils.base_model import BaseModel
import uuid
# Create your models here.

class CustomUserManager(BaseUserManager):
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        
        if password:
            user.set_password(password)
        else:
            raise ValueError('The Password field must be set')
        
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', UserType.ADMIN)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        user = self.create_user(email, password, **extra_fields)
        
        AdminProfile.objects.create(user=user)
        
        return self.create_user(email, password, **extra_fields)
    
class UserType(models.TextChoices):
    ADMIN = 'ADMIN', 'Admin',
    STUDENT = 'STUDENT', 'Student',
    TEACHER = 'TEACHER', 'Teacher',
    
class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    user_type = models.CharField(max_length=20, choices=UserType.choices, default=UserType.STUDENT)
    
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    username = None
    first_name = None
    last_name = None
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = CustomUserManager()
    
    def __str__(self):
        return self.email
    
class Profile(BaseModel):
    first_name = models.CharField(max_length=150, null=True, blank=True)
    last_name = models.CharField(max_length=150, null=True, blank=True)
    phone_no = models.CharField(max_length=20, null=True, blank=True)
    
    address = models.TextField(null=True, blank=True)
    
    class Meta:
        abstract = True
    
class StudentProfile(Profile):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='studentprofile')
    roll_number = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100, null=True, blank=True)
    year = models.IntegerField()
    
class TeacherProfile(Profile):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='teacherprofile')
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100, null=True, blank=True)
    
class AdminProfile(Profile):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='adminprofile')