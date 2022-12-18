django-snomed-ct
====================

Django app/model/utilities for queering SNOMED CT database.

*Simple functionality:*
```python
from snomed_ct.models import Concept, ICD10_Mapping, TextDefinition, Description, ISA
concepts = Concept.by_full_specified_name(term__iregex='aort.+stenosis')
```

Fetch concepts by REGEX matching their fully specified names (related via the Description model).  The method also 
takes other model querying arguments for the Description model, passed as query arguments  

```python
concept = Concept.by_id(194733006)
concept
```

A single Concept can be fetched by the Class method by_id

```python
concept.fully_specified_name_no_type
for rel in snomed_concept.outbound_relationships():
..  print("\t- {} -> {}".format(rel.type, rel.destination))
```

Relationships that have a concept as their _destination_ (that make concept definitions relating another concept to 
the one given) can be returned as an iterable of model and the same can be done in the other direction 
(Concept.inbound_relationships())
```python
for c in Concept.by_definition(term__iregex='aort.+stenosis'):
..  print(c)
```

Concepts can be fetched via matching definitions (the TextDefinition model) made about them by the term, as well as 
by query filter argument to the other terms in that model 

```python
..  for defn in c.definitions().values_list('term', flat=True):
..      print("\t", defn)    
```        

All the definitions for a concept object can be returned as an iteratorof TextDefinition model instances
