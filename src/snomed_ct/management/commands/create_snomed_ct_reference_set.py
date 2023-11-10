from __future__ import unicode_literals

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection

from ...models import Concept


class Command(BaseCommand):
    help = 'Create SNOMED CT reference set, with given name, module SCTID and namespace.'
    release_date = None

    def add_arguments(self, parser):
        parser.add_argument('reference_set_name', type=str)
        parser.add_argument('module_sctid', type=int)
        parser.add_argument('snomed_ct_namespace', type=int)

    def handle(self, *args, **options):
        # namespace id has to consists of 7 digits
        if options['snomed_ct_namespace'] < 1000000 or options['snomed_ct_namespace'] > 9999999:
            raise CommandError("Invalid namespace id.")

        if not Concept.objects.filter(pk=options['module_sctid']).exists():
            raise CommandError("Module with given SCTID does not exists.")

        with transaction.atomic():
            cursor = connection.cursor()

            cursor.execute("""SELECT create_snomed_ct_reference_set(%s, %s, %s);""",
                           [options['reference_set_name'], options['snomed_ct_namespace'], options['module_sctid']])
            reference_set_id = cursor.fetchone()

        if reference_set_id and len(reference_set_id):
            self.stdout.write(self.style.SUCCESS(
                "Successfully created reference set \"%s\", which got assigned SCTID: %d" % (
                    options['reference_set_name'], reference_set_id[0])))
        else:
            raise CommandError("Reference set creation function does not returned any reference set id.")
