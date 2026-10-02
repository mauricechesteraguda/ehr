from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users", "0023_ticket14_quality")]

    operations = [
        migrations.AddField(
            model_name="allergyintolerance",
            name="status",
            field=models.CharField(default="active", max_length=30),
        ),
    ]
