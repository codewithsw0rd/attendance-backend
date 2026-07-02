# Migration to fix ClassSessionTemplate schema mismatch
# Convert from UUID id to BigAutoField

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0005_fix_attendance_flow'),
    ]

    operations = [
        # Drop old id column (UUID) and create new one (BigAutoField)
        # This uses raw SQL because Django migrations don't have a direct way to convert UUID to BigAutoField
        migrations.RunSQL(
            sql="""
            -- Add new bigint id column
            ALTER TABLE attendance_classsessiontemplate ADD COLUMN id_new BIGSERIAL;
            
            -- Drop old constraints that depend on the old id
            ALTER TABLE attendance_classsessiontemplate DROP CONSTRAINT attendance_classsessiontemplate_pkey;
            ALTER TABLE attendance_attendancesession DROP CONSTRAINT IF EXISTS attendance_attendancesession_template_id_fkey;
            
            -- Drop old id column
            ALTER TABLE attendance_classsessiontemplate DROP COLUMN id;
            
            -- Rename new id to id
            ALTER TABLE attendance_classsessiontemplate RENAME COLUMN id_new TO id;
            
            -- Add primary key constraint
            ALTER TABLE attendance_classsessiontemplate ADD PRIMARY KEY (id);
            
            -- Re-add foreign key constraint
            ALTER TABLE attendance_attendancesession ADD CONSTRAINT attendance_attendancesession_template_id_fkey
            FOREIGN KEY (template_id) REFERENCES attendance_classsessiontemplate(id) ON DELETE CASCADE;
            """,
            reverse_sql="""
            -- Reverse migration - not needed for this fix
            """,
        ),
    ]
