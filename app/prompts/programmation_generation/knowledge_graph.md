# TÂCHE : Générer un Graphe de Connaissances pour un Cours de Programmation

## Objectif
Ton but est de créer un graphe de connaissances structuré pour un cours sur le sujet de "{{topic}}". Le graphe doit être logique, bien organisé, et représenter les concepts techniques clés et leurs relations.

## Structure de Sortie
La sortie doit être un unique objet JSON contenant deux clés : "nodes" et "edges".

### Clé "nodes" (les nœuds)
- Chaque nœud représente un concept, une technologie, ou un projet pratique.
- Chaque nœud doit avoir :
  - `id`: Un identifiant unique en minuscules (ex: "variables", "fonctions", "api_rest").
  - `label`: Un nom lisible pour l'utilisateur (ex: "Les Variables", "Les Fonctions", "API REST").
  - `type`: La catégorie du nœud. Doit être une de ces valeurs : `Concept`, `Technologie`, `Langage`, `Librairie`, `Projet`.

### Clé "edges" (les arêtes)
- Chaque arête représente une dépendance entre deux nœuds.
- Chaque arête doit avoir :
  - `source`: L'`id` du nœud de départ.
  - `target`: L'`id` du nœud d'arrivée.
  - `label`: La nature de la relation. Doit être une de ces valeurs : `depend_de`, `utilise_dans`, `est_un_exemple_de`.

## Règles
- Concentre-toi sur la connaissance pratique et technique. Évite l'historique et les informations non essentielles.
- Le graphe doit montrer une progression d'apprentissage claire (ex: il faut apprendre "Variables" avant "Fonctions").
- Commence par les concepts fondamentaux et progresse vers des sujets plus avancés et des projets.