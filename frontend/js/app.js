/**
 * app.js — Orchestrateur principal (refonte v2)
 * Plus de catégories natives. Les workspaces sont 100 % dynamiques.
 */

class App {
  constructor() {
    this.ui                 = new ChatUI();
    this.sessionId          = this._generateSessionId();
    this.selectedWorkspace  = null;
    this.isLoading          = false;
    this.documents          = [];
    this._healthData        = null;

    this._uploadFiles       = [];
    this._uploadWorkspace   = null;
    this._workspaces        = [];   // [{key, label, emoji, couleur, nb_docs}]
  }

  async init() {
    i18n.applyTranslations();
    this._bindEvents();
    this._bindUploadModal();
    this._bindRateLimitModal();
    await Promise.all([
      this._checkHealth(),
      this._loadWorkspaces(),
      this._loadDocuments(),
    ]);
    // Mise à jour périodique du badge toutes les 60s (arrière-plan, sans impact sur la conversation).
    setInterval(() => this._checkHealth().catch(() => {}), 60_000);
  }

  _bindRateLimitModal() {
    const modal = document.getElementById('rateLimitModal');
    const close = () => {
      modal.hidden = true;
      document.body.classList.remove('modal-open');
      this._checkHealth(); // rafraîchir le compteur
    };
    document.getElementById('rateLimitCloseBtn').addEventListener('click', close);
    modal.addEventListener('click', e => { if (e.target === modal) close(); });
  }

  // ─── Langue ───────────────────────────────────────────────────────────────

  _onLangChange() {
    this._renderDocumentList();
    this._updateCategoryBadge();
    if (this._healthData !== null) this._renderHealthBadge(this._healthData);
    this._renderWorkspaceSidebar();
  }

  // ─── Événements ────────────────────────────────────────────────────────

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
      charCounter.textContent = `${inputField.value.length}/2000`;
      inputField.style.height = 'auto';
      inputField.style.height = Math.min(inputField.scrollHeight, 160) + 'px';
    });

    inputField.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!sendBtn.disabled) this._handleSubmit();
      }
    });

    document.getElementById('newChatBtn').addEventListener('click', () => this._startNewChat());

    const menuBtn        = document.getElementById('menuBtn');
    const sidebar        = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    const _openSidebar = () => {
      sidebar.classList.add('sidebar--open');
      sidebarOverlay.classList.add('sidebar-overlay--visible');
      menuBtn.setAttribute('aria-expanded', 'true');
    };
    const _closeSidebar = () => {
      sidebar.classList.remove('sidebar--open');
      sidebarOverlay.classList.remove('sidebar-overlay--visible');
      menuBtn.setAttribute('aria-expanded', 'false');
    };

    menuBtn.addEventListener('click', () =>
      sidebar.classList.contains('sidebar--open') ? _closeSidebar() : _openSidebar()
    );
    sidebarOverlay.addEventListener('click', _closeSidebar);

    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && sidebar.classList.contains('sidebar--open')) {
        _closeSidebar();
        menuBtn.focus();
      }
    });

    // Le radio "Tout" est géré par delegation dans _renderWorkspaceSidebar
  }

  // ─── Submit chat ──────────────────────────────────────────────────────────

  async _handleSubmit() {
    const inputField = document.getElementById('inputField');
    const question   = inputField.value.trim();
    if (!question || this.isLoading) return;

    this.ui.addUserMessage(question);
    inputField.value = '';
    inputField.style.height = 'auto';
    document.getElementById('charCounter').textContent = '0/2000';
    document.getElementById('sendBtn').disabled = true;

    this._setLoading(true);
    this.ui.showSearchSteps();

    try {
      const reader  = await apiChatStream(question, this.selectedWorkspace, this.sessionId);
      const decoder = new TextDecoder();
      let   buffer  = '';
      let   botEl   = null; // null jusqu'au premier token

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
            if (!botEl) { this.ui.hideSearchSteps(); botEl = this.ui.startStreamingMessage(); }
            this.ui.appendToken(botEl, `\n\n⚠️ ${event.error}`);
          } else if (event.token !== undefined) {
            if (!botEl) { this.ui.hideSearchSteps(); botEl = this.ui.startStreamingMessage(); }
            this.ui.appendToken(botEl, event.token);
          }
          if (event.done) {
            this.ui.finalizeMessage(botEl, event.sources || []);
            // Mise à jour instantanée du compteur depuis l'événement SSE (sans requête HTTP).
            if (event.rate_limit > 0 && event.rate_remaining !== undefined) {
              this._updateRateChipDirect(event.rate_remaining, event.rate_used ?? 0, event.rate_limit);
            }
          }
        }
      }
    } catch (err) {
      this.ui.hideSearchSteps();
      if (err.code === 'RATE_LIMIT') {
        this._showRateLimitModal(err.message);
      } else {
        try {
          const data = await apiChat(question, this.selectedWorkspace, this.sessionId);
          this.ui.addAssistantMessage(data.answer, data.sources || []);
        } catch (err2) {
          if (err2.code === 'RATE_LIMIT') {
            this._showRateLimitModal(err2.message);
          } else {
            this.ui.addAssistantMessage(`⚠️ ${err2.message}`, []);
          }
        }
      }
    } finally {
      this._setLoading(false);
      // Rafraîchir silencieusement le badge (compteur de requêtes) sans toucher à la conversation.
      this._checkHealth().catch(() => {});
    }
  }

  // ─── Santé ─────────────────────────────────────────────────────────────

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
    const chip     = document.getElementById('rateChip');
    const isOk     = data.status === 'ok' && data.index_disponible;
    const isFr     = i18n.lang !== 'en';

    badge.className = `status-badge status-badge--${isOk ? 'ok' : 'warn'}`;

    if (isOk) {
      const nbWs   = data.nb_workspaces;
      const nbDocs = data.nb_documents ?? 0;
      const wsPart  = isFr
        ? `${nbWs} espace${nbWs !== 1 ? 's' : ''}`
        : `${nbWs} workspace${nbWs !== 1 ? 's' : ''}`;
      const docPart = isFr
        ? `${nbDocs} document${nbDocs !== 1 ? 's' : ''}`
        : `${nbDocs} document${nbDocs !== 1 ? 's' : ''}`;
      const rerankPart = data.reranker_actif
        ? (isFr ? ' · Reranking actif' : ' · Reranking on')
        : '';

      statusEl.textContent = `${isFr ? 'Prêt' : 'Ready'} · ${wsPart} · ${docPart}${rerankPart}`;

      // Puce requêtes (uniquement si une limite est configurée)
      if (data.requetes_limite > 0) {
        const used = data.requetes_utilisees ?? 0;
        const lim  = data.requetes_limite;
        const rem  = data.requetes_restantes ?? (lim - used);
        const pct  = rem / lim;

        let chipClass = 'rate-chip--ok';
        if (pct <= 0)       chipClass = 'rate-chip--danger';
        else if (pct < 0.3) chipClass = 'rate-chip--warn';

        const label = isFr
          ? `⚡ ${rem} / ${lim} req. restante${rem !== 1 ? 's' : ''}`
          : `⚡ ${rem} / ${lim} req. left`;

        chip.className   = `rate-chip ${chipClass}`;
        chip.textContent = label;
        chip.title       = isFr
          ? `${used} requête(s) utilisée(s) aujourd'hui sur ${lim} autorisée(s)`
          : `${used} of ${lim} requests used today`;
        chip.hidden = false;
      } else {
        chip.hidden = true;
      }
    } else {
      statusEl.textContent = i18n.t('status.noindex');
      chip.hidden = true;
    }

    if (!data.index_disponible) this._showNotice(i18n.t('notice.noindex'));
  }

  _updateRateChipDirect(remaining, used, limit) {
    const chip  = document.getElementById('rateChip');
    if (!chip || limit <= 0) return;
    const isFr  = i18n.lang !== 'en';
    const pct   = remaining / limit;
    let cls = 'rate-chip--ok';
    if (pct <= 0)       cls = 'rate-chip--danger';
    else if (pct < 0.3) cls = 'rate-chip--warn';
    chip.className   = `rate-chip ${cls}`;
    chip.textContent = isFr
      ? `⚡ ${remaining} / ${limit} req. restante${remaining !== 1 ? 's' : ''}`
      : `⚡ ${remaining} / ${limit} req. left`;
    chip.title = isFr
      ? `${used} requête(s) utilisée(s) aujourd'hui sur ${limit} autorisée(s)`
      : `${used} of ${limit} requests used today`;
    chip.hidden = false;

    // Mettre à jour les données santé en mémoire pour rester cohérent.
    if (this._healthData) {
      this._healthData.requetes_restantes = remaining;
      this._healthData.requetes_utilisees = used;
    }
  }

  _showRateLimitModal(detail) {
    const modal  = document.getElementById('rateLimitModal');
    const body   = document.getElementById('rateLimitBody');
    const isFr   = i18n.lang !== 'en';

    // Extraire le compteur depuis le message API si possible (ex: "5/10 requêtes")
    const match = detail && detail.match(/\((\d+)\/(\d+)/);
    if (match) {
      const [, used, lim] = match;
      body.innerHTML = isFr
        ? `Vous avez utilisé vos <strong>${used} / ${lim}</strong> requêtes disponibles pour aujourd'hui.<br>L'accès sera automatiquement rétabli <strong>demain</strong>.`
        : `You have used all <strong>${used} / ${lim}</strong> requests available today.<br>Access will be automatically restored <strong>tomorrow</strong>.`;
    } else {
      body.innerHTML = isFr
        ? `Vous avez utilisé toutes vos requêtes disponibles pour aujourd'hui.<br>L'accès sera automatiquement rétabli <strong>demain</strong>.`
        : `You have used all your available requests for today.<br>Access will be automatically restored <strong>tomorrow</strong>.`;
    }

    modal.hidden = false;
    document.body.classList.add('modal-open');
    document.getElementById('rateLimitCloseBtn').focus();
  }

  // ─── Workspaces ─────────────────────────────────────────────────────────

  async _loadWorkspaces() {
    try {
      const data = await apiGetWorkspaces();
      this._workspaces = data.workspaces || [];
    } catch {
      this._workspaces = [];
    }
    this._renderWorkspaceSidebar();
  }

  _renderWorkspaceSidebar() {
    const list = document.getElementById('categoryList');
    if (!list) return;

    const totalDocs = this._workspaces.reduce((sum, w) => sum + (w.nb_docs || 0), 0);

    let html = `
      <label class="category-item ${this.selectedWorkspace === null ? 'category-item--active' : ''}">
        <input type="radio" name="category" value="" ${this.selectedWorkspace === null ? 'checked' : ''}>
        <span class="category-dot all" aria-hidden="true"></span>
        <span>${i18n.t('ws.all')}</span>
        <span class="category-count">${totalDocs}</span>
      </label>
    `;

    if (!this._workspaces.length) {
      html += `<p class="doc-list__empty" style="margin-top:8px">${i18n.t('ws.none')}</p>`;
      list.innerHTML = html;
      this._bindWorkspaceRadios();
      return;
    }

    for (const ws of this._workspaces) {
      const isActive = this.selectedWorkspace === ws.key;
      html += `
        <label class="category-item category-item--custom ${isActive ? 'category-item--active' : ''}">
          <input type="radio" name="category" value="${this._esc(ws.key)}" ${isActive ? 'checked' : ''}>
          <span class="category-dot" style="background:${this._esc(ws.couleur)}" aria-hidden="true"></span>
          <span>${this._esc(ws.emoji)} ${this._esc(ws.label)}</span>
          <span class="category-count">${ws.nb_docs || 0}</span>
          <button class="cat-delete-btn" data-ws="${this._esc(ws.key)}" data-ws-label="${this._esc(ws.label)}"
            title="Supprimer ce workspace" aria-label="Supprimer ${this._esc(ws.label)}">🗑️</button>
        </label>`;
    }

    list.innerHTML = html;
    this._bindWorkspaceRadios();
  }

  _bindWorkspaceRadios() {
    const list = document.getElementById('categoryList');
    list.querySelectorAll('input[name="category"]').forEach(radio => {
      radio.addEventListener('change', e => {
        this.selectedWorkspace = e.target.value || null;
        this._updateCategoryBadge();
        list.querySelectorAll('.category-item').forEach(el =>
          el.classList.toggle('category-item--active', el.contains(e.target))
        );
      });
    });
    list.querySelectorAll('.cat-delete-btn').forEach(btn => {
      btn.addEventListener('click', e => {
        e.preventDefault();
        e.stopPropagation();
        this._deleteWorkspace(btn.dataset.ws, btn.dataset.wsLabel);
      });
    });
  }

  _updateCategoryBadge() {
    const badge   = document.getElementById('categoryBadge');
    const badgeEl = document.getElementById('categoryBadgeText');
    if (!this.selectedWorkspace) { badge.hidden = true; return; }
    const ws = this._workspaces.find(w => w.key === this.selectedWorkspace);
    badgeEl.textContent = ws ? `${ws.emoji} ${ws.label}` : this.selectedWorkspace;
    badge.hidden = false;
  }

  // ─── Documents ─────────────────────────────────────────────────────────

  async _loadDocuments() {
    try {
      const data     = await apiDocuments();
      this.documents = data.documents || [];
    } catch {
      this.documents = [];
    }
    this._renderDocumentList();
  }

  _renderDocumentList() {
    const list = document.getElementById('documentList');
    if (!this.documents.length) {
      list.innerHTML = `<p class="doc-list__empty">${i18n.t('docs.none')}</p>`;
      return;
    }
    const byWs = this.documents.reduce((acc, doc) => {
      (acc[doc.workspace] = acc[doc.workspace] || []).push(doc);
      return acc;
    }, {});
    list.innerHTML = Object.entries(byWs).map(([ws, docs]) => `
      <div class="doc-group">
        <div class="doc-group__label">${docs[0].workspace_emoji} ${this._esc(docs[0].workspace_label || ws)}</div>
        ${docs.map(d => `
          <div class="doc-item" title="${this._esc(d.nom)}" data-ws="${this._esc(d.workspace)}" data-file="${this._esc(d.nom)}">
            <span class="doc-item__icon">${this._fileIcon(d.nom)}</span>
            <span class="doc-item__name">${this._esc(d.nom.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' '))}</span>
            <span class="doc-item__actions">
              <button class="doc-item__btn doc-item__btn--reindex" title="Ré-indexer" aria-label="Ré-indexer ${this._esc(d.nom)}">🔄</button>
              <button class="doc-item__btn doc-item__btn--delete" title="Supprimer" aria-label="Supprimer ${this._esc(d.nom)}">🗑️</button>
            </span>
          </div>`).join('')}
      </div>`).join('');

    list.querySelectorAll('.doc-item__btn--delete').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const item = btn.closest('.doc-item');
        this._deleteDocument(item.dataset.ws, item.dataset.file);
      });
    });
    list.querySelectorAll('.doc-item__btn--reindex').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const item = btn.closest('.doc-item');
        this._reindexDocument(item.dataset.ws, item.dataset.file, btn);
      });
    });
  }

  // ─── Modal upload ──────────────────────────────────────────────────────

  _bindUploadModal() {
    const modal     = document.getElementById('uploadModal');
    const openBtn   = document.getElementById('openUploadBtn');
    const closeBtn  = document.getElementById('modalCloseBtn');
    const cancelBtn = document.getElementById('cancelUploadBtn');
    const submitBtn = document.getElementById('submitUploadBtn');

    openBtn.addEventListener('click', () => this._openUploadModal());

    [closeBtn, cancelBtn].forEach(btn => btn.addEventListener('click', () => this._closeUploadModal()));
    modal.addEventListener('click', e => { if (e.target === modal) this._closeUploadModal(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && !modal.hidden) this._closeUploadModal(); });

    document.getElementById('btnNewCat').addEventListener('click', () => this._showPanelNewCat());
    document.getElementById('btnCancelNewCat').addEventListener('click', () => this._showPanelCategory());
    document.getElementById('btnCreateCat').addEventListener('click', () => this._handleCreateWorkspace());

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

    submitBtn.addEventListener('click', () => this._handleUpload());
    document.getElementById('reindexBtn').addEventListener('click', () => this._handleReindex());
  }

  async _openUploadModal() {
    this._uploadFiles     = [];
    this._uploadWorkspace = null;
    document.getElementById('fileList').innerHTML      = '';
    document.getElementById('uploadFeedback').hidden   = true;
    document.getElementById('uploadOverlay').hidden    = true;
    document.getElementById('submitUploadBtn').disabled = true;

    this._showPanelCategory();
    await this._renderWorkspaceRadios();
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

  async _renderWorkspaceRadios() {
    const group = document.getElementById('catRadioGroup');
    try {
      const data = await apiGetWorkspaces();
      this._workspaces = data.workspaces || [];
    } catch { /* silencieux */ }

    if (!this._workspaces.length) {
      group.innerHTML = `<p class="doc-list__empty">${i18n.t('ws.none')}</p>`;
      return;
    }

    group.innerHTML = this._workspaces.map(ws => `
      <label class="cat-radio">
        <input type="radio" name="uploadCat" value="${this._esc(ws.key)}">
        <span class="cat-radio__dot" style="background:${this._esc(ws.couleur)}"></span>
        <span class="cat-radio__emoji">${this._esc(ws.emoji)}</span>
        <span class="cat-radio__label">${this._esc(ws.label)}</span>
        <span class="cat-radio__count">${ws.nb_docs} doc${ws.nb_docs !== 1 ? 's' : ''}</span>
      </label>`).join('');

    group.querySelectorAll('input[name="uploadCat"]').forEach(radio => {
      radio.addEventListener('change', e => {
        this._uploadWorkspace = e.target.value;
        this._refreshSubmitBtn();
      });
    });
  }

  async _handleCreateWorkspace() {
    const key     = document.getElementById('newCatKey').value.trim().toLowerCase();
    const label   = document.getElementById('newCatLabel').value.trim();
    const emoji   = document.getElementById('newCatEmoji').value.trim() || '📁';
    const couleur = document.getElementById('newCatColor').value;

    if (!key || !label) {
      this._showFeedback(i18n.lang === 'en' ? '⚠️ Please fill in all fields.' : '⚠️ Remplissez tous les champs.', 'warn');
      return;
    }
    if (!/^[a-z0-9][a-z0-9_-]*$/.test(key)) {
      this._showFeedback(i18n.t('newws.key.hint'), 'warn');
      return;
    }

    document.getElementById('btnCreateCat').disabled = true;
    try {
      const ws = await apiCreateWorkspace({ key, label, emoji, couleur });
      this._showFeedback(i18n.t('newws.success', { label }), 'ok');
      this._showPanelCategory();
      await this._renderWorkspaceRadios();
      this._renderWorkspaceSidebar();
    } catch (err) {
      this._showFeedback(`⚠️ ${err.message}`, 'warn');
    } finally {
      document.getElementById('btnCreateCat').disabled = false;
    }
  }

  _addFiles(fileList) {
    const allowed  = new Set(['.pdf', '.docx', '.txt', '.md']);
    const MAX_SIZE = 50 * 1024 * 1024;
    let   hasWarn  = false;

    for (const file of fileList) {
      const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
      if (!allowed.has(ext)) continue;
      if (file.size > MAX_SIZE) {
        this._showFeedback(
          i18n.t('upload.file.toobig', { name: this._esc(file.name), size: this._humanSize(file.size) }),
          'warn',
        );
        hasWarn = true;
        continue;
      }
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
      this._uploadFiles.length === 0 || !this._uploadWorkspace;
  }

  async _handleUpload() {
    if (!this._uploadWorkspace) { this._showFeedback(i18n.t('upload.err.nows'), 'warn'); return; }
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
      const result = await apiUploadFiles(this._uploadFiles, this._uploadWorkspace, progress => {
        fill.style.width = `${progress}%`;
        pct.textContent  = `${progress}%`;
      });

      const nb_ok   = result.fichiers.filter(f => f.statut === 'ok').length;
      const nb_err  = result.fichiers.filter(f => f.statut === 'erreur').length;
      const errored = result.fichiers.filter(f => f.statut === 'erreur');

      const _errDetail = () => {
        if (!errored.length) return '';
        const lines = errored.map(f =>
          `• <strong>${this._esc(f.nom)}</strong> : ${this._esc(f.detail || 'Erreur inconnue')}`
        ).join('<br>');
        return `<br><small style="opacity:.85">${lines}</small>`;
      };

      if (result.background && nb_ok > 0) {
        fill.style.width = '100%';
        pct.textContent  = '100%';
        if (overlayTxt) overlayTxt.textContent = i18n.t('upload.indexing');
        try {
          const status = await this._waitForIndexation();
          overlay.hidden = true;
          const bgWarns = status.warnings || [];
          const okFinal = nb_ok - bgWarns.length;
          if (bgWarns.length > 0 || nb_err > 0) {
            const warnLines = bgWarns.map(w => `• ${this._esc(w)}`).join('<br>');
            this._showFeedback(
              i18n.t('upload.partial', { ok: Math.max(0, okFinal), err: nb_err + bgWarns.length })
              + (warnLines ? `<br><small style="opacity:.85">${warnLines}</small>` : '')
              + _errDetail(),
              'warn',
            );
          } else {
            this._showFeedback(i18n.t('upload.success', { n: nb_ok }), 'ok');
          }
        } catch (bgErr) {
          overlay.hidden = true;
          this._showFeedback(`⚠️ ${i18n.t('upload.bg.error')} ${bgErr.message}`, 'error');
        }
      } else {
        overlay.hidden = true;
        this._showFeedback(
          i18n.t('upload.partial', { ok: nb_ok, err: nb_err }) + _errDetail(),
          nb_ok > 0 ? 'warn' : 'error',
        );
      }

      await Promise.all([this._loadDocuments(), this._loadWorkspaces()]);
      await this._checkHealth();
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

  _waitForIndexation(timeoutMs = 480000) {
    return new Promise((resolve, reject) => {
      const start = Date.now();
      const poll = setInterval(async () => {
        if (Date.now() - start > timeoutMs) {
          clearInterval(poll);
          resolve({ chunks: 0, files: 0 });
          return;
        }
        try {
          const status = await apiIndexStatus();
          if (!status.running) {
            clearInterval(poll);
            if (status.error) reject(new Error(status.error));
            else resolve(status);
          }
        } catch { /* erreur réseau transitoire */ }
      }, 3000);
    });
  }

  _showFeedback(html, type = 'ok') {
    const el = document.getElementById('uploadFeedback');
    el.className = `upload-feedback upload-feedback--${type}`;
    el.innerHTML = html;
    el.hidden    = false;
  }

  // ─── Re-indexation manuelle ───────────────────────────────────────────

  async _handleReindex() {
    const btn = document.getElementById('reindexBtn');
    const originalText = btn.textContent;

    btn.disabled    = true;
    btn.textContent = i18n.t('reindex.running');
    document.getElementById('uploadFeedback').hidden = true;

    try {
      const result = await apiReindex();
      if (result.background) {
        const status = await this._waitForIndexation();
        this._showFeedback(
          i18n.t('reindex.success', { chunks: status.chunks, files: status.files }), 'ok'
        );
      } else {
        this._showFeedback(
          i18n.t('reindex.success', { chunks: result.total_chunks, files: result.total_files }), 'ok'
        );
      }
      await Promise.all([this._loadDocuments(), this._loadWorkspaces()]);
      await this._checkHealth();
    } catch (err) {
      this._showFeedback(`${i18n.t('reindex.error')} ${err.message}`, 'error');
    } finally {
      btn.disabled    = false;
      btn.textContent = originalText;
    }
  }

  // ─── Suppression / Ré-indexation ──────────────────────────────────────

  async _deleteDocument(workspace, filename) {
    if (!confirm(i18n.t('delete.doc.confirm', { name: filename }))) return;

    const item = document.querySelector(
      `.doc-item[data-ws="${CSS.escape(workspace)}"][data-file="${CSS.escape(filename)}"]`
    );
    if (item) item.style.opacity = '0.4';

    try {
      const result = await apiDeleteDocument(workspace, filename);
      if (result.background) {
        this._showToast(i18n.t('delete.doc.pending', { name: filename }), 'ok');
        this._waitForIndexation().then(async () => {
          this._showToast(i18n.t('delete.doc.success', { name: filename }), 'ok');
          await Promise.all([this._loadDocuments(), this._loadWorkspaces()]);
          await this._checkHealth();
        }).catch(err => {
          this._showToast(`${i18n.t('delete.doc.error')} ${err.message}`, 'error');
        });
      } else {
        this._showToast(i18n.t('delete.doc.success', { name: filename }), 'ok');
      }
      await Promise.all([this._loadDocuments(), this._loadWorkspaces()]);
      await this._checkHealth();
    } catch (err) {
      if (err.status === 404) {
        // File already absent on disk — treat as deleted and refresh list
        this._showToast(i18n.t('delete.doc.success', { name: filename }), 'ok');
        await Promise.all([this._loadDocuments(), this._loadWorkspaces()]);
        await this._checkHealth();
      } else {
        if (item) item.style.opacity = '1';
        this._showToast(`${i18n.t('delete.doc.error')} ${err.message}`, 'error');
      }
    }
  }

  async _deleteWorkspace(key, label) {
    if (!confirm(i18n.t('delete.ws.confirm', { label }))) return;
    try {
      const result = await apiDeleteWorkspace(key);

      if (this.selectedWorkspace === key) {
        this.selectedWorkspace = null;
        this._updateCategoryBadge();
      }
      this._workspaces = this._workspaces.filter(w => w.key !== key);
      this._renderWorkspaceSidebar();

      if (result.background) {
        this._showToast(i18n.t('delete.ws.pending', { label, n: result.docs_deleted }), 'ok');
        this._waitForIndexation().then(async () => {
          this._showToast(i18n.t('delete.ws.success', { label, n: result.docs_deleted }), 'ok');
          await Promise.all([this._loadDocuments(), this._loadWorkspaces()]);
          await this._checkHealth();
        }).catch(() => {});
      } else {
        this._showToast(i18n.t('delete.ws.success', { label, n: result.docs_deleted }), 'ok');
      }

      await Promise.all([this._loadDocuments(), this._loadWorkspaces()]);
      await this._checkHealth();
    } catch (err) {
      this._showToast(`${i18n.t('delete.ws.error')} ${err.message}`, 'error');
    }
  }

  async _reindexDocument(workspace, filename, btnEl) {
    const originalText = btnEl ? btnEl.textContent : '';
    if (btnEl) { btnEl.disabled = true; btnEl.textContent = '⏳'; }

    try {
      const result = await apiReindexFile(workspace, filename);
      this._showToast(
        i18n.t('reindex.file.success', { name: filename, chunks: result.chunks }), 'ok'
      );
      await this._checkHealth();
    } catch (err) {
      this._showToast(`${i18n.t('reindex.file.error')} ${err.message}`, 'error');
    } finally {
      if (btnEl) { btnEl.disabled = false; btnEl.textContent = originalText; }
    }
  }

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

  async _startNewChat() {
    if (this.ui.hasMessages()) {
      try { await apiClearSession(this.sessionId); } catch { /* silencieux */ }
    }
    this.sessionId = this._generateSessionId();
    this.ui.clear();
  }

  // ─── Utilitaires ─────────────────────────────────────────────────────

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
    return { '.pdf': '📕', '.docx': '📘', '.txt': '📄', '.md': '📝' }[ext] || '📎';
  }

  _humanSize(bytes) {
    if (bytes < 1024) return `${bytes} o`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} Ko`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
  }
}

function clearCategory() {
  const radio = document.querySelector('input[name="category"][value=""]');
  if (radio) {
    radio.checked = true;
    radio.dispatchEvent(new Event('change'));
  }
  window._app.selectedWorkspace = null;
  window._app._updateCategoryBadge();
  document.querySelectorAll('.category-item').forEach(el => el.classList.remove('category-item--active'));
  const firstItem = document.querySelector('.category-item');
  if (firstItem) firstItem.classList.add('category-item--active');
}

document.addEventListener('DOMContentLoaded', () => {
  window._app = new App();
  window._app.init();
});
