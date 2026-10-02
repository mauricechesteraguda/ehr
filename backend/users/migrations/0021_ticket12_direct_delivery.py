from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("users", "0020_ticket11_ccda")]

    operations = [
        migrations.AddField(model_name="ccdadocument", name="expires_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.CreateModel(
            name="DirectDelivery",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("recipient_hash", models.CharField(max_length=64)),
                ("recipient_ciphertext", models.BinaryField()),
                ("purpose", models.CharField(max_length=240)),
                ("idempotency_key", models.CharField(max_length=160, unique=True)),
                ("state", models.CharField(choices=[("queued", "Queued"), ("sending", "Sending"), ("sent", "Sent"), ("failed", "Failed"), ("expired", "Expired"), ("cancelled", "Cancelled")], default="queued", max_length=20)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("max_attempts", models.PositiveSmallIntegerField(default=3)),
                ("error_code", models.CharField(blank=True, default="", max_length=40)),
                ("receipt_code", models.CharField(blank=True, default="", max_length=80)),
                ("receipt_checksum", models.CharField(blank=True, default="", max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("artifact", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="direct_deliveries", to="users.ccdadocument")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="direct_deliveries", to="users.user")),
            ],
            options={"indexes": [models.Index(fields=("owner", "created_at"), name="direct_owner_created_idx")], "constraints": [models.CheckConstraint(check=models.Q(max_attempts__gte=1, max_attempts__lte=3), name="direct_max_attempts_1_3")]},
        ),
        migrations.CreateModel(
            name="DirectDeliveryAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.PositiveSmallIntegerField()),
                ("state", models.CharField(choices=[("queued", "Queued"), ("sending", "Sending"), ("sent", "Sent"), ("failed", "Failed"), ("expired", "Expired"), ("cancelled", "Cancelled")], max_length=20)),
                ("outcome_code", models.CharField(blank=True, default="", max_length=40)),
                ("receipt_checksum", models.CharField(blank=True, default="", max_length=64)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("delivery", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="delivery_attempts", to="users.directdelivery")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("delivery", "number"), name="direct_attempt_number_unique")]},
        ),
        migrations.CreateModel(
            name="DirectDeliveryOutbox",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("dispatched_at", models.DateTimeField(blank=True, null=True)),
                ("delivery", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="outbox", to="users.directdelivery")),
            ],
        ),
    ]
