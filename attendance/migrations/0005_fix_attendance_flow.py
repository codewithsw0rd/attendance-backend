# Generated migration to fix attendance flow issues

from django.db import migrations, models
import django.db.models.deletion


def populate_null_sessions(apps, schema_editor):
    """Populate any NULL attendance_session values"""
    Attendance = apps.get_model('attendance', 'Attendance')
    AttendanceSession = apps.get_model('attendance', 'AttendanceSession')
    
    null_records = Attendance.objects.filter(attendance_session__isnull=True)
    
    for record in null_records:
        # Find an active session for this class
        session = AttendanceSession.objects.filter(
            class_session=record.class_session,
            ended_at__isnull=True
        ).first()
        
        if session:
            record.attendance_session = session
            record.save()
            print(f"Linked attendance {record.id} to session {session.id}")
        else:
            # No active session - this shouldn't happen but log it
            print(f"WARNING: No active session for attendance {record.id} (class_session={record.class_session.id})")


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0004_add_template_based_sessions'),
    ]

    operations = [
        # First, populate any NULL attendance_session values
        migrations.RunPython(
            code=populate_null_sessions,
            reverse_code=migrations.RunPython.noop,
        ),
        
        # Then make the field required (NOT NULL)
        migrations.AlterField(
            model_name='attendance',
            name='attendance_session',
            field=models.ForeignKey(
                'attendance.AttendanceSession',
                on_delete=models.CASCADE,
                related_name='attendances',
                help_text='Link to the real-time session during which this attendance was marked'
            ),
        ),
        
        # Add new unique constraint for teacher-initiated records
        migrations.AddConstraint(
            model_name='attendance',
            constraint=models.UniqueConstraint(
                fields=['student', 'class_session', 'initiated_by'],
                condition=models.Q(initiated_by='teacher'),
                name='unique_teacher_per_class_session'
            ),
        ),
    ]
