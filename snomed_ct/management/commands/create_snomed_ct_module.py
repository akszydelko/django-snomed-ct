from __future__ import unicode_literals

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection


class Command(BaseCommand):
    help = 'Create SNOMED CT module, with given name and namespace.'
    release_date = None

    def add_arguments(self, parser):
        parser.add_argument('module_name', type=str)
        parser.add_argument('snomed_ct_namespace', type=int)

    def handle(self, *args, **options):
        # namespace id has to consists of 7 digits
        if options['snomed_ct_namespace'] < 1000000 or options['snomed_ct_namespace'] > 9999999:
            raise CommandError("Invalid namespace id.")

        with transaction.atomic():
            cursor = connection.cursor()

            cursor.execute("""SELECT create_snomed_ct_module(%s, %s);""",
                           [options['module_name'], options['snomed_ct_namespace']])
            module_id = cursor.fetchone()

        if module_id and len(module_id):
            self.stdout.write(self.style.SUCCESS("Successfully created module \"%s\", which got assigned SCTID: %d" % (
                options['module_name'], module_id[0])))
        else:
            raise CommandError("Module creation function does not returned any module SCTID.")
