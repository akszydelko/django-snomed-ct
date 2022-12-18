django-snomed-ct
====================

Django app for queering SNOMED CT database.

*Simple functionality:*

    > from snomed_ct.models import Concept, ICD10_Mapping, TextDefinition, Description, ISA
    > concepts = Concept.by_full_specified_name(term__iregex='aort.+stenosis')
    > concepts
    <ConceptQuerySet [<Concept: 194733006|Mitral and aortic stenosis (disorder)>, [..]
    > concept = Concept.by_id(194733006)
    > concept
    194733006|Mitral and aortic stenosis (disorder)
    > concept.fully_specified_name_no_type
    'Mitral and aortic stenosis'
    for rel in snomed_concept.outbound_relationships():
        print("\t- {} -> {}".format(rel.type, rel.destination))
    [..]
    > for c in Concept.by_definition(term__iregex='aort.+stenosis'):
    ..  print(c)
    ..  for defn in c.definitions().values_list('term', flat=True):
    ..      print("\t", defn)    
        
