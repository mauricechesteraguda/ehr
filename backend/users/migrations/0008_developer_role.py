from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users", "0007_ticket09_indexes")]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("clinician", "Clinician"),
                    ("patient", "Patient"),
                    ("admin", "Administrator"),
                    ("developer", "Developer"),
                ],
                default="patient",
                max_length=20,
            ),
        )
    ]
