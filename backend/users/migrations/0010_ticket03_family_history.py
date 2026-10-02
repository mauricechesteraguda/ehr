# type-10022026-Maurice: Ticket03 family-history schema; synthetic values only.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("users", "0009_ticket02_jobs")]
    operations = [
        migrations.CreateModel(name="FamilyHistory", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("patient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="family_histories", to="users.patient")),
        ]),
        migrations.CreateModel(name="FamilyHistoryVersion", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("version", models.PositiveIntegerField()), ("relationship", models.CharField(max_length=40)),
            ("relative_sex", models.CharField(default="unknown", max_length=20)), ("relative_status", models.CharField(default="unknown", max_length=30)),
            ("relative_deceased", models.BooleanField(blank=True, null=True)), ("condition_system", models.URLField(max_length=300)),
            ("condition_code", models.CharField(max_length=80)), ("condition_display", models.CharField(max_length=240)),
            ("submitted_display", models.CharField(blank=True, default="", max_length=240)), ("terminology_version", models.CharField(blank=True, default="", max_length=80)),
            ("onset_date", models.DateField(blank=True, null=True)), ("recorded_date", models.DateField(blank=True, null=True)),
            ("status", models.CharField(choices=[("active", "Active"), ("entered-in-error", "Entered in error")], default="active", max_length=20)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="family_history_versions_created", to=settings.AUTH_USER_MODEL)),
            ("history", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="users.familyhistory")),
            ("supersedes", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="superseded_by", to="users.familyhistoryversion")),
        ]),
        migrations.AddField(model_name="familyhistory", name="active_version", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="active_for", to="users.familyhistoryversion")),
        migrations.AddConstraint(model_name="familyhistoryversion", constraint=models.UniqueConstraint(fields=("history", "version"), name="family_history_version_unique")),
        migrations.CreateModel(name="FamilyHistoryOutboxEvent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("kind", models.CharField(max_length=80)), ("created_at", models.DateTimeField(auto_now_add=True)), ("dispatched_at", models.DateTimeField(blank=True, null=True)),
            ("family_history", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outbox_events", to="users.familyhistory")), ("version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="users.familyhistoryversion")),
        ]),
    ]
