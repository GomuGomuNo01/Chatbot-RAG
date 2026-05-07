/**
 * app.js — Orchestrateur principal de l'application
 */

class App {
  constructor() {
    this.ui               = new ChatUI();
    this.sessionId        = this._generateSessionId();
    this.selectedCategory = null;
    this.isLoading        = false;
    this.documents        = [];
    this._healthData      = null;
  }

  async init() {
    // Appliquer la langue sauvegardée avant tout rendu
    i18n.applyTranslations();
    this._bindEvents();
    await Promise.all([
      this._checkHealth(),
      this._loadDocuments(),
    ]);
  }

  // ─── Langue ───────────────────────────────────────────────────────────────

  /** Appelé par le sélecteur de langue après i18n.setLang(). */
  _onLangChange() {
    // Re-appliquer les chaînes dynamiques
    this._renderDocumentList();
    this._updateCategoryBadge();
    if (this._healthData !== null) this._renderHealthBadge(this._healthData);
    this._updateWelcomeDesc();
  }

  _updateWelcomeDesc() {
    const el = document.getElementById('welcomeDesc');
    if (!el) return;
    const raw = i18n.t('welcome.desc');
    el.innerHTML = raw
      .replace(/{b1}(.+?){\/b1}/g, '<strong>$1</strong>')
      .replace(/{b2}(.+?){\/b2}/g, '<strong>$1</strong>')
      .replace(/{b3}(.+?){\/b3}/g, '<strong>$1</strong>');
  }

  // ─── Événements ───────────────────────────────────────────────────────────

  _bindEvents() {
    document.getElementById('inputForm').addEventListener('submit', e => {
      e.preventDefault();
      this._handleSubmit();
    });

    const inputField  = document.getElementById('inputField');
    const sendBtn     = document.getElementById('sendBtn');
    const charCounter = document.getElementById('charCounter');

    inputField.addEventListener('input', () => {
      const len = inputField.value.trim().length;
      sendBtn.disabled = len === 0 || this.isLoading;
      charCounter.textContent = `${inputField.value.length}/1000`;
    });

    inputField.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!sendBtn.disabled) this._handleSubmit();
      }
    });

    inputField.addEventListener('input', () => {
      inputField.style.height = 'auto';
      inputField.style.height = Math.min(inputField.scrollHeight, 160) + 'px';
    });

    document.querySelectorAll('input[name="category"]').forEach(radio => {
      radio.addEventListener('change', e => {
        this.selectedCategory = e.target.value || null;
        this._updateCategoryBadge();
        this._highlightActiveCategory(e.target.closest('label'));
      });
    });

    document.getElementById('newChatBtn').addEventListener('click', () => {
      this._startNewChat();
    });

    const menuBtn        = document.getElementById('menuBtn');
    const sidebar        = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    menuBtn.addEventListener('click', () => {
      sidebar.classList.toggle('sidebar--open');
      sidebarOverlay.classList.toggle('sidebar-overlay--visible');
    });
    sidebarOverlay.addEventListener('click', () => {
      sidebar.classList.remove('sidebar--open');
      sidebarOverlay.classList.remove('sidebar-overlay--visible');
    });

    document.querySelectorAll('.example-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const field = document.getElementById('inputField');
        field.value = btn.dataset.question;
        field.dispatchEvent(new Event('input'));
        field.focus();
      });
    });

    this._updateWelcomeDesc();
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
        buffer = lines.pop();

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
    try {
      const data = await apiHealth();
      this._healthData = data;
      this._renderHealthBadge(data);
    } catch {
      this._healthData = null;
      const badge    = document.getElementById('statusBadge');
      const statusEl = document.getElementById('statusText');
      badge.className      = 'status-badge status-badge--error';
      statusEl.textContent = i18n.t('status.offline');
      this._showNotice(i18n.t('notice.offline'));
    }
  }

  _renderHealthBadge(data) {
    const badge    = document.getElementById('statusBadge');
    const statusEl = document.getElementById('statusText');
    const isOk     = data.status === 'ok' && data.index_disponible;

    badge.className      = `status-badge status-badge--${isOk ? 'ok' : 'warn'}`;
    statusEl.textContent = isOk
      ? `${i18n.lang === 'en' ? 'Ready' : 'Prêt'} · ${data.nb_categories} ${i18n.lang === 'en' ? 'categorie(s)' : 'catégorie(s)'}`
      : i18n.t('status.noindex');

    if (!data.index_disponible) {
      this._showNotice(i18n.t('notice.noindex'));
    }
  }

  // ─── Chargement des documents ─────────────────────────────────────────────

  async _loadDocuments() {
    try {
      const data     = await apiDocuments();
      this.documents = data.documents || [];
      this._renderDocumentList();
      this._updateCategoryCounters();
    } catch {
      document.getElementById('documentList').innerHTML =
        `<p class="doc-list__empty">${i18n.t('docs.none')}</p>`;
    }
  }

  _renderDocumentList() {
    const list = document.getElementById('documentList');
    if (!this.documents.length) {
      list.innerHTML = `<p class="doc-list__empty">${i18n.t('docs.empty').replace('\n', '<br>')}<br><code>python ingest.py</code>.</p>`;
      return;
    }
    const byCategory = this.documents.reduce((acc, doc) => {
      (acc[doc.categorie] = acc[doc.categorie] || []).push(doc);
      return acc;
    }, {});
    list.innerHTML = Object.entries(byCategory).map(([cat, docs]) => `
      <div class="doc-group">
        <div class="doc-group__label">${docs[0].emoji} ${i18n.t('cat.' + cat) || docs[0].label}</div>
        ${docs.map(d => `
          <div class="doc-item" title="${this._esc(d.nom)}">
            <span class="doc-item__icon">📄</span>
            <span class="doc-item__name">${this._esc(d.nom.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' '))}</span>
          </div>`).join('')}
      </div>`).join('');
  }

  _updateCategoryCounters() {
    const counts = { all: this.documents.length };
    this.documents.forEach(d => { counts[d.categorie] = (counts[d.categorie] || 0) + 1; });
    Object.entries(counts).forEach(([key, n]) => {
      const el = document.getElementById(`count-${key}`);
      if (el) el.textContent = n;
    });
  }

  // ─── Catégorie active ─────────────────────────────────────────────────────

  _updateCategoryBadge() {
    const badge   = document.getElementById('categoryBadge');
    const badgeEl = document.getElementById('categoryBadgeText');
    if (!this.selectedCategory) { badge.hidden = true; return; }
    badgeEl.textContent = i18n.t(`badge.${this.selectedCategory}`);
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
    document.getElementById('sendBtn').disabled  = val;
    document.getElementById('inputField').disabled = val;
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

  _esc(str) {
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
}

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
