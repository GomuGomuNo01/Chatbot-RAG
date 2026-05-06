/**
 * chat.js — Gestion de l'interface de chat (bulles, sources, indicateur)
 * Ne fait aucun appel réseau ; délègue à api.js via app.js.
 */

const CATEGORY_META = {
  technique:  { label: 'Technique',  color: '#3B82F6', bg: '#EFF6FF', emoji: '⚙️'  },
  rh:         { label: 'RH',         color: '#10B981', bg: '#ECFDF5', emoji: '👥'  },
  juridique:  { label: 'Juridique',  color: '#8B5CF6', bg: '#F5F3FF', emoji: '⚖️'  },
};

class ChatUI {
  constructor() {
    this.messagesEl  = document.getElementById('messages');
    this.typingEl    = document.getElementById('typingIndicator');
    this.welcomeEl   = document.getElementById('welcomeScreen');
    this._msgCount   = 0;
  }

  /** Ajoute une bulle utilisateur dans le chat. */
  addUserMessage(text) {
    this._hideWelcome();
    const el = this._createElement('div', 'message message--user');
    el.innerHTML = `
      <div class="message__bubble">
        <p class="message__text">${this._escapeHtml(text)}</p>
      </div>
      <div class="message__avatar message__avatar--user">Vous</div>
    `;
    this._append(el);
    this._msgCount++;
    return el;
  }

  /**
   * Ajoute une bulle assistant avec ses sources citées.
   * @param {string} text   — réponse Markdown-like
   * @param {Array}  sources — liste de SourceResponse
   */
  addAssistantMessage(text, sources = []) {
    this._hideWelcome();
    const el = this._createElement('div', 'message message--assistant');

    const sourcesHtml = sources.length
      ? this._renderSources(sources)
      : '';

    el.innerHTML = `
      <div class="message__avatar message__avatar--bot">🤖</div>
      <div class="message__body">
        <div class="message__bubble">
          <div class="message__text">${this._renderMarkdown(text)}</div>
        </div>
        ${sourcesHtml}
      </div>
    `;

    this._append(el);
    this._msgCount++;

    // Gestion accordéon des extraits
    el.querySelectorAll('.source-card__toggle').forEach(btn => {
      btn.addEventListener('click', () => {
        const excerpt = btn.closest('.source-card').querySelector('.source-card__excerpt');
        const isOpen  = excerpt.classList.toggle('source-card__excerpt--open');
        btn.textContent = isOpen ? 'Masquer l\'extrait ▲' : 'Voir l\'extrait ▼';
      });
    });

    return el;
  }

  /** Affiche l'indicateur "en train d'écrire…" */
  showTyping() {
    this.typingEl.hidden = false;
    this.scrollToBottom();
  }

  /** Masque l'indicateur. */
  hideTyping() {
    this.typingEl.hidden = true;
  }

  /** Scrolle en bas du conteneur de messages. */
  scrollToBottom() {
    const container = this.messagesEl.closest('.chat-container');
    if (container) {
      requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
      });
    }
  }

  /** Vide le chat et affiche l'écran de bienvenue. */
  clear() {
    this.messagesEl.innerHTML = '';
    this._msgCount = 0;
    if (this.welcomeEl) this.welcomeEl.hidden = false;
    this.hideTyping();
  }

  /** Retourne true si au moins un message a été posté. */
  hasMessages() {
    return this._msgCount > 0;
  }

  // ─── Privé ────────────────────────────────────────────────────────────────

  _hideWelcome() {
    if (this.welcomeEl) this.welcomeEl.hidden = true;
  }

  _append(el) {
    this.messagesEl.appendChild(el);
    this.scrollToBottom();
  }

  _createElement(tag, className) {
    const el = document.createElement(tag);
    el.className = className;
    return el;
  }

  /** Génère le HTML des cartes sources. */
  _renderSources(sources) {
    const cards = sources.map((s, i) => {
      const meta   = CATEGORY_META[s.categorie] || { label: s.categorie, color: '#6B7280', bg: '#F9FAFB', emoji: '📄' };
      const score  = Math.round(s.score * 100);
      const nom    = s.fichier.replace(/\.[^.]+$/, '').replace(/_/g, ' ');
      const page   = typeof s.page === 'number' ? `p. ${s.page}` : s.page;
      const extrait = this._escapeHtml(s.extrait || '');

      return `
        <div class="source-card" style="--cat-color:${meta.color}; --cat-bg:${meta.bg}">
          <div class="source-card__header">
            <span class="source-card__index">${i + 1}</span>
            <div class="source-card__meta">
              <span class="source-card__name" title="${this._escapeHtml(s.fichier)}">${this._escapeHtml(nom)}</span>
              <div class="source-card__tags">
                <span class="source-card__badge">${meta.emoji} ${meta.label}</span>
                <span class="source-card__page">📄 ${page}</span>
                <span class="source-card__score" title="Score de pertinence">
                  <span class="source-card__score-bar" style="width:${score}%"></span>
                  ${score}%
                </span>
              </div>
            </div>
          </div>
          ${extrait ? `
          <button class="source-card__toggle">Voir l'extrait ▼</button>
          <div class="source-card__excerpt">
            <blockquote>${extrait}</blockquote>
          </div>` : ''}
        </div>`;
    }).join('');

    return `
      <div class="sources">
        <span class="sources__label">📎 Sources (${sources.length})</span>
        <div class="sources__list">${cards}</div>
      </div>`;
  }

  /** Convertit le Markdown basique en HTML sécurisé. */
  _renderMarkdown(text) {
    let html = this._escapeHtml(text);
    // Bold et italic
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g,     '<em>$1</em>');
    // Code inline
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    // Listes à puces
    html = html.replace(/^[-•]\s+(.+)$/gm, '<li>$1</li>');
    html = html.replace(/((<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');
    // Paragraphes
    html = html.replace(/\n{2,}/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');
    return `<p>${html}</p>`;
  }

  /** Échappe les caractères HTML pour éviter les injections XSS. */
  _escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
}
