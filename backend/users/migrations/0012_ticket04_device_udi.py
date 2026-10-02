# Ticket04: immutable device versions and atomic integration intent.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("users", "0011_alter_familyhistoryversion_options")]
    operations = [
        migrations.CreateModel(
            name="DeviceVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveIntegerField()), ("code", models.CharField(max_length=80)),
                ("label", models.CharField(max_length=160)), ("status", models.CharField(choices=[("active", "Active"), ("inactive", "Inactive"), ("entered-in-error", "Entered in error")], default="active", max_length=20)),
                ("issuer", models.CharField(max_length=20)), ("device_identifier", models.CharField(blank=True, default="", max_length=80)),
                ("lot_number", models.CharField(blank=True, default="", max_length=20)), ("serial_number", models.CharField(blank=True, default="", max_length=20)),
                ("expiry_date", models.DateField(blank=True, null=True)), ("manufacture_date", models.DateField(blank=True, null=True)),
                ("raw_input", models.CharField(blank=True, default="", max_length=256)), ("parser_version", models.CharField(max_length=40)),
                ("parse_status", models.CharField(choices=[("parsed", "Parsed"), ("parse_failed", "Parse failed"), ("unsupported", "Unsupported")], max_length=20)),
                ("parse_error_code", models.CharField(blank=True, default="", max_length=50)), ("gudid_status", models.CharField(default="not_requested", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="device_versions_created", to=settings.AUTH_USER_MODEL)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="users.device")),
                ("supersedes", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="superseded_by", to="users.deviceversion")),
            ], options={"ordering": ["version"]},
        ),
        migrations.AddField(model_name="device", name="udi", field=models.CharField(blank=True, default="", max_length=256)),
        migrations.AddField(model_name="device", name="active_version", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="active_for", to="users.deviceversion")),
        migrations.CreateModel(name="DeviceOutboxEvent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("kind", models.CharField(max_length=80)), ("created_at", models.DateTimeField(auto_now_add=True)), ("dispatched_at", models.DateTimeField(blank=True, null=True)),
            ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outbox_events", to="users.device")), ("version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="users.deviceversion")),
        ]),
        migrations.AddConstraint(model_name="deviceversion", constraint=models.UniqueConstraint(fields=("device", "version"), name="device_version_unique")),
        migrations.AddConstraint(model_name="device", constraint=models.UniqueConstraint(condition=~models.Q(udi=""), fields=("patient", "udi"), name="device_patient_udi_unique")),
    ]
