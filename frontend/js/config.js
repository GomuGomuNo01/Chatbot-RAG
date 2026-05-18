/**
 * config.js — Configuration de l'URL de l'API
 *
 * FastAPI sert à la fois le frontend (fichiers statiques) et l'API (/api)
 * sur le même domaine, quelle que soit la plateforme de déploiement :
 *
 *   ▶ LOCAL         : http://localhost:7860  →  /api
 *   ▶ HF Spaces     : https://user-space.hf.space  →  /api
 *   ▶ Render        : https://chatbot-rag-xxxx.onrender.com  →  /api
 *   ▶ Autre         : même origine  →  /api
 *
 * Aucune URL en dur n'est nécessaire — même origine dans tous les cas.
 */

const API_BASE = '/api';
