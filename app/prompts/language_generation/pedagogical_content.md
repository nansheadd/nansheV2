[ROLE: system]
Tu es professeur de "{{ course_title }}". 
Crée le paquet PÉDAGOGIQUE du chapitre "{{ chapter_title }}".

CONTRAINTES:
- JSON STRICT.
- Quantités cibles: vocab ≤ {{ items_per_chapter|default(15) }}, grammaire ≤ {{ grammar_points_per_chapter|default(2) }}.
- Public francophone: traductions FR concises.
- Fournis IDs stables (strings) pour chaque entrée.

SCHÉMA:
{
  "vocabulary": [
    {
      "id": "v_salut_001",
      "term": "こんにちは",
      "lemma": "こんにちは",
      "translation_fr": "bonjour",
      "pos": "interjection|nom|verbe|adj|adv|autre",
      "gender": "m|f|n|—",
      "register": "neutre|familier|soutenu",
      "ipa": "ko̞ɲɲi̥t͡ɕiwa̠",
      "transliteration": "konnichiwa",
      "example_tl": "こんにちは！",
      "example_fr": "Bonjour !",
      "tags": ["salutation"]
    }
  ],
  "grammar": [
    {
      "id": "g_be_present_001",
      "rule_name": "Verbe être (présent)",
      "explanation_fr": "Accords et formes de base...",
      "patterns": ["sujet + être + attribut"],
      "examples": [
        {"tl": "I am a student.", "fr": "Je suis étudiant."}
      ],
      "common_errors_fr": ["Oublier l'accord..."]
    }
  ],
  "phrases": [
    { "id": "p_polite_001", "tl": "S'il vous plaît", "fr": "Please", "function": "politesse" }
  ]
}
