# Migration to fix ClassSessionTemplate schema mismatch
# Previous model inherited from BaseModel (UUID id), now it uses default BigAutoField

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0001_initial'),
        ('attendance', '0005_fix_attendance_flow'),
    ]

    operations = [
        # Delete the old table (this will cascade to attendance_sessions with this template)
        migrations.DeleteModel(
            name='ClassSessionTemplate',
        ),
        
        # Recreate with proper BigAutoField
        migrations.CreateModel(
            name='ClassSessionTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('day_of_week', models.IntegerField(
                    choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')],
                    help_text='Day of week (0=Monday, 6=Sunday)'
                )),
                ('start_time', models.TimeField(help_text='Class start time')),
                ('end_time', models.TimeField(help_text='Class end time')),
                ('max_attendance_marking_minutes', models.IntegerField(default=15, help_text='Maximum minutes after class start that students can mark attendance')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this template is active')),
                ('subject', models.ForeignKey(help_text='Subject this template is for', on_delete=django.db.models.deletion.CASCADE, related_name='session_templates', to='academics.subject')),
            ],
            options={
                'ordering': ['day_of_week', 'start_time'],
            },
        ),
        
        # Add unique constraint
        migrations.AddConstraint(
            model_name='classsessiontemplate',
            constraint=models.UniqueConstraint(fields=['subject', 'day_of_week', 'start_time'], name='unique_template_per_subject_time'),
        ),
        
        # Add indexes
        migrations.AddIndex(
            model_name='classsessiontemplate',
            index=models.Index(fields=['subject', 'day_of_week'], name='attendance_c_subject_day_idx'),
        ),
        migrations.AddIndex(
            model_name='classsessiontemplate',
            index=models.Index(fields=['is_active'], name='attendance_c_is_active_idx'),
        ),
        
        # Re-add template field to AttendanceSession
        migrations.AddField(
            model_name='attendancesession',
            name='template',
            field=models.ForeignKey(blank=True, help_text='Template this session is based on (for recurring sessions)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='attendance_sessions', to='attendance.classsessiontemplate'),
        ),
        
        # Re-add the index for template+date
        migrations.AddIndex(
            model_name='attendancesession',
            index=models.Index(fields=['template', 'session_date'], name='attendance_a_template_date_idx'),
        ),
    ]
