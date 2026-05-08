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


# ============================================================
# UPLOAD DE DOCUMENTS
# ============================================================

class CategoryInfo(BaseModel):
    """Informations complètes sur une catégorie."""
    key:      str
    label:    str
    emoji:    str
    couleur:  str
    nb_docs:  int = 0


class CategoriesResponse(BaseModel):
    """Réponse du endpoint GET /api/categories"""
    categories: List[CategoryInfo]
    total:      int


class CreateCategoryRequest(BaseModel):
    """Corps de la requête POST /api/categories"""
    key: str = Field(
        ...,
        min_length=2,
        max_length=32,
        pattern=r'^[a-z0-9_-]+$',
        description="Identifiant technique (minuscules, chiffres, - ou _)",
        examples=["marketing"]
    )
    label: str = Field(
        ...,
        min_length=2,
        max_length=80,
        description="Nom affiché",
        examples=["Documentation Marketing"]
    )
    emoji: str = Field(
        default="📁",
        max_length=8,
        description="Emoji représentant la catégorie"
    )
    couleur: str = Field(
        default="#6B7280",
        pattern=r'^#[0-9A-Fa-f]{6}$',
        description="Couleur hexadécimale"
    )


class UploadedFile(BaseModel):
    """Résultat du traitement d'un fichier uploadé."""
    nom:    str
    chunks: int
    statut: str   # "ok" | "erreur"
    detail: Optional[str] = None


class UploadResponse(BaseModel):
    """Réponse du endpoint POST /api/documents/upload"""
    categorie:    str
    fichiers:     List[UploadedFile]
    total_chunks: int
    message:      str
    background:   bool = False  # True = indexation différée en arrière-plan


class ReindexResponse(BaseModel):
    """Réponse du endpoint POST /api/documents/reindex"""
    total_chunks: int
    total_files:  int
    message:      str
    background:   bool = False  # True = reconstruction différée en arrière-plan


class IndexStatusResponse(BaseModel):
    """Réponse du endpoint GET /api/index/status"""
    running:  bool
    chunks:   int             = 0
    files:    int             = 0
    done_at:  Optional[float] = None
    error:    Optional[str]   = None
    warnings: List[str]       = []   # fichiers partiellement échoués (succès partiel)
    message:  str


class DeleteDocumentResponse(BaseModel):
    """Réponse du endpoint DELETE /api/documents/{categorie}/{filename}"""
    nom:       str
    categorie: str
    message:   str


class DeleteCategoryResponse(BaseModel):
    """Réponse du endpoint DELETE /api/categories/{key}"""
    key:           str
    label:         str
    docs_deleted:  int
    message:       str


class ReindexFileResponse(BaseModel):
    """Réponse du endpoint POST /api/documents/{categorie}/{filename}/reindex"""
    nom:          str
    categorie:    str
    chunks:       int
    total_chunks: int
    total_files:  int
    message:      str