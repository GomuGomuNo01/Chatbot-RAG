/**
 * app.js — Orchestrateur principal de l'application
 * Initialise l'UI, gère les événements et coordonne les appels API.
 */

class App {
  constructor() {
    this.ui              = new ChatUI();
    this.sessionId       = this._generateSessionId();
    this.selectedCategory = null;
    this.isLoading       = false;
    this.documents       = [];
  }

  /** Point d'entrée : appelé à DOMContentLoaded. */
  async init() {
    this._bindEvents();
    await Promise.all([
      this._checkHealth(),
      this._loadDocuments(),
    ]);
  }

  // ─── Événements ───────────────────────────────────────────────────────────

  _bindEvents() {
    // Envoi du formulaire
    document.getElementById('inputForm').addEventListener('submit', e => {
      e.preventDefault();
      this._handleSubmit();
    });

    // Activation du bouton d'envoi selon la saisie
    const inputField = document.getElementById('inputField');
    const sendBtn    = document.getElementById('sendBtn');
    const charCounter = document.getElementById('charCounter');

    inputField.addEventListener('input', () => {
      const len = inputField.value.trim().length;
      sendBtn.disabled = len === 0 || this.isLoading;
      charCounter.textContent = `${inputField.value.length}/1000`;
    });

    // Envoi au Entrée (Shift+Entrée = nouvelle ligne)
    inputField.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!sendBtn.disabled) this._handleSubmit();
      }
    });

    // Auto-resize du textarea
    inputField.addEventListener('input', () => {
      inputField.style.height = 'auto';
      inputField.style.height = Math.min(inputField.scrollHeight, 160) + 'px';
    });

    // Changement de catégorie
    document.querySelectorAll('input[name="category"]').forEach(radio => {
      radio.addEventListener('change', e => {
        this.selectedCategory = e.target.value || null;
        this._updateCategoryBadge();
        this._highlightActiveCategory(e.target.closest('label'));
      });
    });

    // Nouvelle conversation
    document.getElementById('newChatBtn').addEventListener('click', () => {
      this._startNewChat();
    });

    // Menu mobile
    const menuBtn       = document.getElementById('menuBtn');
    const sidebar       = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    menuBtn.addEventListener('click', () => {
      sidebar.classList.toggle('sidebar--open');
      sidebarOverlay.classList.toggle('sidebar-overlay--visible');
    });
    sidebarOverlay.addEventListener('click', () => {
      sidebar.classList.remove('sidebar--open');
      sidebarOverlay.classList.remove('sidebar-overlay--visible');
    });

    // Questions d'exemple
    document.querySelectorAll('.example-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const field = document.getElementById('inputField');
        field.value = btn.dataset.question;
        field.dispatchEvent(new Event('input'));
        field.focus();
      });
    });
  }

  // ─── Envoi d'un message ───────────────────────────────────────────────────

  async _handleSubmit() {
    const inputField = document.getElementById('inputField');
    const question   = inputField.value.trim();
    if (!question || this.isLoading) return;

    this.ui.addUserMessage(question);
    inputField.value = '';
    inputField.style.height = 'auto';
    document.getElementById('charCounter').textContent = '0/1000';
    document.getElementById('sendBtn').disabled = true;

    this._setLoading(true);
    this.ui.showTyping();

    try {
      const reader  = await apiChatStream(question, this.selectedCategory, this.sessionId);
      const decoder = new TextDecoder();
      let   buffer  = '';
      let   botEl   = null;

      this.ui.hideTyping();
      botEl = this.ui.startStreamingMessage();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // conserver la ligne incomplète

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          let event;
          try { event = JSON.parse(line.slice(6)); } catch { continue; }

          if (event.error) {
            this.ui.appendToken(botEl, `\n\n⚠️ ${event.error}`);
          } else if (event.token !== undefined) {
            this.ui.appendToken(botEl, event.token);
          }
          if (event.done) {
            this.ui.finalizeMessage(botEl, event.sources || []);
          }
        }
      }
    } catch (err) {
      this.ui.hideTyping();
      // Fallback non-streaming si le streaming échoue
      try {
        const data = await apiChat(question, this.selectedCategory, this.sessionId);
        this.ui.addAssistantMessage(data.answer, data.sources || []);
      } catch (err2) {
        this.ui.addAssistantMessage(`⚠️ ${err2.message}`, []);
      }
    } finally {
      this._setLoading(false);
    }
  }

  // ─── Santé de l'API ───────────────────────────────────────────────────────

  async _checkHealth() {
    const badge    = document.getElementById('statusBadge');
    const statusEl = document.getElementById('statusText');

    try {
      const data = await apiHealth();
      const isOk = data.status === 'ok' && data.index_disponible;

      badge.className   = `status-badge status-badge--${isOk ? 'ok' : 'warn'}`;
      statusEl.textContent = isOk
        ? `Prêt · ${data.nb_categories} catégorie(s)`
        : 'Index manquant';

      if (!data.index_disponible) {
        this._showNotice('⚠️ Index FAISS non trouvé. Lance <code>python ingest.py</code> pour indexer les documents.');
      }
    } catch {
      badge.className      = 'status-badge status-badge--error';
      statusEl.textContent = 'Hors ligne';
      this._showNotice('❌ Impossible de joindre le serveur. Vérifiez qu\'uvicorn est démarré.');
    }
  }

  // ─── Chargement des documents ─────────────────────────────────────────────

  async _loadDocuments() {
    try {
      const data = await apiDocuments();
      this.documents = data.documents || [];
      this._renderDocumentList();
      this._updateCategoryCounters();
    } catch {
      document.getElementById('documentList').innerHTML =
        '<p class="doc-list__empty">Aucun document chargé.</p>';
    }
  }

  _renderDocumentList() {
    const list = document.getElementById('documentList');

    if (!this.documents.length) {
      list.innerHTML = '<p class="doc-list__empty">Aucun document indexé.<br>Lance <code>python ingest.py</code>.</p>';
      return;
    }

    const byCategory = this.documents.reduce((acc, doc) => {
      (acc[doc.categorie] = acc[doc.categorie] || []).push(doc);
      return acc;
    }, {});

    list.innerHTML = Object.entries(byCategory).map(([cat, docs]) => `
      <div class="doc-group">
        <div class="doc-group__label">${docs[0].emoji} ${docs[0].label}</div>
        ${docs.map(d => `
          <div class="doc-item" title="${this._escHtml(d.nom)}">
            <span class="doc-item__icon">📄</span>
            <span class="doc-item__name">${this._escHtml(d.nom.replace(/\.[^.]+$/, '').replace(/_/g, ' '))}</span>
          </div>`).join('')}
      </div>`).join('');
  }

  _updateCategoryCounters() {
    const counts = { all: this.documents.length };
    this.documents.forEach(d => {
      counts[d.categorie] = (counts[d.categorie] || 0) + 1;
    });

    Object.entries(counts).forEach(([key, n]) => {
      const el = document.getElementById(`count-${key}`);
      if (el) el.textContent = n;
    });
  }

  // ─── Catégorie active ─────────────────────────────────────────────────────

  _updateCategoryBadge() {
    const badge   = document.getElementById('categoryBadge');
    const badgeEl = document.getElementById('categoryBadgeText');

    if (!this.selectedCategory) {
      badge.hidden = true;
      return;
    }

    const labels = { technique: '⚙️ Technique', rh: '👥 RH', juridique: '⚖️ Juridique' };
    badgeEl.textContent = labels[this.selectedCategory] || this.selectedCategory;
    badge.hidden = false;
  }

  _highlightActiveCategory(activeLabel) {
    document.querySelectorAll('.category-item').forEach(el => el.classList.remove('category-item--active'));
    if (activeLabel) activeLabel.classList.add('category-item--active');
  }

  // ─── Nouvelle conversation ────────────────────────────────────────────────

  async _startNewChat() {
    if (this.ui.hasMessages()) {
      try { await apiClearSession(this.sessionId); } catch { /* silencieux */ }
    }
    this.sessionId = this._generateSessionId();
    this.ui.clear();
  }

  // ─── Utilitaires ─────────────────────────────────────────────────────────

  _setLoading(val) {
    this.isLoading = val;
    const sendBtn  = document.getElementById('sendBtn');
    const field    = document.getElementById('inputField');
    sendBtn.disabled = val;
    field.disabled   = val;
  }

  _showNotice(html) {
    let notice = document.getElementById('appNotice');
    if (!notice) {
      notice = document.createElement('div');
      notice.id        = 'appNotice';
      notice.className = 'app-notice';
      document.querySelector('.chat-container').prepend(notice);
    }
    notice.innerHTML = html;
    notice.hidden = false;
  }

  _generateSessionId() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = (Math.random() * 16) | 0;
      return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
    });
  }

  _escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
}

// Exposition globale pour le bouton "Effacer filtre"
function clearCategory() {
  document.querySelector('input[name="category"][value=""]').checked = true;
  window._app.selectedCategory = null;
  window._app._updateCategoryBadge();
  document.querySelectorAll('.category-item').forEach(el => el.classList.remove('category-item--active'));
  document.querySelector('.category-item').classList.add('category-item--active');
}

document.addEventListener('DOMContentLoaded', () => {
  window._app = new App();
  window._app.init();
});
