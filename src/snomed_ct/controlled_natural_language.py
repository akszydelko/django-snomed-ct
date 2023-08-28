import django
django.setup()
from snomed_ct.models import (ISA, ATTRIBUTE_HUMAN_READABLE_NAMES, pretty_print_list, Concept, ASSOCIATED_MORPHOLOGY,
                              FINDING_SITE)
from random import choice

INTERPRETS = 363714003
HAS_INTERPRETATION = 363713009
TODDLER_PERIOD = 713153009
NEO_NATAL_PERIOD = 255407002
CONGENITAL = 255399007
OCCURRENCE = 246454002
CLINICAL_COURSE = 263502005
PATHOLOGICAL_PROCESS = 370135005
DUE_TO = 42752001
CAUSATIVE_AGENT = 246075003
AFTER = 255234002
METHOD = 260686004
ADMINISTERED_SUBSTANCE = 363701004
HAS_INTENT = 363703001
ASSOCIATED_FINDING = 246090004
SUBJECT_RELATIONSHIP_CONTEXT = 408732007

class MalformedSNOMEDExpressionError(Exception):
    pass


class SnomedNounRenderer:

    def __init__(self, id_reference=False):
        self.id_reference = id_reference

    def render_concept(self, concept):
        return concept.fully_specified_name_no_type.lower() if not self.id_reference else "{} ({})".format(
            concept.fully_specified_name_no_type.lower(), concept.id)


class RolePairRenderer(SnomedNounRenderer):
    can_collapse_objects = False
    target_id = None
    object_id = None

    def __init__(self, relationships, id_reference=False):
        super().__init__(id_reference)
        self.relationships = relationships

    def interpretation_subject_name(self, concept):
        return self.render_concept(concept)

    def render(self, relationships=None):
        raise Exception("Needs to be overridden")


class InterpretationRolePairRenderer(RolePairRenderer):
    target_id = INTERPRETS
    object_id = HAS_INTERPRETATION

    def render(self, relationships=None):
        object_pair_rels = self.relationships.filter(type_id=self.object_id)
        if object_pair_rels.count() != 1:
            raise MalformedSNOMEDExpressionError("Unexpected number of {} and {} in {}".format(
                            self.target_id,
                            self.object_id,
                            self.relationships
                        ))
        pair_targets = self.relationships.filter(type_id=self.target_id).destinations()
        pair_object = object_pair_rels.destinations()[0]
        return "is an interpretation of {} as {}".format(
            pretty_print_list(list(map(lambda c: self.interpretation_subject_name(c),
                                       pair_targets)),
                              and_char=", and "),
            self.render_concept(pair_object))

class MethodApplicationRenderer(RolePairRenderer):
    target_id = METHOD
    object_id = ADMINISTERED_SUBSTANCE

    def render(self, relationships=None):
        object_pair_rels = self.relationships.filter(type_id=self.object_id)
        if object_pair_rels.count() != 1:
            raise MalformedSNOMEDExpressionError("Unexpected number of {} and {} in {}".format(
                            self.target_id,
                            self.object_id,
                            self.relationships
                        ))
        method_type = self.relationships.filter(type_id=self.target_id).destinations()[0]
        method_object = object_pair_rels.destinations()[0]
        return "is the {} of some {}".format(self.render_concept(method_type), self.render_concept(method_object))

ROLE_PAIR_RENDERER_MAPPING = {
    INTERPRETS: InterpretationRolePairRenderer,
    METHOD: MethodApplicationRenderer
}


class RoleRenderer(SnomedNounRenderer):
    can_collapse_objects = False

    def __init__(self, relationship, id_reference=False):
        super().__init__(id_reference)
        self.is_lengthy = False
        self.relationship = relationship
        self.role_phrase = ATTRIBUTE_HUMAN_READABLE_NAMES.get(self.relationship.type.id,
                                                              self.relationship.type.fully_specified_name_no_type)


    def render(self, relationships=None):
        return "{} some {}".format(
            self.role_phrase,
            self.render_concept(self.relationship.destination))


class NullRenderer(RoleRenderer):
    def render(self, relationships=None):
        return ""


class RelationshipAsIsaRenderer(RoleRenderer):
    def __init__(self, relationship, with_article=False, id_reference=False):
        super().__init__(relationship, id_reference=id_reference)
        self.with_article = with_article

    def render(self, relationships=None):
        object_name = self.render_concept(self.relationship.destination)
        if self.with_article:
            return f"is {prefix_with_indefinite_article(object_name[0].lower() + object_name[1:], unquoted=True)}"
        else:
            return f"is {object_name.lower()}"


class AlternativeNameRoleRenderer(RoleRenderer):
    can_collapse_objects = True

    def __init__(self, alternative_role_name, relationship, id_reference=False):
        super().__init__(relationship, id_reference=id_reference)
        self.alternative_role_name = alternative_role_name

    def render(self, relationships=None):
        relation_qs = relationships.filter(type=self.relationship.type)
        if relation_qs.count() > 1:
            object_phrase = pretty_print_list([self.render_concept(rel.destination)
                                               for rel in relation_qs], and_char=", and ")
        else:
            object_phrase = self.render_concept(self.relationship.destination)
        return f"{self.alternative_role_name} some {object_phrase}"


class OccursRenderer(RoleRenderer):
    def render(self, relationships=None):
        if self.relationship.destination.id == TODDLER_PERIOD:
            return "occurs as a toddler"
        elif self.relationship.destination.id == NEO_NATAL_PERIOD:
            return "occurs during neonatal period"
        elif self.relationship.destination.id == CONGENITAL:
            return "is congenital"
        else:
            return f"occurs during some {self.relationship.destination.fully_specified_name_no_type.lower()}"


class FindingSiteRenderer(RoleRenderer):

    def __init__(self, relationship, id_reference=False):
        super().__init__(relationship, id_reference=id_reference)
        self.anatomical_sites = set([self.render_concept(Concept.by_id(i))
                                     for i in relationship.destination.part_of_transitive()])
        self.is_lengthy = len(self.anatomical_sites) > 1

    def render(self, relationships=None):
        return "is located in some {}".format(
            "{}".format(pretty_print_list(list(set(self.anatomical_sites)), and_char=", and "))
            if self.is_lengthy else next(iter(self.anatomical_sites))
        )


def prefix_with_indefinite_article(term, unquoted=True):
    return f"{'an' if term[0].lower() in 'aeiou' else 'a'} " + (term if unquoted else f"'{term}'")


def get_renderer(relationship, relationships, id_reference=False):
    if relationship.type.id == OCCURRENCE:
        return OccursRenderer(relationship, id_reference=id_reference)
    elif relationship.type.id == ASSOCIATED_MORPHOLOGY:
        return AlternativeNameRoleRenderer('characterized in form by', relationship,
                                           id_reference=id_reference)
    elif relationship.type.id == HAS_INTENT:
        return AlternativeNameRoleRenderer('is intended as/for', relationship,
                                           id_reference=id_reference)
    elif relationship.type.id == ASSOCIATED_FINDING:
        return AlternativeNameRoleRenderer('is a finding of', relationship,
                                           id_reference=id_reference)
    # elif relationship.type.id == SUBJECT_RELATIONSHIP_CONTEXT:
    #     return AlternativeNameRoleRenderer('has (as finding subject)', relationship,
    #                                        id_reference=id_reference)
    elif relationship.type.id in [HAS_INTERPRETATION, CLINICAL_COURSE]:
        return RelationshipAsIsaRenderer(relationship, id_reference=id_reference)
    elif relationship.type.id in [PATHOLOGICAL_PROCESS]:
        obj = RelationshipAsIsaRenderer(relationship, id_reference=id_reference)
        obj.with_article = True
        return obj
    elif relationship.type.id in [DUE_TO, CAUSATIVE_AGENT]:
        obj = RoleRenderer(relationship, id_reference=id_reference)
        obj.role_phrase = 'is caused by'
        return obj
    elif relationship.type.id in ROLE_PAIR_RENDERER_MAPPING:
        render_class = ROLE_PAIR_RENDERER_MAPPING[relationship.type.id]
        obj = render_class(relationships, id_reference=id_reference)
        return obj
    elif relationship.type.id == AFTER:
        obj = RoleRenderer(relationship, id_reference=id_reference)
        obj.role_phrase = 'follows'
        return obj
    elif relationship.type.id == FINDING_SITE:
        return FindingSiteRenderer(relationship, id_reference=id_reference)
    else:
        return RoleRenderer(relationship, id_reference=id_reference)


class ControlledEnglishGenerator:
    def __init__(self, concept):
        self.concept = concept

    def get_controlled_english_definition(self, embed_ids=False):
        classification_names_w_article = [
           "{} ({})".format(prefix_with_indefinite_article(c.fully_specified_name_no_type).lower(),
                            c.id)for c in self.concept.isa]
        non_isa_relationships = (self.concept.outbound_relationships()
                                             .filter(active=True)
                                             .unique_links()
                                             .exclude(type_id=ISA))
        has_role_group_definitions = non_isa_relationships.exists()
        non_isa_rels_2_skip = set()
        for target_id, pair_render_cls in ROLE_PAIR_RENDERER_MAPPING.items():
            role_pair_matches = non_isa_relationships.filter(type_id=pair_render_cls.object_id)
            if role_pair_matches.exists():
                non_isa_rels_2_skip.update(role_pair_matches.values_list('id', flat=True))

        renderer_class_count = {}
        brief_role_group_items = []
        lengthy_role_group_items = []
        for rel in non_isa_relationships:
            if rel.id not in non_isa_rels_2_skip:
                renderer = get_renderer(rel, non_isa_relationships, id_reference=embed_ids)
                render_class = type(renderer)
                if render_class.can_collapse_objects and renderer_class_count.get(render_class, 0):
                    continue
                else:
                    renderer_class_count[render_class] = renderer_class_count.get(render_class, 0) + 1
                (lengthy_role_group_items if isinstance(renderer, FindingSiteRenderer) and renderer.is_lengthy
                 else brief_role_group_items).append(renderer.render(relationships=non_isa_relationships,))

        role_group_defn_text = "It {}".format(pretty_print_list(brief_role_group_items,
                                                                and_char=", and ")
                                              ) if brief_role_group_items else ""
        if lengthy_role_group_items:
            role_group_defn_text += "{}It {}".format(".  " if brief_role_group_items else "",
                                                     ".  It ".join(lengthy_role_group_items))

        definition_head = pretty_print_list(classification_names_w_article, and_char=", and ")
        definition_text = "{}.  {}".format(", and ".join([definition_head]),
                                           role_group_defn_text) if has_role_group_definitions else definition_head
        return "{} is {}".format(self.concept.fully_specified_name_no_type, definition_text)


def main():
    concepts = Concept.objects.mapped().has_definition()
    pks = concepts.ids
    concept = Concept.objects.mapped().has_definition().get(pk=choice(pks))
    print(concept)
    for defn in concept.definitions():
        print(defn.term)
    print(ControlledEnglishGenerator(concept).get_controlled_english_definition())


if __name__ == '__main__':
    main()
