/**
 * api.js — Client HTTP vers le backend FastAPI (refonte v2)
 * `workspace` remplace `categorie` partout.
 * API_BASE est défini dans config.js.
 */

async function apiChat(question, workspace, sessionId) {
  const body = { question, session_id: sessionId };
  if (workspace) body.workspace = workspace;

  let res;
  try {
    res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error('Impossible de contacter le serveur. Vérifiez votre connexion réseau.');
  }

  if (res.status === 429) {
    const err = await res.json().catch(() => ({}));
    const e = new Error(err.detail || 'Limite journalière de requêtes atteinte.');
    e.code = 'RATE_LIMIT';
    throw e;
  }
  if (res.status === 503) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'L\'index documentaire n\'est pas disponible. Uploadez des documents d\'abord.');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Erreur serveur (${res.status}). Réessayez.`);
  }
  return res.json();
}

async function apiChatStream(question, workspace, sessionId) {
  const body = { question, session_id: sessionId };
  if (workspace) body.workspace = workspace;

  let res;
  try {
    res = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error('Impossible de contacter le serveur. Vérifiez votre connexion réseau.');
  }

  if (res.status === 429) {
    const err = await res.json().catch(() => ({}));
    const e = new Error(err.detail || 'Limite journalière de requêtes atteinte.');
    e.code = 'RATE_LIMIT';
    throw e;
  }
  if (res.status === 503) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'L\'index documentaire n\'est pas disponible. Uploadez des documents d\'abord.');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Erreur serveur (${res.status}). Réessayez.`);
  }
  return res.body.getReader();
}

async function apiDocuments() {
  const res = await fetch(`${API_BASE}/documents`);
  if (res.status === 404) return { documents: [], total: 0, workspaces: [] };
  if (!res.ok) throw new Error(`Impossible de charger les documents (${res.status})`);
  return res.json();
}

async function apiHealth() {
  const res = await fetch(`${API_BASE}/health`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Service indisponible');
  return res.json();
}

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

async function apiGetWorkspaces() {
  const res = await fetch(`${API_BASE}/workspaces`);
  if (!res.ok) throw new Error(`Impossible de charger les workspaces (${res.status})`);
  return res.json();
}

async function apiCreateWorkspace(data) {
  const res = await fetch(`${API_BASE}/workspaces`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || `Erreur création workspace (${res.status})`);
  return json;
}

async function apiDeleteWorkspace(key) {
  const res = await fetch(`${API_BASE}/workspaces/${encodeURIComponent(key)}`, { method: 'DELETE' });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || `Erreur suppression workspace (${res.status})`);
  return json;
}

async function apiReindex() {
  const res = await fetch(`${API_BASE}/documents/reindex`, { method: 'POST' });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || `Erreur re-indexation (${res.status})`);
  return json;
}

async function apiIndexStatus() {
  const res = await fetch(`${API_BASE}/index/status`);
  if (!res.ok) throw new Error(`Impossible de récupérer le statut (${res.status})`);
  return res.json();
}

async function apiDeleteDocument(workspace, filename) {
  const res = await fetch(
    `${API_BASE}/documents/${encodeURIComponent(workspace)}/${encodeURIComponent(filename)}`,
    { method: 'DELETE' }
  );
  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(json.detail || `Erreur suppression (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return json;
}

async function apiReindexFile(workspace, filename) {
  const res = await fetch(
    `${API_BASE}/documents/${encodeURIComponent(workspace)}/${encodeURIComponent(filename)}/reindex`,
    { method: 'POST' }
  );
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || `Erreur ré-indexation (${res.status})`);
  return json;
}

async function apiUploadFiles(files, workspace, onProgress) {
  const form = new FormData();
  form.append('workspace', workspace);
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
      if (xhr.status === 409) reject(new Error(json.detail || 'Une indexation est déjà en cours.'));
      else if (xhr.status === 413) reject(new Error('Fichier(s) trop volumineux.'));
      else if (xhr.status === 422) reject(new Error(json.detail || 'Données invalides.'));
      else if (xhr.status === 503) reject(new Error(json.detail || 'Service temporairement indisponible.'));
      else if (xhr.status >= 500) reject(new Error(json.detail || `Erreur serveur interne (${xhr.status}).`));
      else if (xhr.status >= 200 && xhr.status < 300) resolve(json);
      else reject(new Error(json.detail || `Erreur inattendue (${xhr.status}).`));
    };
    xhr.onerror = () => reject(new Error('Impossible de contacter le serveur.'));
    xhr.ontimeout = () => reject(new Error('Le serveur met trop de temps à répondre.'));
    xhr.timeout = 30000;
    xhr.send(form);
  });
}
