# Generated migration to fix deactivated_by foreign key constraint
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0005_add_can_view_others_activity_logs'),
    ]

    operations = [
        migrations.RunSQL(
            # Drop the incorrect constraint
            sql="""
            ALTER TABLE profile 
            DROP CONSTRAINT IF EXISTS profile_deactivated_by_id_ac0872b6_fk_users_id;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            # Add the correct constraint
            sql="""
            ALTER TABLE profile 
            ADD CONSTRAINT profile_deactivated_by_id_fkey 
            FOREIGN KEY (deactivated_by_id) 
            REFERENCES profile(id) 
            ON DELETE SET NULL 
            DEFERRABLE INITIALLY DEFERRED;
            """,
            reverse_sql="""
            ALTER TABLE profile 
            DROP CONSTRAINT IF EXISTS profile_deactivated_by_id_fkey;
            """,
        ),
    ]
