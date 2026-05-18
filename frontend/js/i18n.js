/**
 * i18n.js — Internationalisation FR / EN (refonte v2)
 * Plus aucune clé spécifique à technique/rh/juridique.
 */

const TRANSLATIONS = {
  fr: {
    /* ── Méta ── */
    'page.title':        'DocAssist',

    /* ── Header ── */
    'header.title':      'DocAssist',
    'header.subtitle':   'Recherche hybride · Sources citées',
    'btn.newchat.title': 'Nouvelle conversation (efface l\'historique)',
    'btn.newchat.aria':  'Nouvelle conversation',
    'btn.menu':          'Ouvrir le menu',
    'status.connecting': 'Connexion…',

    /* ── Sidebar ── */
    'sidebar.workspaces': 'Workspaces',
    'sidebar.docs':       'Documents indexés',
    'sidebar.upload':     'Ajouter des documents',
    'ws.all':             'Tout',
    'ws.none':            'Aucun workspace — créez-en un pour commencer.',
    'docs.loading':       'Chargement…',
    'docs.none':          'Aucun document indexé pour l\'instant.',

    /* ── Bienvenue ── */
    'welcome.title':  'Bonjour ! Que puis-je vous aider à explorer ?',
    'welcome.desc':   'Importez vos documents, organisez-les par workspaces et posez vos questions. Je citerai toujours mes sources.',

    /* ── Saisie ── */
    'input.placeholder':  'Posez votre question…',
    'input.aria':         'Votre question',
    'input.disclaimer':   'L\'assistant peut faire des erreurs. Vérifiez toujours les sources.',
    'btn.send.aria':      'Envoyer',

    /* ── Sources ── */
    'sources.title': 'Sources ({n})',
    'sources.show':  'Voir l\'extrait',
    'sources.hide':  'Masquer l\'extrait',

    /* ── Erreurs / Notices ── */
    'notice.noindex':  '⚠️ Aucun index documentaire pour l\'instant. Importez des documents pour commencer.',
    'notice.offline':  '❌ Impossible de joindre le serveur. Vérifiez qu\'uvicorn est démarré.',
    'status.noindex':  'Index manquant',
    'status.offline':  'Hors ligne',

    /* ── Upload ── */
    'upload.title':       'Ajouter des documents',
    'upload.step1':       '1. Choisir un workspace',
    'upload.step2':       '2. Sélectionner les fichiers',
    'upload.drop.title':  'Glissez vos fichiers ici',
    'upload.drop.hint':   'PDF, DOCX, TXT, MD · 50 Mo max par fichier',
    'upload.browse':      'Parcourir',
    'upload.submit':      'Indexer maintenant',
    'upload.cancel':      'Annuler',
    'upload.sending':     'Envoi des fichiers…',
    'upload.indexing':    'Indexation en cours…',
    'upload.success':     '✅ {n} fichier(s) indexé(s) avec succès.',
    'upload.partial':     '⚠️ {ok} indexé(s), {err} erreur(s).',
    'upload.bg.error':    'Erreur lors de l\'indexation :',
    'upload.err.nofiles': 'Sélectionnez au moins un fichier.',
    'upload.err.nows':    'Choisissez un workspace.',
    'upload.file.toobig': '⚠️ « {name} » ({size}) dépasse la limite de 50 Mo.',

    /* ── Nouveau workspace ── */
    'newws.option':  '＋ Nouveau workspace',
    'newws.title':   'Créer un workspace',
    'newws.key':     'Identifiant',
    'newws.key.hint':'Minuscules, chiffres, tirets, underscores (commence par lettre/chiffre)',
    'newws.label':   'Nom affiché',
    'newws.emoji':   'Choisir un emoji',
    'newws.color':   'Couleur',
    'newws.create':  'Créer',
    'newws.cancel':  'Retour',
    'newws.success': '✅ Workspace « {label} » créé.',

    /* ── Re-indexation ── */
    'reindex.btn':      '🔄 Relancer l\'indexation',
    'reindex.running':  'Indexation en cours…',
    'reindex.success':  '✅ Index recréé : {chunks} chunks depuis {files} fichier(s).',
    'reindex.error':    '⚠️ Erreur d\'indexation.',

    /* ── Suppression document ── */
    'delete.doc.confirm':  'Supprimer « {name} » ? Cette action est irréversible.',
    'delete.doc.pending':  '🗑️ « {name} » supprimé. Reconstruction de l\'index…',
    'delete.doc.success':  '✅ « {name} » supprimé. Index reconstruit.',
    'delete.doc.error':    '⚠️ Erreur lors de la suppression.',

    /* ── Suppression workspace ── */
    'delete.ws.confirm':  'Supprimer le workspace « {label} » et tous ses documents ? Action irréversible.',
    'delete.ws.pending':  '🗑️ Workspace « {label} » supprimé ({n} doc.). Reconstruction de l\'index…',
    'delete.ws.success':  '✅ Workspace « {label} » supprimé ({n} document(s)). Index reconstruit.',
    'delete.ws.error':    '⚠️ Erreur lors de la suppression du workspace.',

    /* ── Ré-indexation d'un fichier ── */
    'reindex.file.success': '✅ « {name} » ré-indexé.',
    'reindex.file.error':   '⚠️ Erreur de ré-indexation.',
  },

  en: {
    /* ── Meta ── */
    'page.title':        'DocAssist',

    /* ── Header ── */
    'header.title':      'DocAssist',
    'header.subtitle':   'Hybrid search · Cited sources',
    'btn.newchat.title': 'New conversation (clears history)',
    'btn.newchat.aria':  'New conversation',
    'btn.menu':          'Open menu',
    'status.connecting': 'Connecting…',

    /* ── Sidebar ── */
    'sidebar.workspaces': 'Workspaces',
    'sidebar.docs':       'Indexed documents',
    'sidebar.upload':     'Add documents',
    'ws.all':             'All',
    'ws.none':            'No workspaces — create one to get started.',
    'docs.loading':       'Loading…',
    'docs.none':          'No documents indexed yet.',

    /* ── Welcome ── */
    'welcome.title':  'Hello! What would you like to explore?',
    'welcome.desc':   'Import your documents, organize them into workspaces, and ask your questions. I will always cite my sources.',

    /* ── Input ── */
    'input.placeholder':  'Ask your question…',
    'input.aria':         'Your question',
    'input.disclaimer':   'The assistant may make mistakes. Always verify sources.',
    'btn.send.aria':      'Send',

    /* ── Sources ── */
    'sources.title': 'Sources ({n})',
    'sources.show':  'Show excerpt',
    'sources.hide':  'Hide excerpt',

    /* ── Errors / Notices ── */
    'notice.noindex':  '⚠️ No documents indexed yet. Upload some to get started.',
    'notice.offline':  '❌ Cannot reach the server. Make sure uvicorn is running.',
    'status.noindex':  'Index missing',
    'status.offline':  'Offline',

    /* ── Upload ── */
    'upload.title':       'Add documents',
    'upload.step1':       '1. Choose a workspace',
    'upload.step2':       '2. Select files',
    'upload.drop.title':  'Drop your files here',
    'upload.drop.hint':   'PDF, DOCX, TXT, MD · 50 MB max per file',
    'upload.browse':      'Browse',
    'upload.submit':      'Index now',
    'upload.cancel':      'Cancel',
    'upload.sending':     'Uploading files…',
    'upload.indexing':    'Indexing…',
    'upload.success':     '✅ {n} file(s) indexed successfully.',
    'upload.partial':     '⚠️ {ok} indexed, {err} error(s).',
    'upload.bg.error':    'Indexation error:',
    'upload.err.nofiles': 'Please select at least one file.',
    'upload.err.nows':    'Please choose a workspace.',
    'upload.file.toobig': '⚠️ « {name} » ({size}) exceeds the 50 MB limit.',

    /* ── New workspace ── */
    'newws.option':  '＋ New workspace',
    'newws.title':   'Create a workspace',
    'newws.key':     'Identifier',
    'newws.key.hint':'Lowercase, digits, hyphens, underscores (must start with letter/digit)',
    'newws.label':   'Display name',
    'newws.emoji':   'Choose an emoji',
    'newws.color':   'Color',
    'newws.create':  'Create',
    'newws.cancel':  'Back',
    'newws.success': '✅ Workspace « {label} » created.',

    /* ── Re-indexation ── */
    'reindex.btn':      '🔄 Re-run indexation',
    'reindex.running':  'Indexing…',
    'reindex.success':  '✅ Index rebuilt: {chunks} chunks from {files} file(s).',
    'reindex.error':    '⚠️ Indexation error.',

    /* ── Delete document ── */
    'delete.doc.confirm':  'Delete « {name} »? This action is irreversible.',
    'delete.doc.pending':  '🗑️ « {name} » deleted. Rebuilding index…',
    'delete.doc.success':  '✅ « {name} » deleted. Index rebuilt.',
    'delete.doc.error':    '⚠️ Error while deleting.',

    /* ── Delete workspace ── */
    'delete.ws.confirm':  'Delete workspace « {label} » and all its documents? Irreversible action.',
    'delete.ws.pending':  '🗑️ Workspace « {label} » deleted ({n} doc.). Rebuilding index…',
    'delete.ws.success':  '✅ Workspace « {label} » deleted ({n} document(s)). Index rebuilt.',
    'delete.ws.error':    '⚠️ Error while deleting workspace.',

    /* ── Reindex single file ── */
    'reindex.file.success': '✅ « {name} » re-indexed.',
    'reindex.file.error':   '⚠️ Re-indexation error.',
  },
};

const i18n = {
  lang: localStorage.getItem('docassist_lang') || 'fr',

  t(key, vars = {}) {
    const str = (TRANSLATIONS[this.lang] || {})[key]
             || (TRANSLATIONS['fr']       || {})[key]
             || key;
    return str.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? `{${k}}`);
  },

  setLang(lang) {
    if (!TRANSLATIONS[lang]) return;
    this.lang = lang;
    localStorage.setItem('docassist_lang', lang);
    document.documentElement.lang = lang;
    this.applyTranslations();
  },

  applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      el.textContent = this.t(el.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-ph]').forEach(el => {
      el.placeholder = this.t(el.dataset.i18nPh);
    });
    document.querySelectorAll('[data-i18n-aria]').forEach(el => {
      el.setAttribute('aria-label', this.t(el.dataset.i18nAria));
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      el.title = this.t(el.dataset.i18nTitle);
    });
    document.title = this.t('page.title');
    document.querySelectorAll('.lang-btn').forEach(btn => {
      btn.classList.toggle('lang-btn--active', btn.dataset.lang === this.lang);
    });
  },
};
