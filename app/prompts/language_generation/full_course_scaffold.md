[ROLE]
Tu es un concepteur expert de programmes d'études linguistiques. Ta mission est de générer la structure complète d'un cours de langue en un seul JSON.

[OBJECTIF]
Créer un JSON contenant **à la fois** le plan de cours détaillé (niveaux et chapitres) et les alphabets de base pour le cours "{{ course_title }}".

{{ rag_context }}

[STRUCTURE DE SORTIE JSON IMPÉRATIVE]
Tu dois retourner un unique objet JSON avec les clés de haut niveau suivantes : `overview`, `levels`, et `character_sets`.

{
  "overview": "Une brève description du cours, de sa philosophie et de ce que l'étudiant va accomplir.",
  "levels": [
    {
      "level_title": "Niveau 1: Les Fondamentaux",
      "chapters": [
        { "title": "Introduction, Prononciation et Écriture", "is_theoretical": true },
        { "title": "Les Salutations Essentielles", "is_theoretical": false },
        "La Structure de Phrase Simple : X est Y"
      ]
    }
  ],
  "character_sets": [
    {
      "name": "Hiragana",
      "description": "Le syllabaire de base pour les mots natifs et la grammaire."
    },
    {
      "name": "Katakana",
      "description": "Le syllabaire utilisé pour les mots d'emprunt et les onomatopées."
    }
  ]
}

[INSTRUCTIONS]
1.  Le plan doit être logique et progressif, adapté à un débutant.
2.  Inclus au moins un chapitre théorique (`"is_theoretical": true`) au début.
3.  Pour `character_sets`, liste uniquement les alphabets/systèmes d'écriture principaux, sans inclure la liste complète des caractères.