"""
Schemas Pydantic : modèles de requêtes et réponses API.

Refonte v2 : `categorie` → `workspace`. Plus aucune catégorie native.
"""

from pydantic import BaseModel, Field

# ============================================================
# REQUÊTES
# ============================================================


class ChatRequest(BaseModel):
    """POST /api/chat"""

    question: str = Field(..., min_length=2, max_length=2000)
    workspace: str | None = Field(
        default=None,
        description="Identifiant de workspace pour limiter la recherche (optionnel).",
    )
    session_id: str | None = Field(default="default")


class ClearMemoryRequest(BaseModel):
    session_id: str = Field(default="default")


# ============================================================
# WORKSPACES
# ============================================================


class WorkspaceInfo(BaseModel):
    key: str
    label: str
    emoji: str
    couleur: str
    nb_docs: int = 0


class WorkspacesResponse(BaseModel):
    workspaces: list[WorkspaceInfo]
    total: int


class CreateWorkspaceRequest(BaseModel):
    key: str = Field(
        ...,
        min_length=2,
        max_length=32,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )
    label: str = Field(..., min_length=1, max_length=80)
    emoji: str = Field(default="📁", max_length=8)
    couleur: str = Field(default="#6B7280", pattern=r"^#[0-9A-Fa-f]{6}$")


class DeleteWorkspaceResponse(BaseModel):
    key: str
    label: str
    docs_deleted: int
    message: str
    background: bool = False


# ============================================================
# DOCUMENTS
# ============================================================


class DocumentInfo(BaseModel):
    nom: str
    workspace: str
    workspace_label: str
    workspace_emoji: str
    summary: str | None = None
    tags: list[str] = []


class DocumentsResponse(BaseModel):
    documents: list[DocumentInfo]
    total: int
    workspaces: list[str]


class UploadedFile(BaseModel):
    nom: str
    chunks: int
    statut: str  # "ok" | "erreur"
    detail: str | None = None


class UploadResponse(BaseModel):
    workspace: str
    fichiers: list[UploadedFile]
    total_chunks: int
    message: str
    background: bool = False


class ReindexResponse(BaseModel):
    total_chunks: int
    total_files: int
    message: str
    background: bool = False


class IndexStatusResponse(BaseModel):
    running: bool
    chunks: int = 0
    files: int = 0
    done_at: float | None = None
    error: str | None = None
    warnings: list[str] = []
    message: str


class DeleteDocumentResponse(BaseModel):
    nom: str
    workspace: str
    message: str
    background: bool = False


class ReindexFileResponse(BaseModel):
    nom: str
    workspace: str
    chunks: int
    total_chunks: int
    total_files: int
    message: str


# ============================================================
# CHAT
# ============================================================


class SourceResponse(BaseModel):
    fichier: str
    page: int | str
    workspace: str
    score: float
    extrait: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]
    question: str
    session_id: str
    nb_sources: int
    from_cache: bool = False


# ============================================================
# HEALTH
# ============================================================


class HealthResponse(BaseModel):
    status: str
    index_disponible: bool
    nb_workspaces: int
    nb_documents: int = 0
    modele_llm: str
    modele_embedding: str
    reranker_actif: bool
    version: str
    r2_enabled: bool = False
    hf_enabled: bool = False
    requetes_utilisees: int = 0
    requetes_limite: int = 0
    requetes_restantes: int | None = None


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    code: int
