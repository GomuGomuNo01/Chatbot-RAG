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

    // Upload state
    this._uploadFiles       = [];
    this._uploadCategory    = null;
    this._customCategories  = {};   // key → {label, emoji, couleur}
  }

  async init() {
    i18n.applyTranslations();
    this._bindEvents();
    this._bindUploadModal();
    await Promise.all([
      this._checkHealth(),
      this._loadDocuments(),
      this._loadCategories(),
    ]);
  }

  // ─── Langue ───────────────────────────────────────────────────────────────

  _onLangChange() {
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

  // ─── Événements principaux ────────────────────────────────────────────────

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
      ? `${i18n.lang === 'en' ? 'Ready' : 'Prêt'} · ${data.nb_categories} ${i18n.lang === 'en' ? 'cat.' : 'cat.'}`
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
          <div class="doc-item" title="${this._esc(d.nom)}" data-cat="${this._esc(d.categorie)}" data-file="${this._esc(d.nom)}">
            <span class="doc-item__icon">${this._fileIcon(d.nom)}</span>
            <span class="doc-item__name">${this._esc(d.nom.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' '))}</span>
            <span class="doc-item__actions">
              <button class="doc-item__btn doc-item__btn--reindex" title="Ré-indexer ce document" aria-label="Ré-indexer ${this._esc(d.nom)}">🔄</button>
              <button class="doc-item__btn doc-item__btn--delete" title="Supprimer ce document" aria-label="Supprimer ${this._esc(d.nom)}">🗑️</button>
            </span>
          </div>`).join('')}
      </div>`).join('');

    // Bind des boutons d'action
    list.querySelectorAll('.doc-item__btn--delete').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const item = btn.closest('.doc-item');
        this._deleteDocument(item.dataset.cat, item.dataset.file);
      });
    });
    list.querySelectorAll('.doc-item__btn--reindex').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const item = btn.closest('.doc-item');
        this._reindexDocument(item.dataset.cat, item.dataset.file, btn);
      });
    });
  }

  _updateCategoryCounters() {
    const counts = { all: this.documents.length };
    this.documents.forEach(d => { counts[d.categorie] = (counts[d.categorie] || 0) + 1; });
    Object.entries(counts).forEach(([key, n]) => {
      const el = document.getElementById(`count-${key}`);
      if (el) el.textContent = n;
    });
  }

  // ─── Catégories ───────────────────────────────────────────────────────────

  async _loadCategories() {
    try {
      const data = await apiGetCategories();
      this._allCategories = data.categories || [];
      // Stocker les catégories custom (non natives)
      const native = new Set(['technique', 'rh', 'juridique']);
      this._allCategories.forEach(c => {
        if (!native.has(c.key)) this._customCategories[c.key] = c;
      });
      this._renderDynamicCategoryItems();
    } catch {
      // Silencieux — les catégories par défaut sont dans le HTML
    }
  }

  /** Injecte dans la sidebar les catégories personnalisées non présentes en dur. */
  _renderDynamicCategoryItems() {
    const native = new Set(['technique', 'rh', 'juridique']);
    const list   = document.getElementById('categoryList');
    if (!list) return;

    // Supprimer les éléments custom déjà injectés (pour éviter doublons)
    list.querySelectorAll('.category-item--custom').forEach(el => el.remove());

    Object.values(this._customCategories).forEach(cat => {
      if (native.has(cat.key)) return;
      const label = document.createElement('label');
      label.className = 'category-item category-item--custom';
      label.innerHTML = `
        <input type="radio" name="category" value="${this._esc(cat.key)}">
        <span class="category-dot" style="background:${this._esc(cat.couleur)}" aria-hidden="true"></span>
        <span>${this._esc(cat.emoji)} ${this._esc(cat.label)}</span>
        <span class="category-count" id="count-${this._esc(cat.key)}">0</span>
        <button class="cat-delete-btn" title="Supprimer cette catégorie" aria-label="Supprimer ${this._esc(cat.label)}">🗑️</button>`;
      label.querySelector('input').addEventListener('change', e => {
        this.selectedCategory = e.target.value || null;
        this._updateCategoryBadge();
        this._highlightActiveCategory(label);
      });
      label.querySelector('.cat-delete-btn').addEventListener('click', e => {
        e.preventDefault();
        e.stopPropagation();
        this._deleteCategory(cat.key, cat.label);
      });
      list.appendChild(label);
    });
  }

  _updateCategoryBadge() {
    const badge   = document.getElementById('categoryBadge');
    const badgeEl = document.getElementById('categoryBadgeText');
    if (!this.selectedCategory) { badge.hidden = true; return; }

    // Chercher dans i18n d'abord, puis dans les catégories custom
    let label = i18n.t(`badge.${this.selectedCategory}`);
    if (label === `badge.${this.selectedCategory}`) {
      const cat = this._customCategories[this.selectedCategory];
      label = cat ? `${cat.emoji} ${cat.label}` : this.selectedCategory;
    }
    badgeEl.textContent = label;
    badge.hidden = false;
  }

  _highlightActiveCategory(activeLabel) {
    document.querySelectorAll('.category-item').forEach(el => el.classList.remove('category-item--active'));
    if (activeLabel) activeLabel.classList.add('category-item--active');
  }

  // ─── Modale d'upload ──────────────────────────────────────────────────────

  _bindUploadModal() {
    const modal     = document.getElementById('uploadModal');
    const openBtn   = document.getElementById('openUploadBtn');
    const closeBtn  = document.getElementById('modalCloseBtn');
    const cancelBtn = document.getElementById('cancelUploadBtn');
    const submitBtn = document.getElementById('submitUploadBtn');

    // Ouvrir
    openBtn.addEventListener('click', () => this._openUploadModal());

    // Fermer
    [closeBtn, cancelBtn].forEach(btn => btn.addEventListener('click', () => this._closeUploadModal()));
    modal.addEventListener('click', e => { if (e.target === modal) this._closeUploadModal(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && !modal.hidden) this._closeUploadModal(); });

    // Créer catégorie
    document.getElementById('btnNewCat').addEventListener('click', () => this._showPanelNewCat());
    document.getElementById('btnCancelNewCat').addEventListener('click', () => this._showPanelCategory());
    document.getElementById('btnCreateCat').addEventListener('click', () => this._handleCreateCategory());

    // Sélection fichiers
    const dropZone  = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    document.getElementById('browseBtn').addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => this._addFiles(fileInput.files));

    dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drop-zone--over'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drop-zone--over'));
    dropZone.addEventListener('drop', e => {
      e.preventDefault();
      dropZone.classList.remove('drop-zone--over');
      this._addFiles(e.dataTransfer.files);
    });
    dropZone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });

    // Submit upload
    submitBtn.addEventListener('click', () => this._handleUpload());

    // Re-indexation manuelle
    document.getElementById('reindexBtn').addEventListener('click', () => this._handleReindex());
  }

  async _openUploadModal() {
    this._uploadFiles    = [];
    this._uploadCategory = null;
    document.getElementById('fileList').innerHTML      = '';
    document.getElementById('uploadFeedback').hidden   = true;
    document.getElementById('uploadOverlay').hidden    = true;
    document.getElementById('submitUploadBtn').disabled = true;

    this._showPanelCategory();
    await this._renderCategoryRadios();
    document.getElementById('uploadModal').hidden = false;
    document.body.classList.add('modal-open');
  }

  _closeUploadModal() {
    document.getElementById('uploadModal').hidden = true;
    document.body.classList.remove('modal-open');
  }

  _showPanelCategory() {
    document.getElementById('panelCategory').hidden = false;
    document.getElementById('panelNewCat').hidden   = true;
    document.getElementById('panelFiles').hidden    = false;
  }

  _showPanelNewCat() {
    document.getElementById('panelCategory').hidden = true;
    document.getElementById('panelNewCat').hidden   = false;
    document.getElementById('panelFiles').hidden    = true;
    document.getElementById('newCatKey').value      = '';
    document.getElementById('newCatLabel').value    = '';
    document.getElementById('newCatEmoji').value    = '📁';
    document.getElementById('newCatColor').value    = '#6B7280';
    this._renderEmojiPicker();
  }

  // ── Emoji picker ─────────────────────────────────────────────────────────

  _renderEmojiPicker() {
    const EMOJIS = [
      '📁','📂','🗂️','📋','📊','📈','📉','📌','📍','🔖','🏷️',
      '📄','📃','📑','📝','📜','📰','🗒️','🗃️','🗄️',
      '💼','🔑','🔒','🔐','🛡️',
      '⚙️','🛠️','🔧','🔩','💡','🎯','🚀','🔬','🧪','📡',
      '👥','🤝','💬','📞','📧','🎓',
      '📚','📖','🏛️','⚖️','🔍',
      '💻','📱','🖥️','🌐',
      '⭐','🌟','🏆','✅','🟢','🔵','🟡','🟠','🔴',
    ];

    const picker  = document.getElementById('emojiPicker');
    const hidden  = document.getElementById('newCatEmoji');
    const current = hidden.value || '📁';

    picker.innerHTML = EMOJIS.map(e => `
      <button type="button" class="emoji-btn${e === current ? ' emoji-btn--active' : ''}"
        data-emoji="${e}" role="option" aria-selected="${e === current}"
        title="${e}">${e}</button>`
    ).join('');

    picker.querySelectorAll('.emoji-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        picker.querySelectorAll('.emoji-btn').forEach(b => {
          b.classList.remove('emoji-btn--active');
          b.setAttribute('aria-selected', 'false');
        });
        btn.classList.add('emoji-btn--active');
        btn.setAttribute('aria-selected', 'true');
        hidden.value = btn.dataset.emoji;
      });
    });
  }

  async _renderCategoryRadios() {
    const group = document.getElementById('catRadioGroup');
    // Recharger les catégories à jour
    try {
      const data = await apiGetCategories();
      this._allCategories = data.categories || [];
      const native = new Set(['technique', 'rh', 'juridique']);
      this._allCategories.forEach(c => {
        if (!native.has(c.key)) this._customCategories[c.key] = c;
      });
      this._renderDynamicCategoryItems();
    } catch { /* silencieux */ }

    const cats    = this._allCategories || [];
    group.innerHTML = cats.map(cat => `
      <label class="cat-radio">
        <input type="radio" name="uploadCat" value="${this._esc(cat.key)}">
        <span class="cat-radio__dot" style="background:${this._esc(cat.couleur)}"></span>
        <span class="cat-radio__emoji">${this._esc(cat.emoji)}</span>
        <span class="cat-radio__label">${this._esc(cat.label)}</span>
        <span class="cat-radio__count">${cat.nb_docs} doc${cat.nb_docs !== 1 ? 's' : ''}</span>
      </label>`).join('');

    group.querySelectorAll('input[name="uploadCat"]').forEach(radio => {
      radio.addEventListener('change', e => {
        this._uploadCategory = e.target.value;
        this._refreshSubmitBtn();
      });
    });
  }

  async _handleCreateCategory() {
    const key    = document.getElementById('newCatKey').value.trim().toLowerCase();
    const label  = document.getElementById('newCatLabel').value.trim();
    const emoji  = document.getElementById('newCatEmoji').value.trim() || '📁';
    const couleur = document.getElementById('newCatColor').value;

    if (!key || !label) {
      this._showFeedback(i18n.lang === 'en' ? '⚠️ Please fill in all fields.' : '⚠️ Remplissez tous les champs.', 'warn');
      return;
    }
    if (!/^[a-z0-9_-]+$/.test(key)) {
      this._showFeedback(i18n.t('newcat.key.hint'), 'warn');
      return;
    }

    document.getElementById('btnCreateCat').disabled = true;
    try {
      await apiCreateCategory({ key, label, emoji, couleur });
      this._customCategories[key] = { key, label, emoji, couleur };
      this._showFeedback(i18n.t('newcat.success', { label }), 'ok');
      this._showPanelCategory();
      await this._renderCategoryRadios();
    } catch (err) {
      this._showFeedback(`⚠️ ${err.message}`, 'warn');
    } finally {
      document.getElementById('btnCreateCat').disabled = false;
    }
  }

  _addFiles(fileList) {
    const allowed = new Set(['.pdf', '.docx', '.txt']);
    for (const file of fileList) {
      const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
      if (!allowed.has(ext)) continue;
      if (this._uploadFiles.some(f => f.name === file.name)) continue;
      this._uploadFiles.push(file);
    }
    this._renderFileList();
    this._refreshSubmitBtn();
  }

  _renderFileList() {
    const ul = document.getElementById('fileList');
    ul.innerHTML = this._uploadFiles.map((f, i) => `
      <li class="file-item">
        <span class="file-item__icon">${this._fileIcon(f.name)}</span>
        <span class="file-item__name" title="${this._esc(f.name)}">${this._esc(f.name)}</span>
        <span class="file-item__size">${this._humanSize(f.size)}</span>
        <button class="file-item__remove" data-idx="${i}" aria-label="Supprimer ${this._esc(f.name)}">×</button>
      </li>`).join('');

    ul.querySelectorAll('.file-item__remove').forEach(btn => {
      btn.addEventListener('click', () => {
        this._uploadFiles.splice(+btn.dataset.idx, 1);
        this._renderFileList();
        this._refreshSubmitBtn();
      });
    });
  }

  _refreshSubmitBtn() {
    document.getElementById('submitUploadBtn').disabled =
      this._uploadFiles.length === 0 || !this._uploadCategory;
  }

  async _handleUpload() {
    if (!this._uploadCategory) { this._showFeedback(i18n.t('upload.err.nocat'), 'warn'); return; }
    if (!this._uploadFiles.length) { this._showFeedback(i18n.t('upload.err.nofiles'), 'warn'); return; }

    const overlay   = document.getElementById('uploadOverlay');
    const fill      = document.getElementById('uploadProgressFill');
    const pct       = document.getElementById('uploadProgressPct');
    const overlayTxt = overlay.querySelector('.upload-overlay__text');

    overlay.hidden  = false;
    fill.style.width = '0%';
    pct.textContent  = '0%';
    if (overlayTxt) overlayTxt.textContent = i18n.t('upload.sending');
    document.getElementById('submitUploadBtn').disabled = true;
    document.getElementById('cancelUploadBtn').disabled = true;

    try {
      // ── Phase 1 : envoi des fichiers (rapide) ──────────────
      const result = await apiUploadFiles(this._uploadFiles, this._uploadCategory, progress => {
        fill.style.width = `${progress}%`;
        pct.textContent  = `${progress}%`;
      });

      const nb_ok  = result.fichiers.filter(f => f.statut === 'ok').length;
      const nb_err = result.fichiers.filter(f => f.statut === 'erreur').length;

      // ── Phase 2 : attente de l'indexation en arrière-plan ──
      if (result.background && nb_ok > 0) {
        fill.style.width = '100%';
        pct.textContent  = '100%';
        if (overlayTxt) overlayTxt.textContent = i18n.t('upload.indexing');

        try {
          await this._waitForIndexation();
          overlay.hidden = true;
          if (nb_err === 0) {
            this._showFeedback(i18n.t('upload.success', { n: nb_ok }), 'ok');
          } else {
            this._showFeedback(i18n.t('upload.partial', { ok: nb_ok, err: nb_err }), 'warn');
          }
        } catch (bgErr) {
          overlay.hidden = true;
          this._showFeedback(`⚠️ ${i18n.t('upload.bg.error')} ${bgErr.message}`, 'error');
        }
      } else {
        // Pas d'indexation (tous en erreur)
        overlay.hidden = true;
        if (nb_ok === 0) {
          this._showFeedback(i18n.t('upload.partial', { ok: 0, err: nb_err }), 'warn');
        } else {
          this._showFeedback(i18n.t('upload.partial', { ok: nb_ok, err: nb_err }), 'warn');
        }
      }

      await this._loadDocuments();
      this._uploadFiles = [];
      document.getElementById('fileList').innerHTML = '';
      this._refreshSubmitBtn();

      if (nb_ok > 0 && nb_err === 0) setTimeout(() => this._closeUploadModal(), 2000);

    } catch (err) {
      overlay.hidden = true;
      this._showFeedback(`⚠️ ${err.message}`, 'error');
    } finally {
      document.getElementById('cancelUploadBtn').disabled = false;
      if (overlayTxt) overlayTxt.textContent = i18n.t('upload.indexing');
    }
  }

  /**
   * Interroge /api/index/status toutes les 3 s jusqu'à la fin de l'indexation.
   * Résout avec le statut final, rejette si erreur d'indexation.
   * Timeout automatique après 8 minutes (sécurité).
   */
  _waitForIndexation(timeoutMs = 480000) {
    return new Promise((resolve, reject) => {
      const start = Date.now();
      const poll = setInterval(async () => {
        if (Date.now() - start > timeoutMs) {
          clearInterval(poll);
          resolve({ chunks: 0, files: 0 });   // timeout → on considère terminé
          return;
        }
        try {
          const status = await apiIndexStatus();
          if (!status.running) {
            clearInterval(poll);
            if (status.error) reject(new Error(status.error));
            else resolve(status);
          }
        } catch {
          /* erreur réseau transitoire — on continue à poller */
        }
      }, 3000);
    });
  }

  _showFeedback(html, type = 'ok') {
    const el  = document.getElementById('uploadFeedback');
    el.className = `upload-feedback upload-feedback--${type}`;
    el.innerHTML = html;
    el.hidden    = false;
  }

  // ─── Re-indexation manuelle ───────────────────────────────────────────────

  async _handleReindex() {
    const btn = document.getElementById('reindexBtn');
    const originalText = btn.textContent;

    btn.disabled    = true;
    btn.textContent = i18n.t('reindex.running');
    document.getElementById('uploadFeedback').hidden = true;

    try {
      const result = await apiReindex();

      if (result.background) {
        // Attendre la fin de l'indexation en arrière-plan
        const status = await this._waitForIndexation();
        this._showFeedback(
          i18n.t('reindex.success', { chunks: status.chunks, files: status.files }),
          'ok'
        );
      } else {
        this._showFeedback(
          i18n.t('reindex.success', { chunks: result.total_chunks, files: result.total_files }),
          'ok'
        );
      }

      await this._loadDocuments();
    } catch (err) {
      this._showFeedback(`${i18n.t('reindex.error')} ${err.message}`, 'error');
    } finally {
      btn.disabled    = false;
      btn.textContent = originalText;
    }
  }

  // ─── Suppression / Ré-indexation de documents ────────────────────────────

  async _deleteDocument(categorie, filename) {
    if (!confirm(i18n.t('delete.doc.confirm', { name: filename }))) return;

    // Feedback inline dans la sidebar
    const item = document.querySelector(`.doc-item[data-cat="${categorie}"][data-file="${CSS.escape(filename)}"]`);
    if (item) item.style.opacity = '0.4';

    try {
      await apiDeleteDocument(categorie, filename);
      this._showToast(i18n.t('delete.doc.success', { name: filename }), 'ok');
      await this._loadDocuments();
      await this._checkHealth();
    } catch (err) {
      if (item) item.style.opacity = '1';
      this._showToast(`${i18n.t('delete.doc.error')} ${err.message}`, 'error');
    }
  }

  async _deleteCategory(key, label) {
    if (!confirm(i18n.t('delete.cat.confirm', { label }))) return;
    try {
      const result = await apiDeleteCategory(key);
      // Si la catégorie supprimée était sélectionnée, remettre à "Tout"
      if (this.selectedCategory === key) {
        this.selectedCategory = null;
        this._updateCategoryBadge();
        document.querySelector('input[name="category"][value=""]').checked = true;
      }
      delete this._customCategories[key];
      this._renderDynamicCategoryItems();
      this._showToast(i18n.t('delete.cat.success', { label, n: result.docs_deleted }), 'ok');
      await this._loadDocuments();
      await this._checkHealth();
    } catch (err) {
      this._showToast(`${i18n.t('delete.cat.error')} ${err.message}`, 'error');
    }
  }

  async _reindexDocument(categorie, filename, btnEl) {
    const originalText = btnEl ? btnEl.textContent : '';
    if (btnEl) { btnEl.disabled = true; btnEl.textContent = '⏳'; }

    try {
      const result = await apiReindexFile(categorie, filename);
      this._showToast(
        i18n.t('reindex.file.success', { name: filename, chunks: result.chunks }),
        'ok'
      );
      await this._checkHealth();
    } catch (err) {
      this._showToast(`${i18n.t('reindex.file.error')} ${err.message}`, 'error');
    } finally {
      if (btnEl) { btnEl.disabled = false; btnEl.textContent = originalText; }
    }
  }

  /** Toast non-bloquant (remplace les alert) */
  _showToast(message, type = 'ok') {
    let toast = document.getElementById('appToast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'appToast';
      document.body.appendChild(toast);
    }
    toast.className = `app-toast app-toast--${type}`;
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => { toast.hidden = true; }, 4000);
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
    document.getElementById('sendBtn').disabled    = val;
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

  _fileIcon(name) {
    const ext = name.slice(name.lastIndexOf('.')).toLowerCase();
    return { '.pdf': '📕', '.docx': '📘', '.txt': '📄' }[ext] || '📎';
  }

  _humanSize(bytes) {
    if (bytes < 1024) return `${bytes} o`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} Ko`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
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
