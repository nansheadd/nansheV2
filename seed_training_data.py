import logging
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, engine # --- NOUVEAU --- Importez l'engine
from app.db.base import Base # Importe tous vos modèles déclarés
from app.models.analytics.training_example_model import TrainingExample

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- NOUVEAU --- Fonction pour initialiser la base de données
def init_db():
    """
    Crée toutes les tables dans la base de données si elles n'existent pas déjà.
    """
    logger.info("Vérification et création des tables de la base de données si nécessaire...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Les tables de la base de données sont prêtes.")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la création des tables : {e}")
        raise

# ... (La liste TRAINING_DATA reste identique) ...
TRAINING_DATA = [
    # --- PROGRAMMATION ---
    ("Apprendre Python de A à Z", "programming"),
    ("Cours complet sur JavaScript et React", "programming"),
    ("Développement web fullstack avec Node.js", "programming"),
    ("Introduction aux algorithmes", "programming"),
    ("Bases de données SQL pour débutants", "programming"),
    ("Machine Learning avec Scikit-Learn", "programming"),
    ("Programmation orientée objet en Java", "programming"),
    ("Créer une app mobile avec Flutter", "programming"),
    ("Apprendre le langage C++", "programming"),
    ("Tutoriel sur le framwork Django", "programming"),
    ("Comment coder en Ruby", "programming"),
    ("Les bases de PHP", "programming"),
    ("Développement de jeux vidéo avec Unity", "programming"),
    ("cours de pyhton", "programming"), # Faute de frappe
    ("apprendre a dev", "programming"), # Raccourci
    ("initiation au code", "programming"),

    # --- PHILOSOPHIE ---
    ("Introduction à la philosophie antique", "philosophy"),
    ("Comprendre Platon et Aristote", "philosophy"),
    ("L'éthique de Spinoza", "philosophy"),
    ("Le stoïcisme : un art de vivre", "philosophy"),
    ("Cours sur la métaphysique", "philosophy"),
    ("La pensée de Friedrich Nietzsche", "philosophy"),
    ("Existentialisme : Sartre et Camus", "philosophy"),
    ("Philosophie des sciences", "philosophy"),
    ("Logique et raisonnement critique", "philosophy"),
    ("Les grands courants de la philo", "philosophy"), # Raccourci
    ("Étude de la République de Platon", "philosophy"),
    ("Qu'est-ce que la conscience ?", "philosophy"),
    ("Le contrat social de Rousseau", "philosophy"),

    # --- LANGUES ---
    ("Apprendre l'anglais pour débutants (A1)", "language"),
    ("Cours d'espagnol niveau intermédiaire B1", "language"),
    ("Parler japonais couramment", "language"),
    ("Grammaire et conjugaison allemande", "language"),
    ("Apprendre l'italien en 30 jours", "language"),
    ("Initiation au mandarin", "language"),
    ("Russe pour les nuls", "language"),
    ("Préparation au TOEFL", "language"),
    ("Anglais des affaires", "language"),
    ("Cours de conversation en portugais", "language"),
    ("Apprendre le coréen et l'alphabet Hangeul", "language"),
    ("Langue des signes française (LSF)", "language"),

    # --- GÉNÉRIQUE (AUTRES SUJETS) ---
    ("Histoire de l'art de la Renaissance", "generic"),
    ("Marketing digital et réseaux sociaux", "generic"),
    ("Les bases de la comptabilité", "generic"),
    ("Apprendre à jouer de la guitare", "generic"),
    ("Introduction à la psychologie", "generic"),
    ("Gestion de projet avec la méthode Agile", "generic"),
    ("Cours de cuisine française", "generic"),
    ("Photographie pour débutants", "generic"),
    ("Économie 101", "generic"),
    ("Biologie moléculaire", "generic"),
    ("Histoire de France", "generic"),
    ("Comment investir en bourse", "generic"),
    ("Cours de dessin", "generic"),
]


def seed_data():
    """
    Injecte le jeu de données d'entraînement dans la base de données.
    """
    db: Session = SessionLocal()
    logger.info("Démarrage de l'injection des données d'entraînement...")
    
    try:
        existing_texts_query = db.query(TrainingExample.input_text).all()
        existing_texts = {text for (text,) in existing_texts_query}
        added_count = 0

        for text, category in TRAINING_DATA:
            if text not in existing_texts:
                example = TrainingExample(
                    input_text=text,
                    corrected_category=category,
                    predicted_category="seed_data",
                    user_id=None
                )
                db.add(example)
                added_count += 1
                existing_texts.add(text)

        if added_count > 0:
            db.commit()
            logger.info(f"✅ {added_count} nouveaux exemples d'entraînement ont été ajoutés.")
        else:
            logger.info("ℹ️ Aucun nouvel exemple à ajouter, la base de données est déjà à jour.")
    
    except Exception as e:
        logger.error(f"❌ Une erreur est survenue pendant le seeding : {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db() # --- NOUVEAU --- On appelle la fonction d'initialisation en premier
    seed_data()