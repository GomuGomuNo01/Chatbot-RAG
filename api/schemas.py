"""
Schemas : modèles Pydantic pour les requêtes et réponses API
"""

from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================================
# REQUÊTES
# ============================================================

class ChatRequest(BaseModel):
    """Corps de la requête POST /api/chat"""
    question: str = Field(
        ...,
        min_length=2,
        max_length=1000,
        description="Question posée par l'utilisateur",
        examples=["Qu'est-ce que Spring Boot ?"]
    )
    categorie: Optional[str] = Field(
        default=None,
        description="Filtre de catégorie : technique, rh, juridique",
        examples=["technique"]
    )
    session_id: Optional[str] = Field(
        default="default",
        description="Identifiant de session pour la mémoire conversationnelle"
    )


class ClearMemoryRequest(BaseModel):
    """Corps de la requête POST /api/chat/clear"""
    session_id: str = Field(
        default="default",
        description="Session à effacer"
    )


# ============================================================
# RÉPONSES
# ============================================================

class SourceResponse(BaseModel):
    """Une source citée dans la réponse."""
    fichier:   str
    page:      int | str
    categorie: str
    score:     float
    extrait:   str


class ChatResponse(BaseModel):
    """Réponse du endpoint POST /api/chat"""
    answer:     str
    sources:    List[SourceResponse]
    question:   str
    session_id: str
    nb_sources: int


class DocumentInfo(BaseModel):
    """Informations sur un document indexé."""
    nom:       str
    categorie: str
    label:     str
    emoji:     str


class DocumentsResponse(BaseModel):
    """Réponse du endpoint GET /api/documents"""
    documents:      List[DocumentInfo]
    total:          int
    categories:     List[str]


class HealthResponse(BaseModel):
    """Réponse du endpoint GET /api/health"""
    status:          str
    index_disponible: bool
    nb_categories:   int
    modele_llm:      str
    modele_embedding: str
    version:         str


class ErrorResponse(BaseModel):
    """Format d'erreur uniforme."""
    error:   str
    detail:  Optional[str] = None
    code:    int