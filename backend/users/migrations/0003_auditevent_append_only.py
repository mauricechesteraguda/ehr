# type-10022026-Maurice: Append-only audit evidence schema and PostgreSQL enforcement.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("users", "0002_patient_observation_device_condition_and_more")]
    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("sequence", models.BigAutoField(primary_key=True, serialize=False)),
                ("occurred_at", models.DateTimeField()),
                ("action", models.CharField(max_length=20)),
                ("resource_type", models.CharField(max_length=80)),
                ("resource_id", models.CharField(max_length=120)),
                ("correlation_id", models.CharField(max_length=80)),
                ("previous_hash", models.CharField(max_length=64)),
                ("current_hash", models.CharField(max_length=64)),
                ("actor", models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="audit_events", to="users.user")),
                ("patient", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="audit_events", to="users.patient")),
            ],
            options={"ordering": ["sequence"]},
        ),
        migrations.AddIndex(model_name="auditevent", index=models.Index(fields=["occurred_at"], name="audit_occurred_at_idx")),
        migrations.AddIndex(model_name="auditevent", index=models.Index(fields=["action"], name="audit_action_idx")),
        migrations.RunSQL("CREATE OR REPLACE FUNCTION ehr_audit_append_only() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'audit events are append-only'; END; $$; CREATE TRIGGER ehr_audit_no_update BEFORE UPDATE OR DELETE ON users_auditevent FOR EACH ROW EXECUTE FUNCTION ehr_audit_append_only();", "DROP TRIGGER IF EXISTS ehr_audit_no_update ON users_auditevent; DROP FUNCTION IF EXISTS ehr_audit_append_only();"),
    ]
