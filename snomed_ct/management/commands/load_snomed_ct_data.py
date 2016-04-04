from __future__ import unicode_literals
import os
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection


class Command(BaseCommand):
    help = 'Load SNOMED CT Release into the database.'
    release_date = None

    def add_arguments(self, parser):
        parser.add_argument('snomed_ct_location', type=str)

    def handle(self, *args, **options):
        with transaction.atomic():
            cursor = connection.cursor()
            self.__discover_release_date(options['snomed_ct_location'])

            self.stdout.write('Loading concept file...')
            cursor.execute("""
            COPY sct2_concept(id, effective_time, active, module_id, definition_status_id)
            FROM %s WITH(FORMAT CSV, HEADER TRUE, DELIMITER '\t');
            """, [os.path.join(options['snomed_ct_location'], 'Terminology',
                               'sct2_Concept_Snapshot_INT_%s.txt' % self.release_date)])

            self.stdout.write('Loading description file...')
            cursor.execute("""
            COPY sct2_description(id, effective_time, active, module_id, concept_id, language_code, type_id, term,
                             case_significance_id)
            FROM %s WITH(FORMAT CSV, HEADER TRUE, DELIMITER '\t', QUOTE E'\b');
            """, [os.path.join(options['snomed_ct_location'], 'Terminology',
                               'sct2_Description_Snapshot-en_INT_%s.txt' % self.release_date)])

            self.stdout.write('Loading text definition file...')
            cursor.execute("""
            COPY sct2_text_definition(id, effective_time, active, module_id, concept_id, language_code, type_id, term,
                                 case_significance_id)
            FROM %s WITH(FORMAT CSV, HEADER TRUE, DELIMITER '\t');
            """, [os.path.join(options['snomed_ct_location'], 'Terminology',
                               'sct2_TextDefinition_Snapshot-en_INT_%s.txt' % self.release_date)])

            self.stdout.write('Loading relationship file...')
            cursor.execute("""
            COPY sct2_relationship(id, effective_time, active, module_id, source_id, destination_id, relationship_group,
                              type_id, characteristic_type_id, modifier_id)
            FROM %s WITH(FORMAT CSV, HEADER TRUE, DELIMITER '\t');
            """, [os.path.join(options['snomed_ct_location'], 'Terminology',
                               'sct2_Relationship_Snapshot_INT_%s.txt' % self.release_date)])

            self.stdout.write('Loading stated relationship file...')
            cursor.execute("""
            COPY sct2_stated_relationship(id, effective_time, active, module_id, source_id, destination_id,
                                     relationship_group, type_id, characteristic_type_id, modifier_id)
            FROM %s WITH(FORMAT CSV, HEADER TRUE, DELIMITER '\t');
            """, [os.path.join(options['snomed_ct_location'], 'Terminology',
                               'sct2_StatedRelationship_Snapshot_INT_%s.txt' % self.release_date)])

            self.stdout.write('Loading language reference set file...')
            cursor.execute("""
            COPY sct2_lang_refset(id, effective_time, active, module_id, refset_id, referenced_component_id,
                             acceptability_id)
            FROM %s WITH(FORMAT CSV, HEADER TRUE, DELIMITER '\t');
            """, [
                os.path.join(options['snomed_ct_location'], 'Refset', 'Language',
                             'der2_cRefset_LanguageSnapshot-en_INT_%s.txt' % self.release_date)])

            self.stdout.write('Loading association reference set file...')
            cursor.execute("""
            COPY sct2_association_refset(id, effective_time, active, module_id, refset_id, referenced_component_id,
                                    target_component_id)
            FROM %s WITH(FORMAT CSV, HEADER TRUE, DELIMITER '\t');
            """, [os.path.join(options['snomed_ct_location'], 'Refset', 'Content',
                               'der2_cRefset_AssociationReferenceSnapshot_INT_%s.txt' % self.release_date)])

            self.stdout.write('Loading simple reference set file...')
            cursor.execute("""
            COPY sct2_simple_refset(id, effective_time, active, module_id, refset_id, referenced_component_id)
            FROM %s WITH(FORMAT CSV, HEADER TRUE, DELIMITER '\t');
            """, [os.path.join(options['snomed_ct_location'], 'Refset', 'Content',
                               'der2_Refset_SimpleSnapshot_INT_%s.txt' % self.release_date)])

            self.stdout.write('Loading attribute value reference set file...')
            cursor.execute("""
            COPY sct2_attribute_value_refset(id, effective_time, active, module_id, refset_id, referenced_component_id,
                                        value_id)
            FROM %s WITH(FORMAT CSV, HEADER TRUE, DELIMITER '\t');
            """, [os.path.join(options['snomed_ct_location'], 'Refset', 'Content',
                               'der2_cRefset_AttributeValueSnapshot_INT_%s.txt' % self.release_date)])

            self.stdout.write('Loading simple map reference set file...')
            cursor.execute("""
            COPY sct2_simple_map_refset(id, effective_time, active, module_id, refset_id, referenced_component_id,
                                   map_target)
            FROM %s WITH(FORMAT CSV, HEADER TRUE, DELIMITER '\t');
            """, [os.path.join(options['snomed_ct_location'], 'Refset', 'Map',
                               'der2_sRefset_SimpleMapSnapshot_INT_%s.txt' % self.release_date)])

            self.stdout.write('Loading complex map reference set file...')
            cursor.execute("""
            COPY sct2_complex_map_refset(id, effective_time, active, module_id, refset_id, referenced_component_id,
                                    map_group, map_priority, map_rule, map_advice, map_target, correlation_id)
            FROM %s WITH(FORMAT CSV, HEADER TRUE, DELIMITER '\t');
            """, [os.path.join(options['snomed_ct_location'], 'Refset', 'Map',
                               'der2_iissscRefset_ComplexMapSnapshot_INT_%s.txt' % self.release_date)])

            self.stdout.write('Loading extended map reference set file...')
            cursor.execute("""
            COPY sct2_extended_map_refset(id, effective_time, active, module_id, refset_id, referenced_component_id,
                                     map_group, map_priority, map_rule, map_advice, map_target, correlation_id,
                                     map_category_id)
            FROM %s WITH(FORMAT CSV, HEADER TRUE, DELIMITER '\t');
            """, [os.path.join(options['snomed_ct_location'], 'Refset', 'Map',
                               'der2_iisssccRefset_ExtendedMapSnapshot_INT_%s.txt' % self.release_date)])

        self.stdout.write(self.style.SUCCESS('Successfully loaded SNOMED CT %s release.' % self.release_date))

    def __raise_date_mismatch_error(self):
        raise CommandError("Release files date mismatch. "
                           "Some of the release files are from different release then the others.")

    def __get_location_file_list(self, location):
        return [os.path.join(location, file_name) for file_name in os.listdir(location)]

    def __discover_release_date(self, location):
        release_file_list = []
        release_file_list.extend(self.__get_location_file_list(os.path.join(location, 'Terminology')))
        release_file_list.extend(self.__get_location_file_list(os.path.join(location, 'Refset', 'Language')))
        release_file_list.extend(self.__get_location_file_list(os.path.join(location, 'Refset', 'Content')))
        release_file_list.extend(self.__get_location_file_list(os.path.join(location, 'Refset', 'Map')))

        for file_path in release_file_list:
            file_name = os.path.basename(file_path)
            match = re.match(r'(sct2|der2)_[\w\-_]+(?P<date>\d{8})\.txt', file_name)

            if not self.release_date:
                self.release_date = match.group('date')
            elif self.release_date != match.group('date'):
                self.__raise_date_mismatch_error()
