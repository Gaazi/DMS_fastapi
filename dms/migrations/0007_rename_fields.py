from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('dms', '0006_expense_receipt_number_and_more'),
    ]

    operations = [
        # Staff Renames
        migrations.RenameField(
            model_name='staff',
            old_name='full_name',
            new_name='name',
        ),
        migrations.RenameField(
            model_name='historicalstaff',
            old_name='full_name',
            new_name='name',
        ),
        
        # Parent Renames
        migrations.RenameField(
            model_name='parent',
            old_name='full_name',
            new_name='name',
        ),
        migrations.RenameField(
            model_name='historicalparent',
            old_name='full_name',
            new_name='name',
        ),
        migrations.RenameField(
            model_name='parent',
            old_name='phone_primary',
            new_name='phone',
        ),
        migrations.RenameField(
            model_name='historicalparent',
            old_name='phone_primary',
            new_name='phone',
        ),

        # Student Renames
        migrations.RenameField(
            model_name='student',
            old_name='contact_number',
            new_name='phone',
        ),
        migrations.RenameField(
            model_name='historicalstudent',
            old_name='contact_number',
            new_name='phone',
        ),
    ]
