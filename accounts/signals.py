from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import StudentProfile


@receiver(post_save, sender=StudentProfile)
def auto_create_face_data(sender, instance, created, **kwargs):
    """Auto-create FaceData record when a StudentProfile is created"""
    if created:
        # Import here to avoid circular imports
        from attendance.models import FaceData
        
        FaceData.objects.get_or_create(student=instance)
