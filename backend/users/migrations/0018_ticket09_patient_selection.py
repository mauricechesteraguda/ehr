from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("users", "0017_ticket08_break_glass")]

    operations = [
        migrations.AddField(model_name="patient", name="given_name", field=models.CharField(blank=True, default="", max_length=80)),
        migrations.AddField(model_name="patient", name="family_name", field=models.CharField(blank=True, default="", max_length=80)),
        migrations.CreateModel(
            name="SmartTokenContext",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("mfa_generation", models.PositiveIntegerField()),
                ("completed_at", models.DateTimeField()),
                ("access_token", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="mfa_context", to="oauth2_provider.accesstoken")),
                ("application", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mfa_token_contexts", to="oauth2_provider.application")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="smart_token_contexts", to="users.user")),
            ],
        ),
    ]
