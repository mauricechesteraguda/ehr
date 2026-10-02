from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    dependencies = [("users", "0019_ticket10_population_exports")]
    operations = [
        migrations.CreateModel(name="CcdaDocument", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("direction", models.CharField(max_length=8)), ("template_id", models.CharField(max_length=120)),
            ("template_version", models.CharField(max_length=40)), ("provenance", models.JSONField(default=dict)),
            ("sha256", models.CharField(max_length=64)), ("size_bytes", models.PositiveBigIntegerField(default=0)),
            ("artifact_path", models.CharField(max_length=500)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("job", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="ccda_document", to="users.job")),
            ("patient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ccda_documents", to="users.patient")),
        ]),
        migrations.CreateModel(name="ReconciliationCandidate", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("section", models.CharField(max_length=30)), ("resource_type", models.CharField(max_length=40)),
            ("payload", models.JSONField()), ("source_fingerprint", models.CharField(max_length=64)),
            ("state", models.CharField(choices=[("pending","Pending"),("accepted","Accepted"),("rejected","Rejected"),("deferred","Deferred"),("stale","Stale"),("conflict","Conflict")], default="pending", max_length=12)),
            ("decided_at", models.DateTimeField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("decided_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="users.user")),
            ("document", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="candidates", to="users.ccdadocument")),
            ("patient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reconciliation_candidates", to="users.patient")),
        ]),
        migrations.AddConstraint(model_name="reconciliationcandidate", constraint=models.UniqueConstraint(fields=("document","source_fingerprint"), name="ccda_candidate_fingerprint_unique")),
    ]
