# Fichier: backend/train_classifier.py (VERSION FINALE ROBUSTE)
import sys
import pickle
from pathlib import Path
import logging

# --- CONFIGURATION DU CHEMIN D'ACCÈS ---
# Cette partie est cruciale. Elle ajoute le dossier 'backend' au chemin de recherche de Python,
# ce qui permet au script de trouver les modules comme 'app.db.session'.
current_dir = Path(__file__).parent.resolve()
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))
# -----------------------------------------

# --- CONFIGURATION DU LOGGING ---
# On configure le logging pour voir ce qu'il se passe en détail.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- IMPORTS (placés après la configuration du chemin) ---
try:
    from sqlalchemy.orm import Session
    from sentence_transformers import SentenceTransformer
    from sklearn.linear_model import SGDClassifier
    from sklearn.preprocessing import LabelEncoder
    from app.db.session import SessionLocal
    from app.models.analytics.training_example_model import TrainingExample
except ImportError as e:
    logger.error(f"❌ Erreur d'importation. Assurez-vous d'avoir installé toutes les dépendances de requirements.txt.")
    logger.error(f"Détail de l'erreur : {e}")
    sys.exit(1) # Quitte le script si les imports échouent

# --- CONFIGURATION DU MODÈLE ---
MODEL_PATH = current_dir / "app" / "services" / "classifier_model.pkl"
BASE_NLP_MODEL = 'all-MiniLM-L6-v2'

def train_and_save_classifier():
    """
    Charge les données, entraîne un classifieur, et le sauvegarde sur le disque.
    """
    logger.info("🚀 Démarrage de l'entraînement du classifieur...")
    db: Session = SessionLocal()
    
    try:
        # 1. Charger les données d'entraînement
        logger.info("1/5 - Chargement des exemples depuis la base de données...")
        examples = db.query(TrainingExample).all()

        if len(examples) < 10:
            logger.warning(f"⚠️ Pas assez de données ({len(examples)} exemples). Entraînement annulé.")
            return

        texts = [ex.input_text for ex in examples]
        labels = [ex.corrected_category for ex in examples]
        logger.info(f"📚 {len(texts)} exemples chargés avec succès.")

        # 2. Créer les embeddings (vecteurs) pour les textes
        logger.info(f"2/5 - Chargement du modèle NLP de base '{BASE_NLP_MODEL}'...")
        embedding_model = SentenceTransformer(BASE_NLP_MODEL)
        logger.info("3/5 - Création des embeddings pour les textes (cela peut prendre un moment)...")
        text_embeddings = embedding_model.encode(texts, show_progress_bar=True)

        # 3. Préparer et entraîner le modèle
        logger.info("4/5 - Entraînement du classifieur...")
        encoder = LabelEncoder()
        classifier = SGDClassifier(loss='log_loss', random_state=42, max_iter=2000, tol=1e-4, n_jobs=-1)
        
        encoded_labels = encoder.fit_transform(labels)
        classifier.fit(text_embeddings, encoded_labels)
        
        # 4. Sauvegarder le pipeline complet (encoder + classifier)
        logger.info(f"5/5 - Sauvegarde du modèle entraîné dans '{MODEL_PATH}'...")
        pipeline = {
            'encoder': encoder,
            'classifier': classifier
        }
        # S'assurer que le dossier parent existe
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump(pipeline, f)

        logger.info("🎉 --- Entraînement Terminé --- 🎉")
        logger.info(f"✅ Classifieur entraîné et sauvegardé avec succès.")
        logger.info(f"Catégories apprises : {list(encoder.classes_)}")

    except Exception as e:
        logger.error(f"❌ Une erreur est survenue pendant l'entraînement : {e}", exc_info=True)
    finally:
        db.close()
        logger.info("Connexion à la base de données fermée.")

if __name__ == "__main__":
    train_and_save_classifier()