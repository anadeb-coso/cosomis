# Generated by Django 4.1.1 on 2022-09-28 11:07

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('administrativelevels', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='administrativelevel',
            name='created_date',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='administrativelevel',
            name='updated_date',
            field=models.DateTimeField(auto_now=True),
        ),
    ]