from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("users", "0012_ticket04_device_udi")]
    operations = [
        migrations.CreateModel(name="Questionnaire", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("code", models.CharField(max_length=80, unique=True)), ("title", models.CharField(max_length=160)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
        ]),
        migrations.CreateModel(name="QuestionnaireVersion", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("version", models.PositiveIntegerField()), ("status", models.CharField(choices=[("draft", "Draft"), ("active", "Active"), ("retired", "Retired")], default="draft", max_length=12)),
            ("allow_draft", models.BooleanField(default=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="questionnaire_versions_created", to=settings.AUTH_USER_MODEL)),
            ("questionnaire", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="users.questionnaire")),
        ], options={"ordering": ["version"]}),
        migrations.CreateModel(name="QuestionnaireItem", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("link_id", models.CharField(max_length=80)), ("text", models.CharField(max_length=240)),
            ("item_type", models.CharField(choices=[("boolean", "Boolean"), ("integer", "Integer"), ("decimal", "Decimal"), ("date", "Date"), ("string", "String"), ("choice", "Choice"), ("quantity", "Quantity")], max_length=12)), ("ordinal", models.PositiveIntegerField()), ("required", models.BooleanField(default=False)), ("repeats", models.BooleanField(default=False)),
            ("min_length", models.PositiveIntegerField(blank=True, null=True)), ("max_length", models.PositiveIntegerField(blank=True, null=True)), ("min_value", models.DecimalField(blank=True, decimal_places=6, max_digits=20, null=True)), ("max_value", models.DecimalField(blank=True, decimal_places=6, max_digits=20, null=True)), ("options", models.JSONField(blank=True, default=list)),
            ("questionnaire_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="items", to="users.questionnaireversion")),
        ], options={"ordering": ["ordinal", "link_id"]}),
        migrations.CreateModel(name="QuestionnaireResponse", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="questionnaire_responses_created", to=settings.AUTH_USER_MODEL)), ("patient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="questionnaire_responses", to="users.patient")), ("questionnaire", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="responses", to="users.questionnaire")),
        ]),
        migrations.CreateModel(name="QuestionnaireResponseVersion", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("version", models.PositiveIntegerField()), ("status", models.CharField(choices=[("draft", "Draft"), ("submitted", "Submitted"), ("returned", "Returned")], default="draft", max_length=12)), ("answers", models.JSONField(default=dict)), ("submitted_at", models.DateTimeField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="questionnaire_response_versions_created", to=settings.AUTH_USER_MODEL)), ("questionnaire_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="response_versions", to="users.questionnaireversion")), ("response", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="users.questionnaireresponse")), ("supersedes", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="corrections", to="users.questionnaireresponseversion")),
        ], options={"ordering": ["version"]}),
        migrations.CreateModel(name="QuestionnaireReview", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("decision", models.CharField(choices=[("accepted", "Accepted"), ("returned", "Returned"), ("rejected", "Rejected")], max_length=12)), ("reason", models.CharField(blank=True, default="", max_length=500)), ("created_at", models.DateTimeField(auto_now_add=True)), ("response_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reviews", to="users.questionnaireresponseversion")), ("reviewer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="questionnaire_reviews", to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="QuestionnaireOutboxEvent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("kind", models.CharField(max_length=80)), ("created_at", models.DateTimeField(auto_now_add=True)), ("dispatched_at", models.DateTimeField(blank=True, null=True)), ("response_version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outbox_events", to="users.questionnaireresponseversion")),
        ]),
        migrations.AddField(model_name="questionnaire", name="active_version", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="active_for", to="users.questionnaireversion")),
        migrations.AddField(model_name="questionnaireresponse", name="active_version", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="active_for", to="users.questionnaireresponseversion")),
        migrations.AddConstraint(model_name="questionnaireversion", constraint=models.UniqueConstraint(fields=("questionnaire", "version"), name="questionnaire_version_unique")),
        migrations.AddConstraint(model_name="questionnaireitem", constraint=models.UniqueConstraint(fields=("questionnaire_version", "link_id"), name="questionnaire_item_link_unique")),
        migrations.AddConstraint(model_name="questionnaireitem", constraint=models.UniqueConstraint(fields=("questionnaire_version", "ordinal"), name="questionnaire_item_order_unique")),
        migrations.AddConstraint(model_name="questionnaireresponseversion", constraint=models.UniqueConstraint(fields=("response", "version"), name="questionnaire_response_version_unique")),
    ]
