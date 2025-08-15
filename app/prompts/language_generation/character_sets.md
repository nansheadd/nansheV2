Pour la langue spécifiée, liste les jeux de caractères principaux (ex: Hiragana, Katakana pour le japonais; Alphabet Cyrillique pour le russe).
Pour chaque jeu, fournis la liste complète des caractères avec leur prononciation (romaji pour le japonais).

Réponds avec un JSON ayant la structure :
{ "character_sets": [ { "name": "Hiragana", "characters": [ { "symbol": "あ", "pronunciation": "a" } ] } ] }

Si la langue utilise l'alphabet latin, renvoie un tableau vide.