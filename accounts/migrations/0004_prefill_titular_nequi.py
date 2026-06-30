from django.db import migrations


def set_titular(apps, schema_editor):
    Negocio = apps.get_model("accounts", "Negocio")
    Negocio.objects.filter(titular_nequi="").update(titular_nequi="Karen Acuña")


def unset_titular(apps, schema_editor):
    # Reversible: dejar vacío de nuevo lo que prellenamos.
    Negocio = apps.get_model("accounts", "Negocio")
    Negocio.objects.filter(titular_nequi="Karen Acuña").update(titular_nequi="")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_negocio_titular_nequi"),
    ]

    operations = [
        migrations.RunPython(set_titular, unset_titular),
    ]
