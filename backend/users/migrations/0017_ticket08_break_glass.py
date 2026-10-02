from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("users", "0016_alter_smsrecoverychallenge_id_and_more")]
    operations = [
        migrations.AddField(model_name="patient", name="restricted_access", field=models.BooleanField(default=False)),
        migrations.CreateModel(
            name="ClinicianPatientAssignment",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                    ("clinician", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="patient_assignments", to="users.user")),
                    ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="clinician_assignments", to="users.patient"))],
            options={"constraints": [models.UniqueConstraint(fields=("clinician", "patient"), name="clinician_patient_assignment_unique")]},
        ),
        migrations.CreateModel(
            name="EmergencyAccessRequest",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                    ("justification", models.CharField(max_length=500)), ("requested_at", models.DateTimeField()), ("expires_at", models.DateTimeField()),
                    ("state", models.CharField(choices=[("active", "Active"), ("expired", "Expired"), ("revoked", "Revoked")], default="active", max_length=10)),
                    ("revoked_at", models.DateTimeField(blank=True, null=True)), ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                    ("review_outcome", models.CharField(blank=True, choices=[("accepted", "Accepted"), ("suspicious", "Suspicious"), ("escalated", "Escalated")], default="", max_length=12)), ("suspicious", models.BooleanField(default=False)),
                    ("clinician", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="emergency_access_requests", to="users.user")),
                    ("patient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="emergency_access_requests", to="users.patient")),
                    ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="emergency_access_reviews", to="users.user"))],
            options={"indexes": [models.Index(fields=["state", "expires_at"], name="emergency_expiry_idx"), models.Index(fields=["reviewed_at"], name="emergency_review_idx")]},
        ),
        migrations.CreateModel(
            name="EmergencyAccessOutboxEvent",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("kind", models.CharField(default="break_glass_granted", max_length=40)), ("created_at", models.DateTimeField(auto_now_add=True)), ("dispatched_at", models.DateTimeField(blank=True, null=True)), ("request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outbox_events", to="users.emergencyaccessrequest"))],
        ),
    ]
