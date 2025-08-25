import logging
from sqlalchemy.orm import Session
from app.models.analytics.training_example_model import TrainingExample

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TRAINING_DATA = [
    # --- PROGRAMMATION ---
    # --- ENRICHISSEMENT : VARIATIONS BRUITÉES + EXEMPLES RÉALISTES ---
    # =========================
    # PROGRAMMATION (réalistes)
    # =========================
    ("OpenClassrooms - Parcours Développeur Python", "programming"),
    ("Udemy cours complet JavaScript 2025", "programming"),
    ("Coursera Machine Learning Andrew Ng en français", "programming"),
    ("MIT OpenCourseWare algorithms introduction", "programming"),
    ("Le Wagon bootcamp fullstack avis", "programming"),
    ("FreeCodeCamp responsive web design", "programming"),
    ("Doc officielle React 18 hooks", "programming"),
    ("Guide NestJS pour backend scalable", "programming"),
    ("Crée une API GraphQL avec Apollo Server", "programming"),
    ("Tests unitaires en Python avec pytest", "programming"),
    ("Clean Code en pratique (SOLID, refactorings)", "programming"),
    ("Microservices avec Spring Boot et Docker", "programming"),
    ("CI/CD GitHub Actions déploiement sur AWS", "programming"),
    ("Kubernetes pour développeurs : pods, services, ingress", "programming"),
    ("Optimiser SQL : index, explain, transactions", "programming"),
    ("Pandas avancé : groupby, pivot, merges", "programming"),
    ("FastAPI + SQLModel tuto complet", "programming"),
    ("Asyncio en Python : coroutines et event loop", "programming"),
    ("Web scraping légal avec Playwright", "programming"),
    ("Détecter les fuites mémoire en Node.js", "programming"),
    ("Sécuriser une appli Django (CSRF, XSS, auth)", "programming"),
    ("Développement mobile Flutter 3 et Dart", "programming"),
    ("React Native + Expo, push notifications", "programming"),
    ("Rust ownership, borrowing, lifetimes", "programming"),
    ("C++ moderne (C++20) coroutines & ranges", "programming"),
    ("TDD de A à Z en Ruby on Rails", "programming"),
    ("Refaire un clone de Trello avec Vue.js 3 + Pinia", "programming"),
    ("Intro à LangChain et RAG en Python", "programming"),
    ("Prompt engineering pour LLMs (guidelines)", "programming"),
    ("TypeScript dans un monorepo Turborepo", "programming"),
    ("Electron : packager une app desktop cross-platform", "programming"),
    ("Next.js 14 App Router + Server Actions", "programming"),
    ("Bun vs Node : benchmarks et compatibilité", "programming"),
    ("SvelteKit : SSR, load, form actions", "programming"),
    ("Tailwind CSS : design system et composants", "programming"),
    ("Graph databases avec Neo4j et Cypher", "programming"),
    ("Elasticsearch : recherche full-text et analyzers", "programming"),
    ("Redis streams et pub/sub en pratique", "programming"),
    ("gRPC vs REST : quand choisir ?", "programming"),
    ("OAuth2/OIDC avec Keycloak", "programming"),
    ("WebSockets temps réel avec Socket.IO", "programming"),
    ("Terraform IaC sur GCP", "programming"),
    ("Ansible pour automatiser les déploiements", "programming"),
    ("Monitoring avec Prometheus + Grafana", "programming"),
    ("Sécurité : OWASP Top 10 2025", "programming"),

    # PROGRAMMATION (fautes / simplifiées / keywords)
    ("cours pyhton gratuit", "programming"),
    ("javascrit debutant", "programming"),
    ("react hook tuto", "programming"),
    ("node js api simple", "programming"),
    ("aprandre a coder vite", "programming"),
    ("programme c++ base", "programming"),
    ("algoritme pour entretien", "programming"),
    ("docker kube debu", "programming"),
    ("git github comment faire", "programming"),
    ("faire un site web rapide", "programming"),
    ("python scraping", "programming"),
    ("app mobile ios swift cours", "programming"),
    ("unity jeux 2d débutant", "programming"),
    ("fast api demarage", "programming"),
    ("typscript guide", "programming"),
    ("haskel fonctionel", "programming"),
    ("kotlin android studio", "programming"),
    ("bash script automate", "programming"),
    ("graph ql pour debutant", "programming"),
    ("electron app bureau tuto", "programming"),
    ("bot discord py", "programming"),
    ("programme rust systeme", "programming"),
    ("design pattern exemples", "programming"),
    ("sql jointures facile", "programming"),
    ("pandas merge erreur", "programming"),
    ("erreur npm fix", "programming"),
    ("erreur pip install", "programming"),
    ("debogage vscode python", "programming"),
    ("regex python simples", "programming"),
    ("webgl demarrer", "programming"),
    ("api rest restful explications", "programming"),
    ("graphql vs rest", "programming"),
    ("hash map c#", "programming"),
    ("php mysql securiser", "programming"),
    ("django auth login", "programming"),
    ("laravel migrations", "programming"),
    ("spring boot securite", "programming"),
    ("go goroutines channels", "programming"),
    ("c pointer memoire", "programming"),
    ("compileur erreur linker", "programming"),
    ("cour programmation pour enfant", "programming"),

    # =========================
    # PHILOSOPHIE (réalistes)
    # =========================
    ("Cours du Collège de France - Foucault audio", "philosophy"),
    ("Khan Academy Philosophie : logique et raisonnement", "philosophy"),
    ("Université ouverte : Histoire de la philo moderne", "philosophy"),
    ("MOOC Coursera philosophie politique", "philosophy"),
    ("Conférence Deleuze sur Spinoza", "philosophy"),
    ("Podcast philosophie morale (utilitarisme vs déontologie)", "philosophy"),
    ("Introduction à la phénoménologie (Husserl, Heidegger)", "philosophy"),
    ("Nietzsche : Généalogie de la morale résumé", "philosophy"),
    ("Kant : impératif catégorique exemples", "philosophy"),
    ("Rousseau Contrat social fiche de lecture", "philosophy"),
    ("Philosophie de l'esprit : qualia et IA", "philosophy"),
    ("Esthétique : jugement de goût chez Kant", "philosophy"),
    ("Épistémologie : falsificationnisme de Popper", "philosophy"),
    ("Philo des sciences : paradigmes chez Kuhn", "philosophy"),
    ("Aristote : éthique à Nicomaque", "philosophy"),

    # PHILOSOPHIE (fautes / simplifiées / keywords)
    ("cours philo debutant", "philosophy"),
    ("philo antique resumé", "philosophy"),
    ("stoicisme pratique", "philosophy"),
    ("bonheur c'est quoi", "philosophy"),
    ("libre arbitre exemples", "philosophy"),
    ("nietzche surhomme explication", "philosophy"),
    ("kantt raison pure", "philosophy"),
    ("spinoza ethique livre 1", "philosophy"),
    ("camus absurde", "philosophy"),
    ("sartre existentialisme", "philosophy"),
    ("foucau pouvoir savoir", "philosophy"),
    ("derrida deconstruction", "philosophy"),
    ("phenomenologie simple", "philosophy"),
    ("logique formelle exercices", "philosophy"),
    ("philo du langage intro", "philosophy"),
    ("conscience definition philo", "philosophy"),
    ("morale et ethique diff", "philosophy"),
    ("lumières philosophes liste", "philosophy"),
    ("machiavel prince resume", "philosophy"),
    ("beauvoir deuxieme sexe idées", "philosophy"),
    ("mythes grecs sens", "philosophy"),
    ("question sens de la vie", "philosophy"),
    ("penser critique exercice", "philosophy"),
    ("philo orientale bouddhisme", "philosophy"),
    ("taoisme wu wei", "philosophy"),

    # =========================
    # LANGUES (réalistes)
    # =========================
    ("Duolingo anglais niveau A1 à B1", "language"),
    ("Babbel espagnol grammaire verbes", "language"),
    ("Italki cours de conversation en japonais", "language"),
    ("Préparer le TOEIC en 4 semaines", "language"),
    ("IELTS Academic writing task 2", "language"),
    ("Anki deck JLPT N3 vocabulaire", "language"),
    ("Podcast allemand facile : Nachrichten leicht", "language"),
    ("YouTube - Français avec Elisa (prononciation)", "language"),
    ("LSF cours en ligne niveau débutant", "language"),
    ("Prononciation anglaise : sons TH /ð/ /θ/", "language"),
    ("Phonétique espagnole : rr vs r", "language"),
    ("Conjugaison italienne : subjonctif présent", "language"),
    ("Mandarin HSK 2 caractères fréquents", "language"),
    ("Vocabulaire néerlandais pour voyageurs", "language"),
    ("Portuguais brésilien : expressions courantes", "language"),
    ("Grammaire russe : cas et déclinaisons", "language"),

    # LANGUES (fautes / simplifiées / keywords)
    ("anglais debutant gratuit", "language"),
    ("apprendre englais vite", "language"),
    ("parler espagnol b1 b2", "language"),
    ("jlpt n3 conseils", "language"),
    ("gramaire allemand cas", "language"),
    ("italien en voyage phrases", "language"),
    ("mandarin pinyin base", "language"),
    ("russe pour debutant", "language"),
    ("toefl preparation", "language"),
    ("anglais business email", "language"),
    ("conversation portugais", "language"),
    ("alphabet hangeul facile", "language"),
    ("lsf niveau 1", "language"),
    ("latin vocabulaire", "language"),
    ("arabe litteraire initiation", "language"),
    ("parler anglais sans accent", "language"),
    ("cours d'allemand pas cher", "language"),
    ("vocabulaire espagnol pdf", "language"),
    ("japonais hiragana katakana", "language"),
    ("grammaire anglaise exercices", "language"),
    ("neerlandais bases", "language"),
    ("apprendre une langue rapidement", "language"),
    ("chine chinois debu", "language"),
    ("suédois cours audio", "language"),
    ("polonais alphabet", "language"),
    ("esperanto facile", "language"),

    # =========================
    # GÉNÉRIQUE (réalistes)
    # =========================
    ("CNED Histoire de l'art - Renaissance", "generic"),
    ("MOOC marketing digital SEO/SEA", "generic"),
    ("Comptabilité pour auto-entrepreneurs", "generic"),
    ("Guitare acoustique accords ouverts", "generic"),
    ("Psychologie cognitive introduction", "generic"),
    ("Gestion de projet Agile Scrum Kanban", "generic"),
    ("Cuisine française sauces mères", "generic"),
    ("Photographie numérique mode manuel", "generic"),
    ("Économie micro vs macro cours", "generic"),
    ("Biologie moléculaire ADN ARN", "generic"),
    ("Histoire de France Révolution française", "generic"),
    ("Investir en bourse ETF pour débutants", "generic"),
    ("Dessin perspective 1 point de fuite", "generic"),
    ("Neurosciences cerveau plasticité", "generic"),
    ("Astronomie observation ciel d'été", "generic"),
    ("Anatomie humaine systèmes", "generic"),
    ("Droit constitutionnel institutions", "generic"),
    ("Empire romain chronologie", "generic"),
    ("Physique quantique vulgarisation", "generic"),
    ("Œnologie dégustation vin", "generic"),
    ("Solfège lecture de notes", "generic"),
    ("Notion prise de notes efficace", "generic"),
    ("Mind mapping pour réviser", "generic"),
    ("Méthodes de mémorisation spaced repetition", "generic"),

    # GÉNÉRIQUE (fautes / simplifiées / keywords)
    ("cours art renaissance", "generic"),
    ("seo referencement simple", "generic"),
    ("compta debu", "generic"),
    ("apprendre guitare accords", "generic"),
    ("psycho cogni intro", "generic"),
    ("agile scrum bases", "generic"),
    ("cuisine francaise recette facile", "generic"),
    ("photo mode manuel iso", "generic"),
    ("eco 101 principes", "generic"),
    ("biologie moleculaire resumé", "generic"),
    ("histoire france dates clés", "generic"),
    ("bourse debutant etf", "generic"),
    ("dessin portrait debutant", "generic"),
    ("neuro pour tous", "generic"),
    ("astronomie etoiles", "generic"),
    ("corps humain comment ca marche", "generic"),
    ("droit consti", "generic"),
    ("empire romain empereurs", "generic"),
    ("quantique simple", "generic"),
    ("oenologie bases", "generic"),
    ("solfege lecture rythm", "generic"),
    ("cours pour debutant", "generic"),
    ("formation facile rapide", "generic"),
    ("je veux des bases", "generic"),
]

def seed_training_data(db: Session) -> None:
    """
    Injecte les données d'entraînement initiales si la table est vide.
    """
    # On ne fait rien si la table contient déjà des données
    if db.query(TrainingExample).first():
        logger.info("La table 'training_examples' contient déjà des données. Seeding ignoré.")
        return

    logger.info("Injection des données d'entraînement initiales dans la table 'training_examples'...")
    
    for text, category in TRAINING_DATA:
        example = TrainingExample(
            input_text=text,
            corrected_category=category,
            predicted_category="seed_data",
            user_id=None
        )
        db.add(example)
    
    db.commit()
    logger.info(f"✅ {len(TRAINING_DATA)} exemples d'entraînement ont été ajoutés.")