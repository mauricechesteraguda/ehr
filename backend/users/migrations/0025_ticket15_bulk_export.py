from django.db import migrations, models
import uuid

class Migration(migrations.Migration):
    dependencies = [("users", "0024_ticket14_allergy_status")]
    operations = [migrations.CreateModel(name="FHIRBulkExport", fields=[
        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
        ("resource_types", models.JSONField(default=list)), ("since", models.DateTimeField(blank=True, null=True)),
        ("purpose", models.CharField(max_length=500)), ("approval", models.CharField(max_length=500)),
        ("transaction_time", models.DateTimeField(blank=True, null=True)), ("request_url", models.CharField(max_length=500)),
        ("requires_access_token", models.BooleanField(default=True)), ("entries", models.JSONField(default=list)),
        ("errors", models.JSONField(default=list)), ("total_bytes", models.PositiveBigIntegerField(default=0)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("job", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="bulk_export", to="users.job")),
    ])]
