from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("users", "0013_ticket05_questionnaires")]
    operations = [
        migrations.CreateModel(name="PatientAmendment", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("resource_type", models.CharField(max_length=80)), ("resource_id", models.CharField(max_length=120)), ("source_version", models.PositiveIntegerField()), ("source_reference", models.CharField(max_length=240)), ("source_checksum", models.CharField(max_length=64)), ("source_snapshot", models.JSONField()), ("proposed_data", models.JSONField(default=dict)), ("reason", models.CharField(max_length=500)), ("status", models.CharField(choices=[("submitted", "Submitted"), ("under_review", "Under review"), ("accepted", "Accepted"), ("denied", "Denied"), ("appended", "Appended")], default="submitted", max_length=20)), ("submitted_at", models.DateTimeField()), ("due_at", models.DateTimeField()), ("decision_reason", models.CharField(blank=True, default="", max_length=500)), ("decided_at", models.DateTimeField(blank=True, null=True)), ("accepted_version", models.PositiveIntegerField(blank=True, null=True)), ("addendum", models.JSONField(blank=True, null=True)),
            ("patient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="amendments", to="users.patient")), ("requested_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="amendments_requested", to=settings.AUTH_USER_MODEL)), ("reviewer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="amendments_reviewed", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["due_at", "id"]}),
        migrations.CreateModel(name="PatientAmendmentOutbox", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("kind", models.CharField(max_length=80)), ("state", models.CharField(choices=[("pending", "Pending"), ("retry", "Retry"), ("sent", "Sent"), ("failed", "Failed")], default="pending", max_length=12)), ("attempts", models.PositiveSmallIntegerField(default=0)), ("next_attempt_at", models.DateTimeField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("sent_at", models.DateTimeField(blank=True, null=True)), ("last_error_code", models.CharField(blank=True, default="", max_length=80)),
            ("amendment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outbox_events", to="users.patientamendment")),
        ]),
        migrations.CreateModel(name="PatientAmendmentCorrection", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("resource_type", models.CharField(max_length=80)), ("resource_id", models.CharField(max_length=120)), ("version", models.PositiveIntegerField()), ("data", models.JSONField(default=dict)), ("supersedes_version", models.PositiveIntegerField()), ("created_at", models.DateTimeField(auto_now_add=True)), ("amendment", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="correction", to="users.patientamendment")),
        ]),
        migrations.AddIndex(model_name="patientamendment", index=models.Index(fields=["status", "due_at"], name="amendment_queue_idx")),
        migrations.AddIndex(model_name="patientamendment", index=models.Index(fields=["patient", "submitted_at"], name="amendment_patient_idx")),
        migrations.AddConstraint(model_name="patientamendmentcorrection", constraint=models.UniqueConstraint(fields=("resource_type", "resource_id", "version"), name="amendment_correction_version_unique")),
    ]
