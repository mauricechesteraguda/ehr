from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0015_ticket07_passkeys'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smsrecoverychallenge',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='webauthnchallenge',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='webauthncredential',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]
