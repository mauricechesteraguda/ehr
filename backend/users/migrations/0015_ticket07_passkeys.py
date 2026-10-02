from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("users", "0014_ticket06_amendments")]
    operations = [
        migrations.AddField(model_name="user", name="recovery_phone_hash", field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="user", name="mfa_generation", field=models.PositiveIntegerField(default=0)),
        migrations.CreateModel(name="WebAuthnCredential", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)), ("credential_id", models.BinaryField(unique=True)), ("public_key", models.BinaryField()), ("sign_count", models.PositiveBigIntegerField(default=0)), ("transports", models.JSONField(default=list)), ("backup_eligible", models.BooleanField(default=False)), ("backup_state", models.BooleanField(default=False)), ("user_verified", models.BooleanField(default=False)), ("name", models.CharField(default="Passkey", max_length=80)), ("revoked_at", models.DateTimeField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="webauthn_credentials", to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="WebAuthnChallenge", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)), ("session_key", models.CharField(max_length=40)), ("challenge_hash", models.CharField(max_length=64, unique=True)), ("ceremony", models.CharField(max_length=16)), ("expires_at", models.DateTimeField()), ("used_at", models.DateTimeField(blank=True, null=True)), ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="SmsRecoveryChallenge", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)), ("code_hash", models.CharField(max_length=64)), ("expires_at", models.DateTimeField()), ("attempts", models.PositiveSmallIntegerField(default=0)), ("used_at", models.DateTimeField(blank=True, null=True)), ("delivery_reference", models.CharField(max_length=80)), ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ]),
    ]
