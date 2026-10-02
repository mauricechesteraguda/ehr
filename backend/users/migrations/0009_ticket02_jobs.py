from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("users", "0008_developer_role")]
    operations = [
        migrations.CreateModel(name="Job", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("kind", models.CharField(max_length=80)), ("input_checksum", models.CharField(max_length=64)),
            ("redacted_input", models.JSONField(default=dict)), ("idempotency_key", models.CharField(max_length=160)),
            ("state", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("succeeded", "Succeeded"), ("failed", "Failed"), ("expired", "Expired"), ("cancelled", "Cancelled")], default="queued", max_length=20)),
            ("attempts", models.PositiveSmallIntegerField(default=0)), ("max_attempts", models.PositiveSmallIntegerField(default=3)),
            ("queued_at", models.DateTimeField(auto_now_add=True)), ("started_at", models.DateTimeField(blank=True, null=True)), ("finished_at", models.DateTimeField(blank=True, null=True)), ("heartbeat_at", models.DateTimeField(blank=True, null=True)), ("expires_at", models.DateTimeField(blank=True, null=True)), ("error_class", models.CharField(blank=True, default="", max_length=120)), ("error_code", models.CharField(blank=True, default="", max_length=80)), ("result_ref", models.CharField(blank=True, default="", max_length=160)),
            ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="jobs", to="users.user")), ("patient", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="jobs", to="users.patient")),
        ], options={"indexes": [models.Index(fields=["state", "queued_at"], name="job_dispatch_idx"), models.Index(fields=["heartbeat_at"], name="job_heartbeat_idx")]}),
        migrations.CreateModel(name="JobAttempt", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("number", models.PositiveSmallIntegerField()), ("state", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("succeeded", "Succeeded"), ("failed", "Failed"), ("expired", "Expired"), ("cancelled", "Cancelled")], default="running", max_length=20)), ("started_at", models.DateTimeField(auto_now_add=True)), ("finished_at", models.DateTimeField(blank=True, null=True)), ("heartbeat_at", models.DateTimeField(blank=True, null=True)), ("error_class", models.CharField(blank=True, default="", max_length=120)), ("error_code", models.CharField(blank=True, default="", max_length=80)), ("job", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="job_attempts", to="users.job")),
        ], options={"constraints": [models.UniqueConstraint(fields=("job", "number"), name="job_attempt_number_unique")]}),
        migrations.CreateModel(name="OutboxEvent", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("kind", models.CharField(max_length=80)), ("state", models.CharField(choices=[("pending", "Pending"), ("dispatched", "Dispatched")], default="pending", max_length=20)), ("created_at", models.DateTimeField(auto_now_add=True)), ("dispatched_at", models.DateTimeField(blank=True, null=True)), ("claimed_at", models.DateTimeField(blank=True, null=True)), ("attempts", models.PositiveSmallIntegerField(default=0)), ("job", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outbox_events", to="users.job")),
        ], options={"indexes": [models.Index(fields=("state", "created_at"), name="outbox_pending_idx")]}),
        migrations.AddConstraint(model_name="job", constraint=models.UniqueConstraint(fields=("idempotency_key",), name="job_idempotency_unique")),
        migrations.AddConstraint(model_name="job", constraint=models.CheckConstraint(check=models.Q(('max_attempts__gte', 1), ('max_attempts__lte', 3)), name="job_max_attempts_1_3")),
    ]
