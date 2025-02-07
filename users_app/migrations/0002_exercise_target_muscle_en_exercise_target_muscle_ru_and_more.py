# Generated by Django 5.1.2 on 2024-12-29 06:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users_app', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='exercise',
            name='target_muscle_en',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='exercise',
            name='target_muscle_ru',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='exercise',
            name='target_muscle_uz',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
