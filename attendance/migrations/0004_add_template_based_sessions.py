# Generated migration for template-based reusable sessions

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0001_initial'),
        ('attendance', '0003_add_student_initiated_fields'),
    ]

    operations = [
        # Create ClassSessionTemplate model
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
        
        # Add unique constraint on ClassSessionTemplate
        migrations.AddConstraint(
            model_name='classsessiontemplate',
            constraint=models.UniqueConstraint(fields=['subject', 'day_of_week', 'start_time'], name='unique_template_per_subject_time'),
        ),
        
        # Add indexes on ClassSessionTemplate
        migrations.AddIndex(
            model_name='classsessiontemplate',
            index=models.Index(fields=['subject', 'day_of_week'], name='attendance_c_subject_day_idx'),
        ),
        migrations.AddIndex(
            model_name='classsessiontemplate',
            index=models.Index(fields=['is_active'], name='attendance_c_is_active_idx'),
        ),
        
        # Add template field to AttendanceSession
        migrations.AddField(
            model_name='attendancesession',
            name='template',
            field=models.ForeignKey(blank=True, help_text='Template this session is based on (for recurring sessions)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='attendance_sessions', to='attendance.classsessiontemplate'),
        ),
        
        # Add session_date field to AttendanceSession
        migrations.AddField(
            model_name='attendancesession',
            name='session_date',
            field=models.DateField(auto_now_add=True, default='2024-01-01', help_text='Date this session occurred'),
            preserve_default=False,
        ),
        
        # Add session_time field to AttendanceSession
        migrations.AddField(
            model_name='attendancesession',
            name='session_time',
            field=models.TimeField(blank=True, help_text='Time of session (e.g., 09:00 for Monday 9 AM class)', null=True),
        ),
        
        # Add indexes on AttendanceSession for template-based queries
        migrations.AddIndex(
            model_name='attendancesession',
            index=models.Index(fields=['template', 'session_date'], name='attendance_a_template_date_idx'),
        ),
        migrations.AddIndex(
            model_name='attendancesession',
            index=models.Index(fields=['session_date', 'session_time'], name='attendance_a_date_time_idx'),
        ),
    ]
