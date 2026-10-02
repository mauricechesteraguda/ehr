from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("users", "0018_ticket09_patient_selection")]
    operations = [
        migrations.CreateModel(
            name="PopulationExportSchedule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("scope", models.CharField(default="all-demo", max_length=20)),
                ("start_date", models.DateField()), ("end_date", models.DateField()),
                ("purpose", models.CharField(max_length=500)), ("format", models.CharField(max_length=20)),
                ("timezone", models.CharField(default="UTC", max_length=64)),
                ("cadence", models.CharField(default="once", max_length=20)),
                ("next_run_at", models.DateTimeField(blank=True, null=True)),
                ("active", models.BooleanField(default=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="population_export_schedules", to="users.user")),
            ],
        ),
        migrations.CreateModel(
            name="PopulationExportArtifact",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("format", models.CharField(max_length=20)), ("path", models.CharField(max_length=500)),
                ("sha256", models.CharField(max_length=64)), ("size_bytes", models.PositiveBigIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("expires_at", models.DateTimeField()),
                ("job", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="population_artifact", to="users.job")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="population_export_artifacts", to="users.user")),
                ("schedule", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="artifacts", to="users.populationexportschedule")),
            ],
        ),
    ]
