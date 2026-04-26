from django.db import migrations, models
import django.db.models.deletion


def populate_report_code(apps, schema_editor):
    UserReportPermission = apps.get_model("reporting", "UserReportPermission")
    GroupReportPermission = apps.get_model("reporting", "GroupReportPermission")
    for obj in UserReportPermission.objects.exclude(report_id=None):
        obj.report_code = obj.report_id
        obj.save(update_fields=["report_code"])
    for obj in GroupReportPermission.objects.exclude(report_id=None):
        obj.report_code = obj.report_id
        obj.save(update_fields=["report_code"])


class Migration(migrations.Migration):
    dependencies = [
        ("reporting", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="userreportpermission",
            name="report_code",
            field=models.CharField(db_index=True, default="", max_length=255, verbose_name="Report code"),
        ),
        migrations.AddField(
            model_name="groupreportpermission",
            name="report_code",
            field=models.CharField(db_index=True, default="", max_length=255, verbose_name="Report code"),
        ),
        migrations.AlterField(
            model_name="userreportpermission",
            name="report",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="reporting.report",
                verbose_name="Report",
            ),
        ),
        migrations.AlterField(
            model_name="groupreportpermission",
            name="report",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="reporting.report",
                verbose_name="Report",
            ),
        ),
        migrations.RunPython(populate_report_code, migrations.RunPython.noop),
    ]
