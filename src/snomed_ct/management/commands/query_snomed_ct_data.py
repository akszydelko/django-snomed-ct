try:
    from tqdm import tqdm
except ImportError:
    def tqdm(item):
        return item
from datetime import date, datetime

from django.core.management.base import BaseCommand
from snomed_ct.models import Concept, ICD10_Mapping, TextSearchTypes, ISA, pretty_print_list
from snomed_ct.controlled_natural_language import ControlledEnglishGenerator, MalformedSNOMEDExpressionError


class Command(BaseCommand):
    help = 'Query SNOMED CT Release from the database.'
    release_date = None

    def __init__(self):
        super().__init__()
        self.today = datetime.now().date()

    def add_arguments(self, parser):
        parser.add_argument('search_terms', type=str, nargs='+')
        parser.add_argument('-qt', '--query-type', dest='query_type',
                            help="What the search is matching against: 'ICD' (name), 'ICD_CODE', 'SNOMED_CODE', "
                                 "or 'SNOMED'",
                            choices=['ICD', 'ICD_CODE', 'SNOMED', 'SNOMED_CODE'], default='SNOMED', type=str)
        parser.add_argument('-rx', '--regex', action='store_true', dest='regex',
                            help='The query is a REGEX, otherwise it is a case-insensitive substring to match',
                            default=False)
        parser.add_argument('-d', '--def-only', action='store_true', dest='def_only',
                            help='Ony show concepts with textual definitions',
                            default=False)
        parser.add_argument('-s', '--icd-name-similarity', type=float, dest='similarity',
                            help='Only include SNOMED concepts whose name is at least as similar to that of the ICD'
                                 'code it is mapped to as measured by the 0 to 1 similarity score '
                                 '.  It defaults to 0, which will skip this comparison (requires python-levenshtein)',
                            default=0)
        parser.add_argument('-r', '--logically-related', action='store_true', dest='related',
                            help='Show concepts logically related to those matched',
                            default=False)
        parser.add_argument('-o', '--output-type', dest='output_type',
                            help="How to print the matching concepts: 'relations', 'english', 'name'",
                            choices=['relations', 'english', 'name'], default='name', type=str)

    def render_concept(self, concept, output_type, related=-1, rendered=None):
        rendered = rendered if rendered else set()
        if concept.id not in rendered:
            concept_name = concept.fully_specified_name_no_type
            other_terms = set(concept.get_preferred_term().terms) - {concept_name}
            alternative_terms = "({})".format(", ".join(concept.get_preferred_term().terms)) if other_terms else ""
            print("---" * 5, f"{concept.id}|{concept_name}", alternative_terms, "---" * 10)
            definitions = concept.definitions().filter(active=True)
            if definitions.exists():
                print("--- Textual definitions ", "---" * 30)
                for defn in definitions:
                    print(defn.term)
                print("---" * 30)
            if output_type == 'relations':
                prior_group = None
                for rel in concept.outbound_relationships().filter(active=True).order_by('relationship_group'):
                    if rel.relationship_group != prior_group and prior_group is not None:
                        print("")
                    print(f"\t- {rel.type} -> {rel.destination} [{rel.relationship_group}]")
                    prior_group = rel.relationship_group
            elif output_type == 'english':
                try:
                    print(ControlledEnglishGenerator(concept).get_controlled_english_definition(embed_ids=True))
                except MalformedSNOMEDExpressionError as e:
                    print("Skipping (malformed expression)", e)
            else:
                print(concept)
            mappings = (concept.icd10_mappings.filter(map_rule='TRUE')
                                              .exclude(map_target__isnull=True)
                                              .exclude(map_target__exact=''))
            if mappings.exists():
                print("ICD 10 Mappings:", ", ".join(["{} ({})".format(map.map_target, map.map_target_name)
                                                     for map in mappings]) )
            rendered.add(concept.id)
            if related >= 1:
                print("{} Related {}".format("---" * 5, "---" * 10))
                for c in concept.outbound_relationships().filter(active=True, type_id=ISA).destinations():
                    self.render_concept(c, output_type, related=related-1, rendered=rendered)
                for c in concept.inbound_relationships().filter(active=True).exclude(type_id=ISA).sources():
                    self.render_concept(c, output_type, related=related-1, rendered=rendered)

    def handle(self, *args, **options):
        search_type = (TextSearchTypes.CASE_INSENSITIVE_REGEX if options['regex']
                       else TextSearchTypes.CASE_INSENSITIVE_CONTAINS)
        rendered_concepts = set()
        if options['query_type'] == 'SNOMED':
            concepts = Concept.by_fully_specified_name(options['search_terms'], search_type=search_type)
            concepts = concepts.has_definitions() if options['def_only'] else concepts
            for concept in concepts.is_active():
                self.render_concept(concept, options['output_type'], 1 if options['related'] else -1,
                                    rendered=rendered_concepts)
        elif options['query_type'] == 'SNOMED_CODE':
            concepts = Concept.objects.by_ids(options['search_terms'])
            concepts = concepts.has_definitions() if options['def_only'] else concepts
            for concept in concepts.is_active():
                self.render_concept(concept, options['output_type'], 1 if options['related'] else -1,
                                    rendered=rendered_concepts)
        elif options['query_type'] == 'ICD_CODE':
            mappings = ICD10_Mapping.objects.by_icd_codes(options['search_terms'])
            mappings = mappings.has_definitions() if options['def_only'] else mappings
            for mapping in mappings:
                concept = mapping.referenced_component
                icd_name = mapping.map_target_name.split(', unspecified')[0]
                if concept.active:
                    render = True
                    if options['similarity'] > float(0):
                        try:
                            from Levenshtein import ratio
                            score1 = ratio(concept.fully_specified_name_no_type, icd_name)
                            score2 = max([ratio(syn, icd_name) for syn in concept.get_preferred_term().terms])
                            if score1 < options['similarity'] or score2 < options['similarity']:
                                render = False
                        except ImportError:
                            raise NotImplemented("Please install python-Levenshtein")
                    if render:
                        self.render_concept(concept, options['output_type'], 1 if options['related'] else -1,
                                            rendered=rendered_concepts)
        else:
            mappings = ICD10_Mapping.objects.by_icd_names(options['search_terms'], search_type=search_type)
            mappings = mappings.has_definitions() if options['def_only'] else mappings
            for mapping in mappings:
                if mapping.referenced_component.active:
                    self.render_concept(mapping.referenced_component, options['output_type'],
                                        1 if options['related'] else -1,
                                        rendered=rendered_concepts)

