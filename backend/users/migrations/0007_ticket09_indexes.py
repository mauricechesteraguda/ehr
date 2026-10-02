# type-10022026-Maurice: Ticket09 query indexes for bounded admin and safety reads.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users", "0006_patientexport")]
    operations = [
        migrations.AddIndex(model_name="user", index=models.Index(fields=["role", "is_active"], name="user_role_active_idx")),
        migrations.AddIndex(model_name="interactionrule", index=models.Index(fields=["active", "severity"], name="rule_active_severity_idx")),
        migrations.AddIndex(model_name="interactionrule", index=models.Index(fields=["medication_code", "active"], name="rule_med_active_idx")),
        migrations.AddIndex(model_name="alertconfiguration", index=models.Index(fields=["severity_floor"], name="alert_floor_idx")),
    ]
