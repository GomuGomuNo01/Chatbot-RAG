/**
 * i18n.js — Internationalisation FR / EN
 * Usage : i18n.t('key')  |  i18n.setLang('en')  |  i18n.applyTranslations()
 */

const TRANSLATIONS = {
  fr: {
    /* ── Méta ── */
    'page.title':        'Assistant Documentaire',

    /* ── Header ── */
    'header.title':      'Assistant Documentaire',
    'header.subtitle':   'Recherche sémantique · Sources citées',
    'btn.newchat.title': 'Nouvelle conversation (efface l\'historique)',
    'btn.newchat.aria':  'Nouvelle conversation',
    'status.connecting': 'Connexion…',

    /* ── Sidebar ── */
    'sidebar.category':  'Catégorie',
    'sidebar.docs':      'Documents indexés',
    'cat.all':           'Tout',
    'cat.technique':     'Technique',
    'cat.rh':            'Ressources Humaines',
    'cat.juridique':     'Juridique',
    'docs.loading':      'Chargement…',
    'docs.none':         'Aucun document chargé.',
    'docs.empty':        'Aucun document indexé.\nLance python ingest.py.',

    /* ── Écran de bienvenue ── */
    'welcome.title':  'Bonjour ! Comment puis-je vous aider ?',
    'welcome.desc':   'Posez vos questions sur la documentation {b1}technique{/b1}, les ressources {b2}RH{/b2} ou les documents {b3}juridiques{/b3}. Je citerai toujours mes sources.',
    'welcome.q1':     '👥 Congés payés',
    'welcome.q2':     '⚙️ Configurer Spring Boot',
    'welcome.q3':     '⚖️ Clauses CDI',
    'welcome.q1_val': 'Quelles sont les règles sur les congés payés ?',
    'welcome.q2_val': 'Comment configurer Spring Boot ?',
    'welcome.q3_val': 'Quelles sont les clauses essentielles d\'un contrat CDI ?',

    /* ── Saisie ── */
    'input.placeholder':  'Posez votre question…',
    'input.aria':         'Votre question',
    'input.disclaimer':   'L\'assistant peut faire des erreurs. Vérifiez toujours les sources.',
    'btn.send.aria':      'Envoyer',

    /* ── Badge catégorie ── */
    'badge.technique': '⚙️ Technique',
    'badge.rh':        '👥 RH',
    'badge.juridique': '⚖️ Juridique',

    /* ── Sources ── */
    'sources.title': 'Sources ({n})',
    'sources.show':  'Voir l\'extrait',
    'sources.hide':  'Masquer l\'extrait',

    /* ── Erreurs / Notices ── */
    'notice.noindex':  '⚠️ Index FAISS non trouvé. Lance <code>python ingest.py</code> pour indexer les documents.',
    'notice.offline':  '❌ Impossible de joindre le serveur. Vérifiez qu\'uvicorn est démarré.',
    'status.noindex':  'Index manquant',
    'status.offline':  'Hors ligne',
    'error.generic':   '⚠️ {msg}',

    /* ── CATEGORY_META (chat.js) ── */
    'meta.technique.label': 'Technique',
    'meta.rh.label':        'RH',
    'meta.juridique.label': 'Juridique',

    /* ── Upload ── */
    'upload.btn':         'Ajouter des documents',
    'upload.title':       'Ajouter des documents',
    'upload.step1':       '1. Choisir une catégorie',
    'upload.step2':       '2. Sélectionner les fichiers',
    'upload.drop.title':  'Glissez vos fichiers ici',
    'upload.drop.hint':   'PDF, DOCX, TXT · 50 Mo max par fichier',
    'upload.browse':      'Parcourir',
    'upload.submit':      'Indexer maintenant',
    'upload.cancel':      'Annuler',
    'upload.indexing':    'Indexation en cours…',
    'upload.success':     '✅ {n} fichier(s) indexé(s) avec succès.',
    'upload.partial':     '⚠️ {ok} indexé(s), {err} erreur(s).',
    'upload.err.nofiles': 'Sélectionnez au moins un fichier.',
    'upload.err.nocat':   'Choisissez une catégorie.',

    /* ── Nouvelle catégorie ── */
    'newcat.option':  '＋ Nouvelle catégorie',
    'newcat.title':   'Créer une catégorie',
    'newcat.key':     'Identifiant (ex: marketing)',
    'newcat.key.hint':'Minuscules, chiffres, tirets uniquement',
    'newcat.label':   'Nom affiché',
    'newcat.emoji':   'Choisir un emoji',
    'newcat.color':   'Couleur',
    'newcat.create':  'Créer',
    'newcat.cancel':  'Retour',
    'newcat.success': '✅ Catégorie « {label} » créée.',

    /* ── Re-indexation ── */
    'reindex.btn':      '🔄 Relancer l\'indexation',
    'reindex.running':  'Indexation en cours…',
    'reindex.success':  '✅ Index recréé : {chunks} chunks depuis {files} fichier(s).',
    'reindex.error':    '⚠️ Erreur d\'indexation.',
    'reindex.confirm':  'Relancer une indexation complète de tous les documents présents ?',

    /* ── Sidebar bouton upload ── */
    'sidebar.upload': 'Ajouter des documents',
  },

  en: {
    /* ── Méta ── */
    'page.title':        'Document Assistant',

    /* ── Header ── */
    'header.title':      'Document Assistant',
    'header.subtitle':   'Semantic search · Cited sources',
    'btn.newchat.title': 'New conversation (clears history)',
    'btn.newchat.aria':  'New conversation',
    'status.connecting': 'Connecting…',

    /* ── Sidebar ── */
    'sidebar.category':  'Category',
    'sidebar.docs':      'Indexed documents',
    'cat.all':           'All',
    'cat.technique':     'Technical',
    'cat.rh':            'Human Resources',
    'cat.juridique':     'Legal',
    'docs.loading':      'Loading…',
    'docs.none':         'No documents loaded.',
    'docs.empty':        'No documents indexed.\nRun python ingest.py.',

    /* ── Écran de bienvenue ── */
    'welcome.title':  'Hello! How can I help you?',
    'welcome.desc':   'Ask questions about {b1}technical{/b1} documentation, {b2}HR{/b2} resources or {b3}legal{/b3} documents. I will always cite my sources.',
    'welcome.q1':     '👥 Paid leave',
    'welcome.q2':     '⚙️ Configure Spring Boot',
    'welcome.q3':     '⚖️ Employment contract',
    'welcome.q1_val': 'What are the rules on paid leave?',
    'welcome.q2_val': 'How to configure Spring Boot?',
    'welcome.q3_val': 'What are the essential clauses of an employment contract?',

    /* ── Saisie ── */
    'input.placeholder':  'Ask your question…',
    'input.aria':         'Your question',
    'input.disclaimer':   'The assistant may make mistakes. Always verify sources.',
    'btn.send.aria':      'Send',

    /* ── Badge catégorie ── */
    'badge.technique': '⚙️ Technical',
    'badge.rh':        '👥 HR',
    'badge.juridique': '⚖️ Legal',

    /* ── Sources ── */
    'sources.title': 'Sources ({n})',
    'sources.show':  'Show excerpt',
    'sources.hide':  'Hide excerpt',

    /* ── Erreurs / Notices ── */
    'notice.noindex':  '⚠️ FAISS index not found. Run <code>python ingest.py</code> to index documents.',
    'notice.offline':  '❌ Cannot reach the server. Make sure uvicorn is running.',
    'status.noindex':  'Index missing',
    'status.offline':  'Offline',
    'error.generic':   '⚠️ {msg}',

    /* ── CATEGORY_META (chat.js) ── */
    'meta.technique.label': 'Technical',
    'meta.rh.label':        'HR',
    'meta.juridique.label': 'Legal',

    /* ── Upload ── */
    'upload.btn':         'Add documents',
    'upload.title':       'Add documents',
    'upload.step1':       '1. Choose a category',
    'upload.step2':       '2. Select files',
    'upload.drop.title':  'Drop your files here',
    'upload.drop.hint':   'PDF, DOCX, TXT · 50 MB max per file',
    'upload.browse':      'Browse',
    'upload.submit':      'Index now',
    'upload.cancel':      'Cancel',
    'upload.indexing':    'Indexing…',
    'upload.success':     '✅ {n} file(s) indexed successfully.',
    'upload.partial':     '⚠️ {ok} indexed, {err} error(s).',
    'upload.err.nofiles': 'Please select at least one file.',
    'upload.err.nocat':   'Please choose a category.',

    /* ── Nouvelle catégorie ── */
    'newcat.option':  '＋ New category',
    'newcat.title':   'Create a category',
    'newcat.key':     'Identifier (e.g. marketing)',
    'newcat.key.hint':'Lowercase, digits, hyphens only',
    'newcat.label':   'Display name',
    'newcat.emoji':   'Choose an emoji',
    'newcat.color':   'Color',
    'newcat.create':  'Create',
    'newcat.cancel':  'Back',
    'newcat.success': '✅ Category « {label} » created.',

    /* ── Re-indexation ── */
    'reindex.btn':      '🔄 Re-run indexation',
    'reindex.running':  'Indexing…',
    'reindex.success':  '✅ Index rebuilt: {chunks} chunks from {files} file(s).',
    'reindex.error':    '⚠️ Indexation error.',
    'reindex.confirm':  'Re-run full indexation of all documents?',

    /* ── Sidebar bouton upload ── */
    'sidebar.upload': 'Add documents',
  },
};

/* ─────────────────────────────────────────────────────────── */

const i18n = {
  lang: localStorage.getItem('docassist_lang') || 'fr',

  /** Retourne la traduction pour une clé, avec variables optionnelles. */
  t(key, vars = {}) {
    const str = (TRANSLATIONS[this.lang] || {})[key]
             || (TRANSLATIONS['fr']       || {})[key]
             || key;
    return str.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? `{${k}}`);
  },

  /** Change la langue et met à jour l'UI. */
  setLang(lang) {
    if (!TRANSLATIONS[lang]) return;
    this.lang = lang;
    localStorage.setItem('docassist_lang', lang);
    document.documentElement.lang = lang;
    this.applyTranslations();
  },

  /** Met à jour tous les éléments marqués data-i18n-*. */
  applyTranslations() {
    // Contenu texte
    document.querySelectorAll('[data-i18n]').forEach(el => {
      el.textContent = this.t(el.dataset.i18n);
    });
    // Placeholder
    document.querySelectorAll('[data-i18n-ph]').forEach(el => {
      el.placeholder = this.t(el.dataset.i18nPh);
    });
    // aria-label
    document.querySelectorAll('[data-i18n-aria]').forEach(el => {
      el.setAttribute('aria-label', this.t(el.dataset.i18nAria));
    });
    // title
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      el.title = this.t(el.dataset.i18nTitle);
    });
    // data-question sur les boutons exemples
    const qKeys = ['welcome.q1_val', 'welcome.q2_val', 'welcome.q3_val'];
    document.querySelectorAll('.example-btn[data-i18n-q]').forEach((btn, i) => {
      btn.dataset.question = this.t(qKeys[i] || btn.dataset.i18nQ);
    });
    // Titre de la page
    document.title = this.t('page.title');
    // Boutons langue : marquer l'actif
    document.querySelectorAll('.lang-btn').forEach(btn => {
      btn.classList.toggle('lang-btn--active', btn.dataset.lang === this.lang);
    });
  },
};
