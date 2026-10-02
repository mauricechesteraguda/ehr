# type-10022026-Maurice: Ticket 05 interaction safety evidence and signing schema.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("users", "0004_medicationorder_medicationorderversion_and_more")]
    operations = [
        migrations.CreateModel(name="AlertConfiguration", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("singleton", models.BooleanField(default=True, unique=True)),
            ("severity_floor", models.CharField(choices=[("LOW", "Low"), ("MODERATE", "Moderate"), ("HIGH", "High")], default="LOW", max_length=10)),
            ("updated_at", models.DateTimeField(auto_now=True)),
        ]),
        migrations.CreateModel(name="InteractionRule", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("kind", models.CharField(choices=[("DRUG_DRUG", "Drug-drug"), ("DRUG_ALLERGY", "Drug-allergy")], max_length=20)),
            ("medication_code", models.CharField(max_length=80)), ("related_medication_code", models.CharField(blank=True, default="", max_length=80)),
            ("allergy_code", models.CharField(blank=True, default="", max_length=80)),
            ("severity", models.CharField(choices=[("LOW", "Low"), ("MODERATE", "Moderate"), ("HIGH", "High"), ("CRITICAL", "Critical")], max_length=10)),
            ("description", models.CharField(default="Synthetic demo rule", max_length=240)), ("active", models.BooleanField(default=True)),
            ("effective_from", models.DateTimeField(blank=True, null=True)), ("effective_to", models.DateTimeField(blank=True, null=True)), ("updated_at", models.DateTimeField(auto_now=True)),
        ]),
        migrations.CreateModel(name="InteractionEvaluation", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("evaluated_at", models.DateTimeField()), ("fingerprint", models.CharField(max_length=64)), ("floor", models.CharField(max_length=10)), ("findings", models.JSONField(default=list)), ("stale", models.BooleanField(default=False)),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="interaction_evaluations", to=settings.AUTH_USER_MODEL)),
            ("medication_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="evaluations", to="users.medicationorderversion")),
        ]),
        migrations.CreateModel(name="InteractionAcknowledgement", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("acknowledged_at", models.DateTimeField()),
            ("clinician", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="interaction_acknowledgements", to=settings.AUTH_USER_MODEL)),
            ("evaluation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="acknowledgements", to="users.interactionevaluation")),
        ]),
    ]
