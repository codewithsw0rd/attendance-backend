# Generated migration for adding student-initiated attendance support

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0002_alter_attendance_unique_together_and_more'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        # Add initiated_by field
        migrations.AddField(
            model_name='attendance',
            name='initiated_by',
            field=models.CharField(
                choices=[
                    ('student', 'Student Self-Service'),
                    ('teacher', 'Teacher Batch Session'),
                    ('manual', 'Admin Manual Override'),
                ],
                default='teacher',
                help_text='Whether attendance was self-marked by student or teacher-marked',
                max_length=20,
            ),
        ),
        
        # Add initiated_by_user field
        migrations.AddField(
            model_name='attendance',
            name='initiated_by_user',
            field=models.ForeignKey(
                blank=True,
                help_text='Teacher or admin who initiated this record (if applicable)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='initiated_attendance_records',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        
        # Add attempt_count field
        migrations.AddField(
            model_name='attendance',
            name='attempt_count',
            field=models.IntegerField(
                default=1,
                help_text='Number of attempts student made to mark attendance',
            ),
        ),
        
        # Update constraints
        migrations.RemoveConstraint(
            model_name='attendance',
            name='unique_attendance_manual_marking',
        ),
        
        migrations.AddConstraint(
            model_name='attendance',
            constraint=models.UniqueConstraint(
                condition=models.Q(('initiated_by', 'student')),
                fields=['student', 'class_session', 'initiated_by'],
                name='unique_student_initiated_per_class_session',
            ),
        ),
        
        migrations.AddConstraint(
            model_name='attendance',
            constraint=models.UniqueConstraint(
                condition=models.Q(('initiated_by', 'manual')),
                fields=['student', 'class_session', 'initiated_by'],
                name='unique_manual_per_class_session',
            ),
        ),
    ]
