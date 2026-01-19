# Generated migration to fix deactivated_by foreign key constraint
from django.db import migrations, connection


def fix_constraint_forward(apps, schema_editor):
    """Fix the deactivated_by constraint - only runs on PostgreSQL."""
    if connection.vendor != 'postgresql':
        # SQLite doesn't support this constraint manipulation, skip it
        return
    
    with connection.cursor() as cursor:
        # Drop the incorrect constraint if it exists
        cursor.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.table_constraints 
                    WHERE constraint_name = 'profile_deactivated_by_id_ac0872b6_fk_users_id'
                ) THEN
                    ALTER TABLE profile 
                    DROP CONSTRAINT profile_deactivated_by_id_ac0872b6_fk_users_id;
                END IF;
            END $$;
        """)
        # Add the correct constraint if it doesn't exist
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.table_constraints 
                    WHERE constraint_name = 'profile_deactivated_by_id_fkey'
                ) THEN
                    ALTER TABLE profile 
                    ADD CONSTRAINT profile_deactivated_by_id_fkey 
                    FOREIGN KEY (deactivated_by_id) 
                    REFERENCES profile(id) 
                    ON DELETE SET NULL 
                    DEFERRABLE INITIALLY DEFERRED;
                END IF;
            END $$;
        """)


def fix_constraint_reverse(apps, schema_editor):
    """Reverse the constraint fix - only runs on PostgreSQL."""
    if connection.vendor != 'postgresql':
        return
    
    with connection.cursor() as cursor:
        cursor.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.table_constraints 
                    WHERE constraint_name = 'profile_deactivated_by_id_fkey'
                ) THEN
                    ALTER TABLE profile 
                    DROP CONSTRAINT profile_deactivated_by_id_fkey;
                END IF;
            END $$;
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0005_add_can_view_others_activity_logs'),
    ]

    operations = [
        migrations.RunPython(fix_constraint_forward, fix_constraint_reverse),
    ]
