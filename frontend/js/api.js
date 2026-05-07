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

/**
 * Récupère toutes les catégories disponibles (hardcodées + personnalisées).
 * @returns {Promise<Object>} CategoriesResponse
 */
async function apiGetCategories() {
  const res = await fetch(`${API_BASE}/categories`);
  if (!res.ok) throw new Error(`Impossible de charger les catégories (${res.status})`);
  return res.json();
}

/**
 * Crée une nouvelle catégorie personnalisée.
 * @param {{ key, label, emoji, couleur }} data
 * @returns {Promise<Object>} CategoryInfo
 */
async function apiCreateCategory(data) {
  const res = await fetch(`${API_BASE}/categories`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || `Erreur création catégorie (${res.status})`);
  return json;
}

/**
 * Upload des fichiers dans une catégorie et les indexe.
 * @param {FileList|File[]} files
 * @param {string} categorie
 * @param {function(number):void} [onProgress]  — appelé avec % avancement upload
 * @returns {Promise<Object>} UploadResponse
 */
/**
 * Relance l'indexation complète de tous les documents présents dans docs/.
 * @returns {Promise<Object>} ReindexResponse
 */
async function apiReindex() {
  const res = await fetch(`${API_BASE}/documents/reindex`, { method: 'POST' });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || `Erreur re-indexation (${res.status})`);
  return json;
}

async function apiUploadFiles(files, categorie, onProgress) {
  const form = new FormData();
  form.append('categorie', categorie);
  for (const file of files) {
    form.append('files', file);
  }

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_BASE}/documents/upload`);

    if (onProgress) {
      xhr.upload.addEventListener('progress', e => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
      });
    }

    xhr.onload = () => {
      const json = (() => { try { return JSON.parse(xhr.responseText); } catch { return {}; } })();
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(json);
      } else {
        reject(new Error(json.detail || `Erreur upload (${xhr.status})`));
      }
    };
    xhr.onerror = () => reject(new Error('Erreur réseau lors de l\'upload'));
    xhr.send(form);
  });
}
