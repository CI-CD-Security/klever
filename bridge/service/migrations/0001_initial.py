# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2017-01-09 21:57
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('jobs', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Node',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('USER_OCCUPIED', 'User occupied'), ('HEALTHY', 'Healthy'), ('AILING', 'Ailing'), ('DISCONNECTED', 'Disconnected')], max_length=13)),
                ('hostname', models.CharField(max_length=128)),
            ],
            options={
                'db_table': 'node',
            },
        ),
        migrations.CreateModel(
            name='NodesConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cpu', models.CharField(max_length=128)),
                ('cores', models.PositiveSmallIntegerField()),
                ('ram', models.BigIntegerField()),
                ('memory', models.BigIntegerField()),
            ],
            options={
                'db_table': 'nodes_configuration',
            },
        ),
        migrations.CreateModel(
            name='Scheduler',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('0', 'Klever'), ('1', 'VerifierCloud')], max_length=1)),
                ('status', models.CharField(choices=[('HEALTHY', 'Healthy'), ('AILING', 'Ailing'), ('DISCONNECTED', 'Disconnected')], default='AILING', max_length=12)),
            ],
            options={
                'db_table': 'scheduler',
            },
        ),
        migrations.CreateModel(
            name='SchedulerUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('login', models.CharField(max_length=128)),
                ('password', models.CharField(max_length=128)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'scheduler_user',
            },
        ),
        migrations.CreateModel(
            name='Solution',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.BinaryField()),
                ('archname', models.CharField(max_length=256)),
                ('archive', models.FileField(upload_to='Service')),
            ],
            options={
                'db_table': 'solution',
            },
        ),
        migrations.CreateModel(
            name='SolvingProgress',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('priority', models.CharField(choices=[('URGENT', 'Urgent'), ('HIGH', 'High'), ('LOW', 'Low'), ('IDLE', 'Idle')], max_length=6)),
                ('start_date', models.DateTimeField(null=True)),
                ('finish_date', models.DateTimeField(null=True)),
                ('tasks_total', models.PositiveIntegerField(default=0)),
                ('tasks_pending', models.PositiveIntegerField(default=0)),
                ('tasks_processing', models.PositiveIntegerField(default=0)),
                ('tasks_finished', models.PositiveIntegerField(default=0)),
                ('tasks_error', models.PositiveIntegerField(default=0)),
                ('tasks_cancelled', models.PositiveIntegerField(default=0)),
                ('solutions', models.PositiveIntegerField(default=0)),
                ('error', models.CharField(max_length=1024, null=True)),
                ('configuration', models.BinaryField()),
                ('job', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='jobs.Job')),
                ('scheduler', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='service.Scheduler')),
            ],
            options={
                'db_table': 'solving_progress',
            },
        ),
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('PROCESSING', 'Processing'), ('FINISHED', 'Finished'), ('ERROR', 'Error'), ('CANCELLED', 'Cancelled')], default='PENDING', max_length=10)),
                ('error', models.CharField(max_length=1024, null=True)),
                ('description', models.BinaryField()),
                ('archname', models.CharField(max_length=256)),
                ('archive', models.FileField(upload_to='Service')),
                ('progress', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='service.SolvingProgress')),
            ],
            options={
                'db_table': 'task',
            },
        ),
        migrations.CreateModel(
            name='VerificationTool',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('version', models.CharField(max_length=128)),
                ('scheduler', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='service.Scheduler')),
            ],
            options={
                'db_table': 'verification_tool',
            },
        ),
        migrations.CreateModel(
            name='Workload',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jobs', models.PositiveIntegerField()),
                ('tasks', models.PositiveIntegerField()),
                ('cores', models.PositiveSmallIntegerField()),
                ('ram', models.BigIntegerField()),
                ('memory', models.BigIntegerField()),
                ('for_tasks', models.BooleanField()),
                ('for_jobs', models.BooleanField()),
            ],
            options={
                'db_table': 'workload',
            },
        ),
        migrations.AddField(
            model_name='solution',
            name='task',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='service.Task'),
        ),
        migrations.AddField(
            model_name='node',
            name='config',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='service.NodesConfiguration'),
        ),
        migrations.AddField(
            model_name='node',
            name='workload',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='service.Workload'),
        ),
    ]
