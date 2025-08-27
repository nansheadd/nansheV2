# TÂCHE : Générer le Contenu d'une Leçon de Programmation

## Objectif
Ton but est de générer le contenu pédagogique pour le concept de programmation : "{{node_label}}". Le contenu doit être pratique, clair, et centré sur le code.

## Format de Sortie
La sortie doit être un unique objet JSON avec une seule clé : "content".
- La valeur de "content" doit être une chaîne de caractères formatée en Markdown.
- Le contenu doit inclure :
  1. Une explication concise du concept.
  2. Au moins un exemple de code clair et commenté dans le langage "{{language}}".
  3. Une explication du fonctionnement de l'exemple de code.

## Règles
- **SOIS DIRECT** : Va droit au but. Pas de blabla, pas d'historique.
- **LE CODE D'ABORD** : Priorise les exemples de code fonctionnels.
- Utilise Markdown pour le formatage, surtout pour les blocs de code (ex: ```{{language}}\n...```).