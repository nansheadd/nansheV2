import sys
from pathlib import Path

# Assure que les imports de l'application fonctionnent
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.analytics.vector_store_model import VectorStore

def inspect_data():
    """
    Se connecte à la DB et affiche les 100 premières entrées de la vector_store.
    """
    db: Session = SessionLocal()
    try:
        print("--- Inspection des 100 premiers atomes de la Vector Store ---")
        
        # On récupère les 100 premières entrées
        atoms = db.query(VectorStore).limit(100).all()
        
        if not atoms:
            print("La table vector_store est vide.")
            return

        for atom in atoms:
            print("\n-------------------------------------")
            print(f"ID           : {atom.id}")
            print(f"Domain       : {atom.domain}")
            print(f"Area         : {atom.area}")
            print(f"Skill        : {atom.skill}")
            print(f"Content Type : {atom.content_type}")
            print(f"Chunk Text   : {atom.chunk_text[:100]}...") # Aperçu du texte
            print(f"Embedding    : {str(atom.embedding)[:60]}...") # Aperçu du vecteur
        
    finally:
        db.close()

if __name__ == "__main__":
    inspect_data()