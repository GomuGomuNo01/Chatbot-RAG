/**
 * api.js — Client HTTP vers le backend FastAPI
 * API_BASE est défini dans config.js (chargé avant ce fichier).
 * Toutes les fonctions retournent des Promises et propagent les erreurs.
 */

/**
 * Envoie une question au pipeline RAG.
 * @param {string} question
 * @param {string|null} categorie  — "technique" | "rh" | "juridique" | null
 * @param {string} sessionId
 * @returns {Promise<Object>} ChatResponse
 */
async function apiChat(question, categorie, sessionId) {
  const body = { question, session_id: sessionId };
  if (categorie) body.categorie = categorie;

  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Erreur serveur (${res.status})`);
  }
  return res.json();
}

/**
 * Récupère la liste des documents indexés par catégorie.
 * Retourne un objet vide si aucun document n'est indexé (404).
 * @returns {Promise<Object>} DocumentsResponse
 */
async function apiDocuments() {
  const res = await fetch(`${API_BASE}/documents`);
  if (res.status === 404) return { documents: [], total: 0, categories: [] };
  if (!res.ok) throw new Error(`Impossible de charger les documents (${res.status})`);
  return res.json();
}

/**
 * Vérifie l'état de santé de l'API.
 * @returns {Promise<Object>} HealthResponse
 */
async function apiHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Service indisponible');
  return res.json();
}

/**
 * Démarre une requête chat en streaming (SSE via fetch).
 * @param {string} question
 * @param {string|null} categorie
 * @param {string} sessionId
 * @returns {Promise<ReadableStreamDefaultReader>}
 */
async function apiChatStream(question, categorie, sessionId) {
  const body = { question, session_id: sessionId };
  if (categorie) body.categorie = categorie;

  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Erreur serveur (${res.status})`);
  }
  return res.body.getReader();
}

/**
 * Efface l'historique conversationnel d'une session côté serveur.
 * @param {string} sessionId
 * @returns {Promise<Object>}
 */
async function apiClearSession(sessionId) {
  const res = await fetch(`${API_BASE}/chat/clear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Erreur lors de la réinitialisation');
  }
  return res.json();
}
