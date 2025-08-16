[ROLE: system]
Génère des EXERCICES pour le chapitre "{{ chapter_title }}" (type de cours: {{ course_type }}).
Base-toi sur la leçon ci-jointe (texte intégral). 
Couvre compréhension, lexique, grammaire et production guidée.

CONTRAINTES:
- JSON STRICT.
- Varie les types (QCM, complétion, appariement, construction de phrase…).
- Donne réponses, distracteurs, et UNE RAISON (rationale) pour la correction.

SCHÉMA:
{
  "exercises": [
    {
      "id": "ex_qcm_001",
      "title": "Compréhension du dialogue",
      "component_type": "qcm|fill_in_the_blank|drag_drop|sentence_construction|character_recognition|discussion",
      "bloom_level": "remember|understand|apply|analyze|evaluate|create",
      "difficulty": 1,
      "skills": ["listening","reading","vocabulary","grammar","writing","speaking"],
      "content_json": {
        "prompt": "…",
        "choices": ["A","B","C","D"],
        "answer": 1,
        "rationales": ["…","…","…","…"]
      }
    }
  ]
}
