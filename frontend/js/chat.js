/**
 * chat.js — Interface de chat : bulles, streaming, sources, Markdown
 */

const CATEGORY_META = {
  technique:  { label: 'Technique',  color: '#3B82F6', bg: '#EFF6FF', emoji: '⚙️'  },
  rh:         { label: 'RH',         color: '#10B981', bg: '#ECFDF5', emoji: '👥'  },
  juridique:  { label: 'Juridique',  color: '#8B5CF6', bg: '#F5F3FF', emoji: '⚖️'  },
};

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
      </div>
      <div class="message__avatar message__avatar--user">Vous</div>`;
    this._append(el);
    this._msgCount++;
    return el;
  }

  /** Bulle assistant complète (non-streaming) */
  addAssistantMessage(text, sources = []) {
    this._hideWelcome();
    const el = this._make('div', 'message message--assistant');
    el.innerHTML = `
      <div class="message__avatar message__avatar--bot">🤖</div>
      <div class="message__body">
        <div class="message__bubble">
          <div class="message__text">${this._md(text)}</div>
        </div>
        ${sources.length ? this._renderSources(sources) : ''}
      </div>`;
    this._bindAccordion(el);
    this._append(el);
    this._msgCount++;
    return el;
  }

  // ── Streaming ──────────────────────────────────────────────────────────────

  /** Crée une bulle vide prête pour le streaming. */
  startStreamingMessage() {
    this._hideWelcome();
    const el = this._make('div', 'message message--assistant');
    el.innerHTML = `
      <div class="message__avatar message__avatar--bot">🤖</div>
      <div class="message__body">
        <div class="message__bubble">
          <div class="message__text message__text--streaming" data-raw=""></div>
        </div>
      </div>`;
    this._append(el);
    this._msgCount++;
    return el;
  }

  /** Ajoute un token à la bulle en cours de streaming. */
  appendToken(el, token) {
    const textEl = el.querySelector('.message__text--streaming');
    if (!textEl) return;
    textEl.dataset.raw += token;
    textEl.innerHTML = this._md(textEl.dataset.raw) + '<span class="cursor-blink"></span>';
    this.scrollToBottom();
  }

  /** Finalise la bulle : retire le curseur, ajoute les sources. */
  finalizeMessage(el, sources = []) {
    const textEl = el.querySelector('.message__text--streaming');
    if (textEl) {
      textEl.classList.remove('message__text--streaming');
      const cursor = textEl.querySelector('.cursor-blink');
      if (cursor) cursor.remove();
    }
    if (sources && sources.length) {
      const body = el.querySelector('.message__body');
      const div  = document.createElement('div');
      div.innerHTML = this._renderSources(sources);
      body.appendChild(div.firstElementChild);
      this._bindAccordion(el);
    }
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
      const meta   = CATEGORY_META[s.categorie] || { label: s.categorie, color: '#6B7280', bg: '#F9FAFB', emoji: '📄' };
      const score  = Math.round(s.score * 100);
      const nom    = s.fichier.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' ');
      const page   = typeof s.page === 'number' ? `p. ${s.page}` : s.page;
      const extrait = this._esc(s.extrait || '');
      return `
        <div class="source-card" style="--cat-color:${meta.color};--cat-bg:${meta.bg}">
          <div class="source-card__header">
            <span class="source-card__index">${i + 1}</span>
            <div class="source-card__meta">
              <span class="source-card__name" title="${this._esc(s.fichier)}">${this._esc(nom)}</span>
              <div class="source-card__tags">
                <span class="source-card__badge">${meta.emoji} ${meta.label}</span>
                <span class="source-card__page">📄 ${page}</span>
                <span class="source-card__score" title="Pertinence">
                  <span class="source-card__score-bar" style="width:${score}%"></span>
                  ${score}%
                </span>
              </div>
            </div>
          </div>
          ${extrait ? `
          <button class="source-card__toggle">Voir l'extrait ▼</button>
          <div class="source-card__excerpt"><blockquote>${extrait}</blockquote></div>` : ''}
        </div>`;
    }).join('');
    return `
      <div class="sources">
        <span class="sources__label">📎 Sources (${sources.length})</span>
        <div class="sources__list">${cards}</div>
      </div>`;
  }

  _bindAccordion(el) {
    el.querySelectorAll('.source-card__toggle').forEach(btn => {
      btn.addEventListener('click', () => {
        const excerpt = btn.closest('.source-card').querySelector('.source-card__excerpt');
        const open    = excerpt.classList.toggle('source-card__excerpt--open');
        btn.textContent = open ? "Masquer l'extrait ▲" : "Voir l'extrait ▼";
      });
    });
  }

  // ── Markdown ───────────────────────────────────────────────────────────────

  /** Convertit le Markdown en HTML sécurisé. */
  _md(raw) {
    if (!raw) return '';

    // 1. Blocs de code (``` ... ```) — traiter avant l'échappement
    const codeBlocks = [];
    let s = raw.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
      const idx = codeBlocks.push(
        `<pre class="code-block"><code class="lang-${this._esc(lang) || 'text'}">${this._esc(code.trim())}</code></pre>`
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

    // 5. Gras et italique
    s = s.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    s = s.replace(/\*\*(.+?)\*\*/g,     '<strong>$1</strong>');
    s = s.replace(/\*(.+?)\*/g,         '<em>$1</em>');

    // 6. Ligne horizontale
    s = s.replace(/^---$/gm, '<hr class="md-hr">');

    // 7. Listes numérotées
    s = s.replace(/((?:^\d+\. .+\n?)+)/gm, block => {
      const items = block.trim().split('\n').map(l => `<li>${l.replace(/^\d+\. /, '')}</li>`).join('');
      return `<ol class="md-ol">${items}</ol>`;
    });

    // 8. Listes à puces
    s = s.replace(/((?:^[-•*] .+\n?)+)/gm, block => {
      const items = block.trim().split('\n').map(l => `<li>${l.replace(/^[-•*] /, '')}</li>`).join('');
      return `<ul class="md-ul">${items}</ul>`;
    });

    // 9. Paragraphes (double saut de ligne)
    s = s.split(/\n{2,}/).map(para => {
      para = para.trim();
      if (!para) return '';
      if (/^<(h[123]|ul|ol|hr|pre)/.test(para)) return para;
      return `<p>${para.replace(/\n/g, '<br>')}</p>`;
    }).join('\n');

    // 10. Restaurer code blocks et inline codes
    s = s.replace(/\x00CODE(\d+)\x00/g,   (_, i) => codeBlocks[i]);
    s = s.replace(/\x00INLINE(\d+)\x00/g, (_, i) => inlineCodes[i]);

    return s;
  }

  // ── Utilitaires ────────────────────────────────────────────────────────────

  _esc(str) {
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
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
