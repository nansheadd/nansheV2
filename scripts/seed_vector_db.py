import chromadb
import json
import os
import logging
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# --- Configuration ---
# Configurez les logs pour voir ce qu'il se passe
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Chemin vers le dossier où la base de données ChromaDB sera stockée
CHROMA_PERSIST_DIRECTORY = "./chroma_db"
# Nom de la "collection" (similaire à une table en SQL)
COLLECTION_NAME = "japanese_course_material"
# Modèle d'embedding. 'paraphrase-multilingual-MiniLM-L12-v2' est un bon modèle polyvalent.
EMBEDDING_MODEL_NAME = SentenceTransformer('all-MiniLM-L6-v2')

# Liste des fichiers de données à traiter
DATA_FILES = [
    "app/data/langues/kana.jsonl",
    "app/data/langues/kanjis.jsonl",
    "app/data/langues/vocabulaire.jsonl"
]

# --- Fonctions de Préparation du Texte ---

def format_kana_for_embedding(item):
    """Crée une phrase descriptive pour un kana."""
    data = item.get('data', {})
    return f"Caractère japonais {data.get('script', '')} : {data.get('character', '')}, prononcé {data.get('romaji', '')}."

def format_kanji_for_embedding(item):
    """Crée une phrase descriptive pour un kanji."""
    data = item.get('data', {})
    return f"Kanji japonais : {data.get('character', '')}. Signification : {data.get('meaning', '')}. Lectures ON : {data.get('onyomi_romaji', '')}, Lectures KUN : {data.get('kunyomi_romaji', '')}."

def format_vocabulary_for_embedding(item):
    """Crée une phrase descriptive pour un mot de vocabulaire."""
    data = item.get('data', {})
    example = data.get('example_sentences', [{}])[0].get('fr', '')
    return f"Mot de vocabulaire japonais : {data.get('word', '')} ({data.get('reading', '')}). Signification : {data.get('meaning', '')}. Exemple : {example}"

# Mapping entre le type de contenu et la fonction de formatage
CONTENT_TYPE_FORMATTERS = {
    "kana": format_kana_for_embedding,
    "kanji": format_kanji_for_embedding,
    "vocabulary": format_vocabulary_for_embedding
}

# --- Script Principal ---

def seed_vector_database():
    """
    Script principal pour lire les fichiers JSONL, créer les embeddings,
    et les stocker dans ChromaDB.
    """
    logging.info("--- Début du script de seeding de la base de données vectorielle ---")

    # 1. Initialiser le client ChromaDB
    # `PersistentClient` sauvegarde la base de données sur le disque
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIRECTORY)
    logging.info(f"Client ChromaDB initialisé. Base de données stockée dans : {CHROMA_PERSIST_DIRECTORY}")

    # 2. Charger le modèle d'embedding
    # Le modèle sera téléchargé automatiquement la première fois
    logging.info(f"Chargement du modèle d'embedding : {EMBEDDING_MODEL_NAME}...")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    logging.info("Modèle chargé avec succès.")

    # 3. Créer ou récupérer la collection
    # `get_or_create_collection` évite les doublons si le script est lancé plusieurs fois
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"} # Utilise la similarité cosinus, bon pour le texte
    )
    logging.info(f"Collection '{COLLECTION_NAME}' chargée/créée.")

    # 4. Traiter chaque fichier de données
    for file_path in DATA_FILES:
        if not os.path.exists(file_path):
            logging.warning(f"Le fichier {file_path} n'a pas été trouvé. Passage au suivant.")
            continue

        logging.info(f"--- Traitement du fichier : {file_path} ---")
        
        documents_to_embed = []
        metadatas = []
        ids = []

        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in tqdm(lines, desc=f"Lecture de {os.path.basename(file_path)}"):
                try:
                    item = json.loads(line)
                    doc_id = item.get('doc_id')
                    content_type = item.get('content_type')

                    if not doc_id or not content_type:
                        logging.warning(f"Ligne ignorée (doc_id ou content_type manquant): {line.strip()}")
                        continue
                    
                    # Sélectionner la bonne fonction de formatage
                    formatter = CONTENT_TYPE_FORMATTERS.get(content_type)
                    if not formatter:
                        logging.warning(f"Aucun formateur trouvé pour le content_type '{content_type}'. Ligne ignorée.")
                        continue
                        
                    # Créer le texte qui sera "embeddé"
                    document_text = formatter(item)
                    documents_to_embed.append(document_text)
                    
                    # Les métadonnées permettent de filtrer les résultats plus tard
                    # On stocke l'objet JSON entier comme métadonnée pour le récupérer facilement
                    metadatas.append(item)
                    ids.append(doc_id)

                except json.JSONDecodeError:
                    logging.error(f"Erreur de décodage JSON pour la ligne : {line.strip()}")

        if not documents_to_embed:
            logging.info(f"Aucun document valide à ajouter depuis {file_path}.")
            continue

        # 5. Créer les embeddings pour les documents du fichier
        logging.info(f"Création des embeddings pour {len(documents_to_embed)} documents...")
        embeddings = embedding_model.encode(documents_to_embed, show_progress_bar=True)
        logging.info("Embeddings créés.")

        # 6. Ajouter les données à la collection ChromaDB par lots (batch)
        # C'est beaucoup plus efficace que d'ajouter un par un
        logging.info(f"Ajout de {len(ids)} documents à la collection '{COLLECTION_NAME}'...")
        # `upsert` met à jour les documents s'ils existent déjà, sinon les crée
        collection.upsert(
            embeddings=embeddings.tolist(), # L'API attend une liste Python
            documents=documents_to_embed,
            metadatas=metadatas,
            ids=ids
        )
        logging.info(f"Documents du fichier {file_path} ajoutés avec succès.")

    logging.info("--- Script de seeding terminé avec succès ! ---")
    item_count = collection.count()
    logging.info(f"La collection '{COLLECTION_NAME}' contient maintenant {item_count} documents.")


if __name__ == "__main__":
    # Assurez-vous que le script est lancé depuis la racine du dossier 'backend'
    # pour que les chemins relatifs fonctionnent.
    seed_vector_database()
