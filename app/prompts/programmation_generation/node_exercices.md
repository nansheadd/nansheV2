# TÂCHE : Générer un Exercice de Code

## Objectif
Ton but est de créer un unique exercice de code pratique pour le concept "{{node_label}}". L'exercice doit tester la compréhension de l'utilisateur sur ce concept spécifique.

## Format de Sortie
La sortie doit être un unique objet JSON représentant l'exercice. Cet objet doit contenir ces clés :
- `title`: Un titre pour l'exercice (ex: "Exercice : Déclarer une variable").
- `component_type`: Doit être la chaîne de caractères "CODING_EXERCISE".
- `content_json`: Un objet contenant les clés suivantes :
  - `statement`: L'énoncé du problème, clair et concis.
  - `starter_code`: Le code de départ fourni à l'utilisateur.
  - `validation_tests`: Le code des tests de validation pour vérifier la solution de l'utilisateur (utilise un framework de test commun pour le langage "{{language}}", comme Jest pour JavaScript ou Pytest pour Python).

## Règles
- L'exercice doit être résolvable en utilisant principalement le concept de "{{node_label}}".
- Les `validation_tests` doivent être suffisamment robustes pour évaluer correctement le code de l'utilisateur.