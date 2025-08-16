[ROLE: system]
Génère un mini-formulaire pour personnaliser un cours sur "{{ title }}".

CONTRAINTES:
- JSON STRICT.
- Types de champs: text, select, multiselect, integer, boolean, slider.
- Chaque select a des {value,label}.

SCHÉMA:
{
  "fields": [
    {"name":"level","label":"Ton niveau actuel ?","type":"select","options":[
      {"value":"a1","label":"A1 Débutant"}, {"value":"a2","label":"A2 Élémentaire"}, {"value":"b1","label":"B1 Intermédiaire"}
    ]},
    {"name":"goals","label":"Que veux-tu accomplir ?","type":"multiselect","options":[
      {"value":"travel","label":"Voyage"}, {"value":"work","label":"Travail"}, {"value":"exam","label":"Examen (DELE/DELF…)"}
    ]},
    {"name":"time_per_day","label":"Minutes par jour","type":"slider","min":5,"max":60,"step":5,"default":15},
    {"name":"include_transliteration","label":"Afficher la translittération ?","type":"boolean","default":true}
  ]
}
