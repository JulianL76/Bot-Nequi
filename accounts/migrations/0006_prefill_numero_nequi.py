from django.db import migrations


def set_numero(apps, schema_editor):
    Negocio = apps.get_model("accounts", "Negocio")
    Negocio.objects.filter(numero_nequi="").update(numero_nequi="3005941334")


def unset_numero(apps, schema_editor):
    Negocio = apps.get_model("accounts", "Negocio")
    Negocio.objects.filter(numero_nequi="3005941334").update(numero_nequi="")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_negocio_numero_nequi"),
    ]

    operations = [
        migrations.RunPython(set_numero, unset_numero),
    ]
