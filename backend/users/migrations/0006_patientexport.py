from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("users", "0005_ticket05_interaction_safety")]
    operations = [migrations.CreateModel(
        name="PatientExport",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("artifact_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
            ("format", models.CharField(choices=[("json", "JSON"), ("pdf", "PDF")], max_length=4)),
            ("path", models.CharField(max_length=500)),
            ("sha256", models.CharField(max_length=64)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("expires_at", models.DateTimeField()),
            ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exports", to="users.patient")),
            ("requested_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="patient_exports", to="users.user")),
        ],
        options={"constraints": [models.UniqueConstraint(fields=("patient", "requested_by", "format"), name="one_active_export_slot")]},
    )]
