# Generated by Django 4.2.1 on 2023-05-26 08:17

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupReportPermission",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("view", models.BooleanField(default=True, verbose_name="View")),
                ("print", models.BooleanField(default=True, verbose_name="Print")),
                ("export", models.BooleanField(default=True, verbose_name="Export")),
                ("deleted", models.BooleanField(default=False, verbose_name="deleted")),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="auth.group",
                        verbose_name="Group",
                    ),
                ),
            ],
            options={
                "verbose_name": "Group Report Permission",
                "verbose_name_plural": "Group Report Permissions",
            },
        ),
        migrations.CreateModel(
            name="Report",
            fields=[
                (
                    "code",
                    models.CharField(
                        editable=False,
                        max_length=255,
                        primary_key=True,
                        serialize=False,
                        verbose_name="Code",
                    ),
                ),
                ("deleted", models.BooleanField(default=False, verbose_name="deleted")),
                (
                    "groups",
                    models.ManyToManyField(
                        through="reporting.GroupReportPermission",
                        to="auth.group",
                        verbose_name="Groups",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="UserReportPermission",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("view", models.BooleanField(default=True, verbose_name="View")),
                ("print", models.BooleanField(default=True, verbose_name="Print")),
                ("export", models.BooleanField(default=True, verbose_name="Export")),
                ("deleted", models.BooleanField(default=False, verbose_name="deleted")),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="reporting.report",
                        verbose_name="Report",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="User",
                    ),
                ),
            ],
            options={
                "verbose_name": "User Report Permission",
                "verbose_name_plural": "User Report Permissions",
            },
        ),
        migrations.AddField(
            model_name="report",
            name="users",
            field=models.ManyToManyField(
                through="reporting.UserReportPermission",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Users",
            ),
        ),
        migrations.AddField(
            model_name="groupreportpermission",
            name="report",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="reporting.report",
                verbose_name="Report",
            ),
        ),
    ]