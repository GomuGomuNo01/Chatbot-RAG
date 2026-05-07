/**
 * chat.js — Interface de chat : bulles, streaming, sources, Markdown
 */

const CATEGORY_BASE = {
  technique: { color: '#3B82F6', bg: '#EFF6FF', emoji: '⚙️' },
  rh:        { color: '#10B981', bg: '#ECFDF5', emoji: '👥' },
  juridique: { color: '#8B5CF6', bg: '#F5F3FF', emoji: '⚖️' },
};

function getCategoryMeta(cat) {
  const base  = CATEGORY_BASE[cat] || { color: '#6B7280', bg: '#F9FAFB', emoji: '📄' };
  const label = typeof i18n !== 'undefined'
    ? i18n.t(`meta.${cat}.label`)
    : (cat || cat);
  return { ...base, label };
}

class ChatUI {
  constructor() {
    this.messagesEl = document.getElementById('messages');
    this.typingEl   = document.getElementById('typingIndicator');
    this.welcomeEl  = document.getElementById('welcomeScreen');
    this._msgCount  = 0;
  }

  /** Bulle utilisateur */
  addUserMessage(text) {
    this._hideWelcome();
    const el = this._make('div', 'message message--user');
    el.innerHTML = `
      <div class="message__bubble">
        <p class="message__text">${this._esc(text)}</p>
        <time class="message__time">${this._ts()}</time>
      </div>
      <div class="message__avatar message__avatar--user" aria-hidden="true">Vous</div>`;
    this._append(el);
    this._msgCount++;
    return el;
  }

  /** Bulle assistant complète (non-streaming) */
  addAssistantMessage(text, sources = []) {
    this._hideWelcome();
    const el = this._make('div', 'message message--assistant');
    el.innerHTML = `
      <div class="message__avatar message__avatar--bot" aria-hidden="true">🤖</div>
      <div class="message__body">
        <div class="message__bubble">
          <div class="message__text">${this._md(text)}</div>
          <time class="message__time">${this._ts()}</time>
        </div>
        ${sources.length ? this._renderSources(sources) : ''}
      </div>`;
    this._bindAccordion(el);
    this._bindCopyButtons(el);
    this._append(el);
    this._msgCount++;
    return el;
  }

  // ── Streaming ──────────────────────────────────────────────────────────────

  startStreamingMessage() {
    this._hideWelcome();
    const el = this._make('div', 'message message--assistant');
    el.innerHTML = `
      <div class="message__avatar message__avatar--bot" aria-hidden="true">🤖</div>
      <div class="message__body">
        <div class="message__bubble">
          <div class="message__text message__text--streaming" data-raw=""></div>
        </div>
      </div>`;
    this._append(el);
    this._msgCount++;
    return el;
  }

  appendToken(el, token) {
    const textEl = el.querySelector('.message__text--streaming');
    if (!textEl) return;
    textEl.dataset.raw += token;
    textEl.innerHTML = this._md(textEl.dataset.raw) + '<span class="cursor-blink" aria-hidden="true"></span>';
    this.scrollToBottom();
  }

  finalizeMessage(el, sources = []) {
    const textEl = el.querySelector('.message__text--streaming');
    if (textEl) {
      textEl.classList.remove('message__text--streaming');
      const cursor = textEl.querySelector('.cursor-blink');
      if (cursor) cursor.remove();
      // Ajouter timestamp
      const time = document.createElement('time');
      time.className   = 'message__time';
      time.textContent = this._ts();
      textEl.closest('.message__bubble').appendChild(time);
    }
    if (sources && sources.length) {
      const body = el.querySelector('.message__body');
      const div  = document.createElement('div');
      div.innerHTML = this._renderSources(sources);
      body.appendChild(div.firstElementChild);
      this._bindAccordion(el);
    }
    this._bindCopyButtons(el);
    this.scrollToBottom();
  }

  // ── Indicateur de frappe ───────────────────────────────────────────────────

  showTyping()  { this.typingEl.hidden = false; this.scrollToBottom(); }
  hideTyping()  { this.typingEl.hidden = true; }

  scrollToBottom() {
    const c = this.messagesEl.closest('.chat-container');
    if (c) requestAnimationFrame(() => { c.scrollTop = c.scrollHeight; });
  }

  clear() {
    this.messagesEl.innerHTML = '';
    this._msgCount = 0;
    if (this.welcomeEl) this.welcomeEl.hidden = false;
    this.hideTyping();
  }

  hasMessages() { return this._msgCount > 0; }

  // ── Sources ────────────────────────────────────────────────────────────────

  _renderSources(sources) {
    const cards = sources.map((s, i) => {
      const meta    = getCategoryMeta(s.categorie);
      const score   = Math.round(s.score * 100);
      const nom     = s.fichier.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' ');
      const page    = typeof s.page === 'number' ? `p. ${s.page}` : s.page;
      const extrait = this._esc(s.extrait || '');

      // Couleur de la barre de score
      const barColor = score >= 70 ? '#10B981'
                     : score >= 40 ? '#F59E0B'
                     : '#EF4444';

      return `
        <div class="source-card" style="--cat-color:${meta.color};--cat-bg:${meta.bg}">
          <div class="source-card__header">
            <span class="source-card__index" aria-label="Source ${i + 1}">${i + 1}</span>
            <div class="source-card__meta">
              <span class="source-card__name" title="${this._esc(s.fichier)}">${this._esc(nom)}</span>
              <div class="source-card__tags">
                <span class="source-card__badge">${meta.emoji} ${meta.label}</span>
                <span class="source-card__page">📄 ${page}</span>
              </div>
            </div>
            <div class="source-card__score-wrap" title="Pertinence : ${score}%">
              <div class="source-card__score-track">
                <div class="source-card__score-fill" style="width:${score}%;background:${barColor}"></div>
              </div>
              <span class="source-card__score-label">${score}%</span>
            </div>
          </div>
          ${extrait ? `
          <button class="source-card__toggle" aria-expanded="false">
            <span class="source-card__toggle-icon">▶</span> ${i18n.t('sources.show')}
          </button>
          <div class="source-card__excerpt" hidden>
            <blockquote>${extrait}</blockquote>
          </div>` : ''}
        </div>`;
    }).join('');

    return `
      <div class="sources">
        <span class="sources__label">📎 ${i18n.t('sources.title', { n: sources.length })}</span>
        <div class="sources__list">${cards}</div>
      </div>`;
  }

  _bindAccordion(el) {
    el.querySelectorAll('.source-card__toggle').forEach(btn => {
      btn.addEventListener('click', () => {
        const card    = btn.closest('.source-card');
        const excerpt = card.querySelector('.source-card__excerpt');
        const icon    = btn.querySelector('.source-card__toggle-icon');
        const open    = excerpt.hidden;
        excerpt.hidden = !open;
        btn.setAttribute('aria-expanded', open);
        icon.textContent = open ? '▼' : '▶';
        btn.querySelector('.source-card__toggle-icon').nextSibling.textContent =
          ' ' + i18n.t(open ? 'sources.hide' : 'sources.show');
      });
    });
  }

  // ── Copier code ────────────────────────────────────────────────────────────

  _bindCopyButtons(el) {
    el.querySelectorAll('.code-block').forEach(pre => {
      if (pre.querySelector('.code-copy-btn')) return; // Already bound
      const btn = document.createElement('button');
      btn.className   = 'code-copy-btn';
      btn.title       = 'Copier';
      btn.textContent = '⎘';
      btn.addEventListener('click', () => {
        const code = pre.querySelector('code');
        navigator.clipboard.writeText(code ? code.innerText : pre.innerText).then(() => {
          btn.textContent = '✓';
          btn.classList.add('code-copy-btn--done');
          setTimeout(() => {
            btn.textContent = '⎘';
            btn.classList.remove('code-copy-btn--done');
          }, 1800);
        }).catch(() => {});
      });
      pre.style.position = 'relative';
      pre.appendChild(btn);
    });
  }

  // ── Markdown ───────────────────────────────────────────────────────────────

  _md(raw) {
    if (!raw) return '';

    // 1. Blocs de code (``` lang \n ... ```)
    const codeBlocks = [];
    let s = raw.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
      const safeLang = this._esc(lang) || 'text';
      const idx = codeBlocks.push(
        `<pre class="code-block" data-lang="${safeLang}"><code class="lang-${safeLang}">${this._esc(code.trim())}</code></pre>`
      ) - 1;
      return `\x00CODE${idx}\x00`;
    });

    // 2. Code inline `...`
    const inlineCodes = [];
    s = s.replace(/`([^`\n]+)`/g, (_, c) => {
      const idx = inlineCodes.push(`<code class="inline-code">${this._esc(c)}</code>`) - 1;
      return `\x00INLINE${idx}\x00`;
    });

    // 3. Échapper le HTML restant
    s = this._esc(s);

    // 4. Titres
    s = s.replace(/^### (.+)$/gm, '<h3 class="md-h3">$1</h3>');
    s = s.replace(/^## (.+)$/gm,  '<h2 class="md-h2">$1</h2>');
    s = s.replace(/^# (.+)$/gm,   '<h1 class="md-h1">$1</h1>');

    // 5. Gras et italique (ordre : ***bold-italic** > **bold** > *italic*)
    s = s.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    s = s.replace(/\*\*(.+?)\*\*/g,     '<strong>$1</strong>');
    s = s.replace(/\*([^*\n]+?)\*/g,    '<em>$1</em>');

    // 6. Tableaux Markdown  | col | col | …
    s = s.replace(/((?:^\|.+\|\n?)+)/gm, block => this._renderTable(block));

    // 7. Ligne horizontale
    s = s.replace(/^---$/gm, '<hr class="md-hr">');

    // 8. Listes numérotées
    s = s.replace(/((?:^\d+\. .+\n?)+)/gm, block => {
      const items = block.trim().split('\n')
        .map(l => `<li>${l.replace(/^\d+\.\s+/, '')}</li>`).join('');
      return `<ol class="md-ol">${items}</ol>`;
    });

    // 9. Listes à puces
    s = s.replace(/((?:^[-•*] .+\n?)+)/gm, block => {
      const items = block.trim().split('\n')
        .map(l => `<li>${l.replace(/^[-•*]\s+/, '')}</li>`).join('');
      return `<ul class="md-ul">${items}</ul>`;
    });

    // 10. Paragraphes (double saut de ligne)
    s = s.split(/\n{2,}/).map(para => {
      para = para.trim();
      if (!para) return '';
      if (/^<(h[123]|ul|ol|hr|pre|table)/.test(para)) return para;
      return `<p>${para.replace(/\n/g, '<br>')}</p>`;
    }).join('\n');

    // 11. Restaurer blocs
    s = s.replace(/\x00CODE(\d+)\x00/g,   (_, i) => codeBlocks[+i]);
    s = s.replace(/\x00INLINE(\d+)\x00/g, (_, i) => inlineCodes[+i]);

    return s;
  }

  /** Convertit un bloc de lignes | col | ... en <table> HTML. */
  _renderTable(block) {
    const lines = block.trim().split('\n').filter(l => l.trim());
    if (lines.length < 2) return block;

    const parseRow = l =>
      l.replace(/^\||\|$/g, '').split('|').map(c => c.trim());

    const headers  = parseRow(lines[0]);
    const isSep    = l => /^\|?[\s|:-]+\|?$/.test(l);

    // Ligne 2 doit être un séparateur |---|---|
    if (!isSep(lines[1])) return block;

    const dataRows = lines.slice(2);

    const headHtml = headers.map(h => `<th>${this._esc(h)}</th>`).join('');
    const bodyHtml = dataRows.map(row => {
      const cells = parseRow(row);
      return `<tr>${cells.map(c => `<td>${this._esc(c)}</td>`).join('')}</tr>`;
    }).join('');

    return `<div class="md-table-wrap"><table class="md-table"><thead><tr>${headHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></div>`;
  }

  // ── Utilitaires ────────────────────────────────────────────────────────────

  _esc(str) {
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  _ts() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  _make(tag, cls) {
    const el = document.createElement(tag);
    el.className = cls;
    return el;
  }

  _hideWelcome() { if (this.welcomeEl) this.welcomeEl.hidden = true; }

  _append(el) {
    this.messagesEl.appendChild(el);
    this.scrollToBottom();
  }
}
