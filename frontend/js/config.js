/**
 * config.js — Configuration de l'URL de l'API
 *
 * ▶ LOCAL  : rien à changer, /api est résolu par FastAPI sur localhost
 * ▶ RENDER : renseigne RENDER_URL après le déploiement, puis pousse.
 *            Ex : https://chatbot-rag-xxxx.onrender.com
 */

const RENDER_URL = 'https://chatbot-rag-xodz.onrender.com';   // ← coller ici l'URL Render après déploiement

const API_BASE = (() => {
  const { hostname } = window.location;
  const isLocal = hostname === 'localhost' || hostname === '127.0.0.1';
  if (isLocal) return '/api';
  if (RENDER_URL) return `${RENDER_URL.replace(/\/$/, '')}/api`;
  // Fallback : même origine (utile si le frontend et l'API partagent le même domaine)
  return '/api';
})();
