django-snomed-ct
====================

Django app/model/utilities for quering SNOMED CT database.

*Simple functionality:*
```python
from snomed_ct.models import Concept, ICD10_Mapping, TextDefinition, Description, ISA
```

Via the Django model, you can fetch concepts by REGEX matching their fully specified names (related via the **Description** model).  The method also 
takes other model querying arguments (**active**, **language_code**, **type** (a **Concept**) - fully specified name or synonym, etc) for the Description model, passed as query arguments  

```python
concepts = Concept.by_full_specified_name(term__iregex='aort.+stenosis')
```

A single Concept can be fetched by the Class method **by_id** and you can get direct access to the fully specified name 
(**get_fully_specified_name** method and **fully_specified_name** property) and the name without the parenthesized type suffix (**fully_specified_name_no_type** property) 

```python
concept = Concept.by_id(194733006)
concept.fully_specified_name_no_type
concept.fully_specified_name
```
Relationships about a given concept (concept definitions relating another concept to 
the one given) can be returned as an iterable of the Relationship model and the same can be done in the other direction 
via the **inbound_relationships()** method on Concept model instances.

```python

for rel in snomed_concept.outbound_relationships():
..  print("\t- {} -> {}".format(rel.type, rel.destination))
```

Concepts can be fetched via matching definitions (the **TextDefinition** model) made about them by the term, as well as 
by query filter argument to the other terms in that model 

```python
for c in Concept.by_definition(term__iregex='aort.+stenosis'):
..  print(c)
```

All the definitions for a concept object can be returned as an iterator of TextDefinition model instances

```python
..  for defn in c.definitions().values_list('term', flat=True):
..      print("\t", defn)    
```        
