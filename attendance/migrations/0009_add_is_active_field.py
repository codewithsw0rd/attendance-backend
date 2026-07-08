# Generated migration for adding is_active field to AttendanceSession

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0008_rename_attendance_a_template_date_idx_attendance__templat_337a48_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendancesession',
            name='is_active',
            field=models.BooleanField(default=True, help_text='Whether this session is currently active (not ended)'),
        ),
        migrations.AddIndex(
            model_name='attendancesession',
            index=models.Index(fields=['template', 'session_date', 'is_active'], name='attendance_a_templat_sess_act_idx'),
        ),
    ]
