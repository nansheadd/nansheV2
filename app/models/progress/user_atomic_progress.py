from sqlalchemy import Integer, String, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base

class UserCharacterProgress(Base):
    """
    Suit la progression d'un utilisateur sur un caractère spécifique (kana, kanji, etc.).
    """
    __tablename__ = 'user_character_progress'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    
    # L'ID de l'atome dans la table vector_store
    character_atom_id: Mapped[int] = mapped_column(Integer, index=True) 

    # Force de la connaissance (0.0 à 1.0)
    strength: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Direction: 'read' (kana -> romaji) ou 'write' (romaji -> kana)
    direction: Mapped[str] = mapped_column(String(10))

    __table_args__ = (UniqueConstraint('user_id', 'character_atom_id', 'direction', name='_user_char_direction_uc'),)


class UserVocabularyProgress(Base):
    """
    Suit la progression d'un utilisateur sur un mot de vocabulaire spécifique.
    """
    __tablename__ = 'user_vocabulary_progress'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)

    # L'ID de l'atome dans la table vector_store
    vocabulary_atom_id: Mapped[int] = mapped_column(Integer, index=True)

    # Barre de mémorisation (0.0 à 1.0)
    memorization_strength: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Direction: 'jp_to_fr' ou 'fr_to_jp'
    direction: Mapped[str] = mapped_column(String(10))

    __table_args__ = (UniqueConstraint('user_id', 'vocabulary_atom_id', 'direction', name='_user_vocab_direction_uc'),)


class UserAtomProgress(Base):
    __tablename__ = 'user_atom_progress'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    atom_id: Mapped[int] = mapped_column(ForeignKey('atoms.id'), index=True)
    
    # Statut de complétion
    status: Mapped[str] = mapped_column(String(20), default='not_started') # not_started, in_progress, completed
    
    # Score ou force (de 0.0 à 1.0)
    strength: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (UniqueConstraint('user_id', 'atom_id', name='_user_atom_uc'),)