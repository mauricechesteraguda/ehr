from django.db import migrations, models
import django.db.models.deletion
import uuid


def seed_demo(apps, schema_editor):
    Service = apps.get_model("users", "CDSService")
    Rule = apps.get_model("users", "CDSRuleVersion")
    medication = Service.objects.create(id="demo-medication-safety", hook="medication-prescribe", title="Medication safety demo")
    patient = Service.objects.create(id="demo-patient-view", hook="patient-view", title="Patient safety demo")
    Rule.objects.create(service=medication, rule_key="allergy-warning", version=1, status="active", safety_critical=True, config={"kind": "DRUG_ALLERGY"}, published_at=__import__("django.utils.timezone", fromlist=["now"]).now())
    Rule.objects.create(service=medication, rule_key="interaction-reminder", version=1, status="active", config={"kind": "DRUG_DRUG"}, published_at=__import__("django.utils.timezone", fromlist=["now"]).now())
    Rule.objects.create(service=patient, rule_key="allergy-warning", version=1, status="active", safety_critical=True, config={"kind": "DRUG_ALLERGY"}, published_at=__import__("django.utils.timezone", fromlist=["now"]).now())


class Migration(migrations.Migration):
    dependencies = [("users", "0021_ticket12_direct_delivery")]
    operations = [
        migrations.CreateModel(name="CDSService", fields=[
            ("id", models.CharField(max_length=80, primary_key=True, serialize=False)),
            ("hook", models.CharField(max_length=40)), ("title", models.CharField(max_length=160)),
            ("description", models.CharField(default="Deterministic non-clinical demo", max_length=240)),
            ("version", models.CharField(default="1.0.0", max_length=20)), ("active", models.BooleanField(default=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
        ]),
        migrations.CreateModel(name="CDSRuleVersion", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("rule_key", models.CharField(max_length=80)), ("version", models.PositiveIntegerField()),
            ("status", models.CharField(choices=[("draft", "Draft"), ("active", "Active"), ("retired", "Retired")], default="draft", max_length=10)),
            ("config", models.JSONField(default=dict)), ("safety_critical", models.BooleanField(default=False)),
            ("published_at", models.DateTimeField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("service", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="rules", to="users.cdsservice")),
        ]),
        migrations.CreateModel(name="CDSInvocation", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("request_key", models.CharField(max_length=120)),
            ("hook", models.CharField(max_length=40)), ("context_fingerprint", models.CharField(max_length=64)), ("outcome", models.CharField(default="success", max_length=20)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("patient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="users.patient")), ("service", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="users.cdsservice")),
        ]),
        migrations.CreateModel(name="CDSCard", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("summary", models.CharField(max_length=240)), ("detail", models.CharField(max_length=500)), ("indicator", models.CharField(max_length=10)), ("source", models.JSONField(default=dict)), ("suggestions", models.JSONField(default=list)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("invocation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cards", to="users.cdsinvocation")), ("rule", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="users.cdsruleversion")),
        ]),
        migrations.CreateModel(name="CDSCardAction", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("action", models.CharField(choices=[("accept", "Accept"), ("dismiss", "Dismiss"), ("override", "Override")], max_length=10)), ("suggestion_id", models.CharField(blank=True, default="", max_length=80)), ("reason", models.CharField(blank=True, default="", max_length=500)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="users.user")), ("card", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="actions", to="users.cdscard")),
        ]),
        migrations.CreateModel(name="CDSOutboxEvent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("kind", models.CharField(max_length=40)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("card", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="users.cdscard")), ("invocation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="outbox_events", to="users.cdsinvocation")),
        ]),
        migrations.AddConstraint(model_name="cdsservice", constraint=models.UniqueConstraint(fields=("id", "version"), name="cds_service_version_unique")),
        migrations.AddConstraint(model_name="cdsruleversion", constraint=models.UniqueConstraint(fields=("service", "rule_key", "version"), name="cds_rule_version_unique")),
        migrations.AddConstraint(model_name="cdsinvocation", constraint=models.UniqueConstraint(fields=("service", "request_key"), name="cds_invocation_idempotency_unique")),
        migrations.AddConstraint(model_name="cdscardaction", constraint=models.UniqueConstraint(fields=("card", "actor", "action", "suggestion_id"), name="cds_card_action_idempotent")),
        migrations.RunPython(seed_demo, migrations.RunPython.noop),
    ]
