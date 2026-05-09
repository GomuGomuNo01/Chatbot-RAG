"""
query_processor.py — Amélioration sémantique des requêtes avant retrieval

Deux couches complémentaires :

1. expand_acronyms()      — Expansion instantanée des abréviations françaises
                            (CDI → CDI contrat à durée indéterminée)
                            Aucun appel LLM, latence nulle.

2. contextualize_query()  — Réécriture contextuelle via LLM (léger, ~100 tokens)
                            Activée uniquement si l'historique n'est pas vide
                            ET si la question contient des marqueurs anaphoriques
                            (pronoms, références implicites, question très courte).
                            Résout : "Quelles sont ses conditions ?" →
                                     "Quelles sont les conditions du CDI ?"
"""

import logging
import re

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Dictionnaire d'acronymes FR/EN → forme longue
# ──────────────────────────────────────────────────────────────

ACRONYMS: dict[str, str] = {
    # ── Ressources Humaines / Droit du travail ────────────────
    "CDI": "contrat à durée indéterminée",
    "CDD": "contrat à durée déterminée",
    "CTT": "contrat de travail temporaire",
    "CDDI": "contrat à durée déterminée d'insertion",
    "SMIC": "salaire minimum interprofessionnel de croissance",
    "RH": "ressources humaines",
    "DRH": "directeur des ressources humaines",
    "RTT": "réduction du temps de travail",
    "CP": "congés payés",
    "AT": "accident du travail",
    "MP": "maladie professionnelle",
    "IRP": "institutions représentatives du personnel",
    "CE": "comité d'entreprise",
    "CSE": "comité social et économique",
    "DP": "délégué du personnel",
    "DS": "délégué syndical",
    "PSE": "plan de sauvegarde de l'emploi",
    "PEE": "plan d'épargne entreprise",
    "PERCO": "plan d'épargne pour la retraite collectif",
    "IJSS": "indemnités journalières de sécurité sociale",
    "ARE": "allocation de retour à l'emploi",
    "AREF": "allocation de retour à l'emploi formation",
    "ASS": "allocation de solidarité spécifique",
    "RSA": "revenu de solidarité active",
    "PASS": "plafond annuel de la sécurité sociale",
    "URSSAF": "union de recouvrement des cotisations de sécurité sociale et d'allocations familiales",
    "CPAM": "caisse primaire d'assurance maladie",
    "CARSAT": "caisse d'assurance retraite et de la santé au travail",
    "OPCO": "opérateur de compétences",
    "VAE": "validation des acquis de l'expérience",
    "CPF": "compte personnel de formation",
    "CIF": "congé individuel de formation",
    "DIF": "droit individuel à la formation",
    "GPEC": "gestion prévisionnelle des emplois et des compétences",
    # ── Juridique / Légal ─────────────────────────────────────
    "TVA": "taxe sur la valeur ajoutée",
    "CA": "chiffre d'affaires",
    "SAS": "société par actions simplifiée",
    "SASU": "société par actions simplifiée unipersonnelle",
    "SARL": "société à responsabilité limitée",
    "EURL": "entreprise unipersonnelle à responsabilité limitée",
    "SA": "société anonyme",
    "SCI": "société civile immobilière",
    "SNC": "société en nom collectif",
    "CGI": "code général des impôts",
    "CC": "code civil",
    "CT": "code du travail",
    "CPP": "code de procédure pénale",
    "CPC": "code de procédure civile",
    "CPH": "conseil de prud'hommes",
    "CNIL": "commission nationale de l'informatique et des libertés",
    "RGPD": "règlement général sur la protection des données",
    "GDPR": "general data protection regulation",
    "CGV": "conditions générales de vente",
    "CGU": "conditions générales d'utilisation",
    "NDA": "accord de confidentialité",
    "SLA": "accord de niveau de service",
    # ── Technique / Informatique ──────────────────────────────
    "API": "interface de programmation applicative",
    "BDD": "base de données",
    "SQL": "structured query language",
    "ORM": "object-relational mapping",
    "CI": "intégration continue",
    "CD": "déploiement continu",
    "POC": "preuve de concept",
    "MVP": "produit minimum viable",
    "UI": "interface utilisateur",
    "UX": "expérience utilisateur",
    "REST": "representational state transfer",
    "HTTP": "hypertext transfer protocol",
    "HTTPS": "hypertext transfer protocol sécurisé",
    "SSH": "secure shell",
    "TLS": "transport layer security",
    "SSL": "secure sockets layer",
    "JWT": "json web token",
    "CRUD": "create read update delete",
    "MVC": "model view controller",
    "OOP": "programmation orientée objet",
    "POO": "programmation orientée objet",
    "IAM": "identity and access management",
    "SSO": "single sign-on",
    "MFA": "authentification multi-facteurs",
    "DNS": "domain name system",
    "VPN": "réseau privé virtuel",
    "VM": "machine virtuelle",
    "K8S": "kubernetes",
    "IaC": "infrastructure as code",
    "SRE": "site reliability engineering",
    # ── Web / JavaScript ──────────────────────────────────────
    "DOM": "document object model",
    "JS": "javascript",
    "TS": "typescript",
    "HTML": "hypertext markup language",
    "CSS": "cascading style sheets",
    "AJAX": "asynchronous javascript and xml",
    "SPA": "single page application",
    "PWA": "progressive web application",
    "CSR": "client-side rendering",
    "SSR": "server-side rendering",
    "JSX": "javascript xml",
    "ESM": "ecmascript module",
    "CJS": "commonjs module",
    "BOM": "browser object model",
    # ── Java / Spring Boot ────────────────────────────────────
    "JVM": "java virtual machine",
    "JDK": "java development kit",
    "JRE": "java runtime environment",
    "JPA": "java persistence api",
    "JDBC": "java database connectivity",
    "JMS": "java message service",
    "JNDI": "java naming and directory interface",
    "JAR": "java archive",
    "WAR": "web application archive",
    "IoC": "inversion of control",
    "DI": "dependency injection",
    "AOP": "aspect oriented programming",
    "POJO": "plain old java object",
    "DTO": "data transfer object",
    "DAO": "data access object",
    "AMQP": "advanced message queuing protocol",
    "AOT": "ahead of time compilation",
    "GraalVM": "graal virtual machine",
    # ── Architecture / Patterns ───────────────────────────────
    "BFF": "backend for frontend",
    "CQRS": "command query responsibility segregation",
    "DDD": "domain driven design",
    "TDD": "test driven development",
    "SOLID": "single responsibility open closed liskov substitution interface segregation dependency inversion",
    # ── Données / Bases ───────────────────────────────────────
    "JSON": "javascript object notation",
    "XML": "extensible markup language",
    "YAML": "yaml ain't markup language",
    "TOML": "tom's obvious minimal language",
    "CSV": "comma separated values",
    "NoSQL": "not only sql",
    "RDBMS": "relational database management system",
}

# Marqueurs anaphoriques signalant une question dépendante du contexte
_ANAPHORA = re.compile(
    r"\b(il|elle|ils|elles|son|sa|ses|leur|leurs|"
    r"ce|cet|cette|ces|celui|celle|ceux|celles|"
    r"y|en|ça|cela|ceci|lequel|laquelle|lesquels|lesquelles|"
    r"dont|duquel|de laquelle|"
    r"le même|la même|les mêmes|"
    # Références duales / plurielles implicites
    r"les deux|tous les deux|toutes les deux|"
    r"l'un et l'autre|l'une et l'autre|"
    r"l'un de l'autre|l'une de l'autre|"
    r"entre eux|entre elles|entre les deux|"
    r"chacun|chacune|l'un|l'une|l'autre)\b",
    re.IGNORECASE,
)

# ──────────────────────────────────────────────────────────────
# Patterns de questions comparatives
# ──────────────────────────────────────────────────────────────

# Détecte "différence entre X et Y", "comparer X et Y", "X vs Y", etc.
_COMPARATIVE_RE: list[re.Pattern] = [
    # "la différence entre X et Y", "quelles différences entre X et Y"
    re.compile(
        r"\bdiff[eé]rence[s]?\s+entre\s+(.+?)\s+et\s+(.+?)(?=\s*\?|$)",
        re.IGNORECASE,
    ),
    # "comparer X et Y", "comparaison entre X et Y"
    re.compile(
        r"\bcompar(?:er|aison|ez)\s+(?:entre\s+)?(.+?)\s+et\s+(.+?)(?=\s*\?|$)",
        re.IGNORECASE,
    ),
    # "X versus Y", "X vs Y"
    re.compile(
        r"\b(.+?)\s+(?:versus|vs\.?)\s+(.+?)(?=\s*\?|$)",
        re.IGNORECASE,
    ),
    # "distinguer X de Y", "distinction entre X et Y"
    re.compile(
        r"\bdistin(?:guer|ction)\s+(?:entre\s+|de\s+)?(.+?)\s+(?:et|de)\s+(.+?)(?=\s*\?|$)",
        re.IGNORECASE,
    ),
    # "qu'est-ce qui différencie X de Y"
    re.compile(
        r"\bdiff[eé]renci(?:e|er|ent)\s+(.+?)\s+(?:de|et)\s+(.+?)(?=\s*\?|$)",
        re.IGNORECASE,
    ),
]

# Prompt ultra-compact pour la réécriture contextuelle
_REWRITE_PROMPT = """\
Tu es un assistant de reformulation. Réécris la question de l'utilisateur \
pour qu'elle soit autonome et précise, en tenant compte du contexte ci-dessous.
Ne donne QUE la question reformulée, sans explication ni ponctuation finale.

Contexte (derniers échanges) :
{context}

Question originale : {question}
Question reformulée :"""


# ──────────────────────────────────────────────────────────────
# Couche 1 : expansion des acronymes
# ──────────────────────────────────────────────────────────────


def expand_acronyms(text: str) -> str:
    """
    Remplace les acronymes connus par « ACRONYME (forme longue) ».
    Travaille sur les mots entiers uniquement (pas dans une sous-chaîne).

    Supporte :
    - Acronymes tout majuscules  : CDI, JPA, REST, DOM
    - Acronymes mixed-case connus : IoC, GraalVM, NoSQL
    - Acronymes avec chiffres    : K8S, HTML5

    Exemple :
        "c'est quoi un CDI ?"        → "c'est quoi un CDI (contrat à durée indéterminée) ?"
        "configurer IoC avec Spring"  → "configurer IoC (inversion of control) avec Spring"
    """

    def _replace(match: re.Match) -> str:
        token = match.group(0)
        # Cherche d'abord le token exact (pour les mixed-case comme IoC, NoSQL)
        # puis sa version uppercase (pour les acronymes standards)
        key = token if token in ACRONYMS else token.upper()
        if key in ACRONYMS:
            expanded = f"{token} ({ACRONYMS[key]})"
            logger.debug(f"Acronyme étendu : {token} → {expanded}")
            return expanded
        return token

    # Pattern élargi : majuscule suivie de lettres/chiffres (2-9 chars total)
    # Capture : CDI, JPA, REST, DOM, IoC, GraalVM, NoSQL, K8S, HTML5
    return re.sub(r"\b[A-Z][A-Za-z0-9]{1,8}\b", _replace, text)


# ──────────────────────────────────────────────────────────────
# Couche 2 : réécriture contextuelle via LLM
# ──────────────────────────────────────────────────────────────


def _needs_contextualization(question: str, has_history: bool) -> bool:
    """
    Détermine si la question nécessite une réécriture contextuelle.
    Critères : présence de pronoms anaphoriques OU question très courte.
    """
    if not has_history:
        return False
    q = question.strip()
    word_count = len(q.split())
    has_anaphora = bool(_ANAPHORA.search(q))
    is_short = word_count <= 5  # "Quelles sont ses conditions ?"
    return has_anaphora or is_short


def contextualize_query(
    question: str,
    history_text: str,
    llm,
    *,
    max_history_chars: int = 600,
) -> str:
    """
    Réécrit la question pour la rendre autonome en utilisant l'historique.
    Retourne la question originale si aucune réécriture n'est nécessaire.

    Args:
        question          : question brute de l'utilisateur
        history_text      : historique formaté (résultat de memory.format_compact())
        llm               : instance ChatGroq
        max_history_chars : troncature de l'historique injecté dans le prompt

    Returns:
        Question enrichie du contexte, ou question originale.
    """
    has_history = bool(history_text and history_text.strip())
    if not _needs_contextualization(question, has_history):
        return question

    context_snippet = history_text[-max_history_chars:] if has_history else ""

    try:
        from langchain_core.messages import HumanMessage

        prompt_text = _REWRITE_PROMPT.format(
            context=context_snippet,
            question=question,
        )
        result = llm.invoke([HumanMessage(content=prompt_text)])
        # Sécurité stricte : result.content DOIT être une str.
        # En cas contraire (MagicMock en test, type inattendu…), on abandonne
        # la réécriture et on retourne la question originale.
        if not isinstance(result.content, str):
            return question
        rewritten = result.content.strip().strip('"').strip("'")

        # Sécurité : si la réécriture est vide ou trop longue, on garde l'original
        if not rewritten or len(rewritten) > 400:
            return question

        logger.info(f"Query rewritten: «{question}» → «{rewritten}»")
        return rewritten

    except Exception as e:
        logger.warning(f"Query rewriting ignoré (non bloquant) : {e}")
        return question


async def contextualize_query_async(
    question: str,
    history_text: str,
    llm,
    *,
    max_history_chars: int = 600,
) -> str:
    """Version async de contextualize_query pour le streaming."""
    has_history = bool(history_text and history_text.strip())
    if not _needs_contextualization(question, has_history):
        return question

    context_snippet = history_text[-max_history_chars:] if has_history else ""

    try:
        from langchain_core.messages import HumanMessage

        prompt_text = _REWRITE_PROMPT.format(
            context=context_snippet,
            question=question,
        )
        result = await llm.ainvoke([HumanMessage(content=prompt_text)])
        if not isinstance(result.content, str):
            return question
        rewritten = result.content.strip().strip('"').strip("'")

        if not rewritten or len(rewritten) > 400:
            return question

        logger.info(f"[STREAM] Query rewritten: «{question}» → «{rewritten}»")
        return rewritten

    except Exception as e:
        logger.warning(f"[STREAM] Query rewriting ignoré : {e}")
        return question


# ──────────────────────────────────────────────────────────────
# Décomposition des questions comparatives
# ──────────────────────────────────────────────────────────────


def decompose_comparative_query(question: str) -> list[str]:
    """
    Détecte les questions comparatives et les décompose en sous-requêtes
    spécialisées pour maximiser le rappel FAISS.

    Principe : une question du type « différence entre CDI et CDD » nécessite
    des chunks sur CDI *et* des chunks sur CDD. Une unique requête vectorielle
    ne couvre pas forcément les deux termes. On génère donc 3 sous-requêtes :
      1. Requête ciblée sur le concept A
      2. Requête ciblée sur le concept B
      3. Requête directe sur la comparaison A/B

    Exemple :
      "Quelle est la différence entre un CDI et un CDD ?"
      → [
          "CDI (contrat à durée indéterminée) définition caractéristiques",
          "CDD (contrat à durée déterminée) définition caractéristiques",
          "différence CDI (contrat à durée indéterminée) CDD (contrat à durée déterminée)",
        ]

    Retourne une liste vide si aucun pattern comparatif n'est détecté.
    """
    # Nettoyer la question des mots interrogatifs parasites avant la détection
    cleaned = re.sub(
        r"^(quelle est|quelles sont|qu'est-ce que|comment|pourquoi|"
        r"what is|what are|how|why)\s+",
        "",
        question.strip(),
        flags=re.IGNORECASE,
    )

    for pattern in _COMPARATIVE_RE:
        m = pattern.search(cleaned)
        if m:
            x = m.group(1).strip().rstrip(".,;:")
            y = m.group(2).strip().rstrip(".,;:")

            # Ignorer si l'un des termes est trop court ou trop vague
            if len(x) < 2 or len(y) < 2:
                continue

            # Expansion des acronymes dans chaque terme
            x_exp = expand_acronyms(x)
            y_exp = expand_acronyms(y)

            sub_queries = [
                f"{x_exp} définition caractéristiques",
                f"{y_exp} définition caractéristiques",
                f"différence {x_exp} {y_exp}",
            ]
            logger.info(
                f"[decompose] Question comparative détectée : «{x}» vs «{y}» "
                f"→ {len(sub_queries)} sous-requêtes"
            )
            return sub_queries

    return []


# ──────────────────────────────────────────────────────────────
# Pipeline complet : expand + contextualize
# ──────────────────────────────────────────────────────────────


def build_search_query(
    question: str,
    history_text: str,
    llm,
) -> str:
    """
    Construit la requête optimale pour le retrieval FAISS :
    1. Expand les acronymes
    2. Contextualise si nécessaire (pronoms, question courte)

    La question ORIGINALE est conservée pour la génération LLM ;
    seule la requête de recherche est améliorée.
    """
    expanded = expand_acronyms(question)
    search_q = contextualize_query(expanded, history_text, llm)
    return search_q


async def build_search_query_async(
    question: str,
    history_text: str,
    llm,
) -> str:
    """Version async de build_search_query."""
    expanded = expand_acronyms(question)
    search_q = await contextualize_query_async(expanded, history_text, llm)
    return search_q


# ──────────────────────────────────────────────────────────────
# Détection des références à des articles de loi
# ──────────────────────────────────────────────────────────────


def _normalize_article_ref(ref: str) -> str | None:
    """
    Normalise une référence d'article vers le format stocké dans les PDFs.

    Le Code du Travail stocke les articles sans point ni espace entre la lettre
    de préfixe et les chiffres (ex : « L1111-1 » et non « L. 1111-1 »).
    Les utilisateurs utilisent souvent la notation officielle avec point.

    Exemples :
        "L. 1234-5"  → "L1234-5"   ✓ format PDF Code du Travail
        "R. 123-4"   → "R123-4"
        "D. 123-4"   → "D123-4"
        "4"          → None         (Code Civil — pas de variante)
        "111-1"      → None         (Code Pénal — pas de variante)
    """
    m = re.match(r"^([A-Z])\.\s+(\d[\d\-]*)\s*$", ref.strip())
    if m:
        return f"{m.group(1)}{m.group(2)}"
    return None


def _expand_article_range(start_ref: str, end_ref: str) -> list[str]:
    """
    Tente d'énumérer les articles d'une plage « articles X à Y ».

    N'énumère que si X et Y sont des entiers purs (sans tiret ni lettre)
    et si la plage contient au plus 10 articles. Sinon retourne les deux bornes.

    Exemples :
        "4", "7"       → ["4", "5", "6", "7"]
        "1", "50"      → ["1", "50"]  (plage trop grande)
        "L1234-5", "L1234-10" → ["L1234-5", "L1234-10"]
    """
    s, e = start_ref.strip(), end_ref.strip()
    if re.match(r"^\d+$", s) and re.match(r"^\d+$", e):
        si, ei = int(s), int(e)
        if 0 < ei - si <= 10:
            return [str(n) for n in range(si, ei + 1)]
    return [s, e]


def _article_query_forms(ref: str) -> list[str]:
    """
    Génère toutes les formes de requête FAISS pour une référence d'article.

    Produit « Article X » (forme originale) et, si applicable, « Article Y »
    (forme normalisée PDF) pour couvrir les variantes de notation.

    Exemples :
        "L. 1234-5" → ["Article L. 1234-5", "Article L1234-5"]
        "4"         → ["Article 4"]
        "111-1"     → ["Article 111-1"]
    """
    forms = [f"Article {ref}"]
    normalized = _normalize_article_ref(ref)
    if normalized:
        nq = f"Article {normalized}"
        if nq not in forms:
            forms.append(nq)
    return forms


# Détecte "articles X à Y" ou "articles X au Y" (plages d'articles)
_ARTICLE_RANGE_RE = re.compile(
    r"\barticles?\s+([A-Z]*\.?\s*\d+(?:[–\-]\d+)*)\s+(?:à|au)\s+([A-Z]*\.?\s*\d+(?:[–\-]\d+)*)",
    re.IGNORECASE,
)

# "article 4", "l'article L. 1234-5", "articles R. 123-4", etc.
_ARTICLE_NUM_RE = re.compile(
    r"\barticles?\s+([A-Z]*\.?\s*\d+(?:[–\-]\d+)*)",
    re.IGNORECASE,
)
# "et l'article N" / "à l'article N" après une première mention
_ARTICLE_AND_RE = re.compile(
    r"(?:et|à|ou)\s+(?:l[aes']?\s+)?articles?\s+([A-Z]*\.?\s*\d+(?:[–\-]\d+)*)",
    re.IGNORECASE,
)


def extract_article_queries(question: str) -> list[str]:
    """
    Détecte les références à des articles de loi dans la question et génère
    des requêtes ciblées à ajouter au multi-retrieval.

    Améliorations :
    • Gère les plages : « articles 4 à 7 » → requêtes pour 4, 5, 6, 7
    • Normalise le format Code du Travail : « L. 1234-5 » génère aussi
      « Article L1234-5 » (le PDF stocke sans point ni espace)
    • Déduplique les références identiques

    Exemples :
        "que dit l'article 4 du code civil"
            → ["Article 4"]
        "article L. 1234-5 du code du travail"
            → ["Article L. 1234-5", "Article L1234-5"]
        "les articles 1 à 3 du code civil"
            → ["Article 1", "Article 2", "Article 3"]
        "articles R. 123-1 et R. 123-2"
            → ["Article R. 123-1", "Article R123-1",
               "Article R. 123-2", "Article R123-2"]

    Retourne une liste vide si aucune référence légale n'est trouvée.
    """
    raw_refs: list[str] = []

    # ── Plages : "articles X à Y" ──────────────────────────────
    for m in _ARTICLE_RANGE_RE.finditer(question):
        raw_refs.extend(_expand_article_range(m.group(1).strip(), m.group(2).strip()))

    # ── Références individuelles ────────────────────────────────
    for m in _ARTICLE_NUM_RE.finditer(question):
        raw_refs.append(m.group(1).strip())
    for m in _ARTICLE_AND_RE.finditer(question):
        raw_refs.append(m.group(1).strip())

    # ── Génération des formes de requête + déduplication ────────
    seen: set[str] = set()
    queries: list[str] = []
    for ref in raw_refs:
        for form in _article_query_forms(ref):
            if form not in seen:
                seen.add(form)
                queries.append(form)

    if queries:
        logger.info(f"[article_queries] Références légales détectées : {queries}")
    return queries


# ──────────────────────────────────────────────────────────────
# Détection des annotations Java / Spring Boot (@Annotation)
# ──────────────────────────────────────────────────────────────

# Capture @AnnotationName (éventuellement suivi de parenthèses)
_ANNOTATION_RE = re.compile(r"@([A-Z][A-Za-z0-9]+)(?:\([^)]*\))?")

# Annotations Spring Boot fréquentes : génère aussi des sous-requêtes enrichies
_SPRING_ANNOTATION_CONTEXT: dict[str, str] = {
    "SpringBootApplication": "spring boot application main class configuration",
    "RestController": "rest controller http endpoints web mvc",
    "Controller": "mvc controller web layer",
    "Service": "service layer business logic component",
    "Repository": "repository data access layer database",
    "Component": "spring component bean dependency injection",
    "Autowired": "dependency injection autowiring beans",
    "Bean": "spring bean factory configuration",
    "Configuration": "spring configuration class beans",
    "Value": "property injection configuration value",
    "ConfigurationProperties": "configuration properties binding external config",
    "EnableAutoConfiguration": "auto-configuration spring boot",
    "Transactional": "transaction management database",
    "Entity": "jpa entity database table mapping",
    "Table": "jpa table mapping database",
    "Column": "jpa column mapping database field",
    "Id": "jpa primary key entity identifier",
    "GeneratedValue": "jpa auto-generated primary key",
    "OneToMany": "jpa one to many relationship",
    "ManyToOne": "jpa many to one relationship",
    "ManyToMany": "jpa many to many relationship",
    "RequestMapping": "http request mapping url route",
    "GetMapping": "http get request handler endpoint",
    "PostMapping": "http post request handler endpoint",
    "PutMapping": "http put request handler endpoint",
    "DeleteMapping": "http delete request handler endpoint",
    "PathVariable": "url path variable rest api",
    "RequestBody": "http request body deserialization",
    "ResponseBody": "http response body serialization",
    "RequestParam": "http request parameter query string",
    "ExceptionHandler": "exception handling error management",
    "Scheduled": "scheduled task cron job",
    "Async": "asynchronous method execution",
    "EnableScheduling": "enable scheduling configuration",
    "EnableAsync": "enable async configuration",
    "Profile": "spring profile environment configuration",
    "ConditionalOnProperty": "conditional bean creation configuration",
    "SpringBootTest": "integration test spring boot",
    "Test": "unit test junit",
    "MockBean": "mock bean test",
}


def extract_annotation_queries(question: str) -> list[str]:
    """
    Détecte les annotations Java/Spring Boot dans la question et génère
    des requêtes ciblées pour améliorer le retrieval sur la doc Spring Boot.

    Principe : le modèle d'embedding paraphrase aligne mal "comment utiliser
    @RestController" avec le chunk qui définit RestController. Une requête
    directe "@RestController rest controller http endpoints" garantit un hit.

    Exemples :
        "comment utiliser @RestController ?"
        → ["@RestController rest controller http endpoints web mvc"]

        "@Autowired vs @Bean quelle différence ?"
        → ["@Autowired dependency injection autowiring beans",
           "@Bean spring bean factory configuration"]

    Retourne une liste vide si aucune annotation n'est trouvée.
    """
    queries: list[str] = []
    seen: set[str] = set()

    for m in _ANNOTATION_RE.finditer(question):
        name = m.group(1)
        if name in seen:
            continue
        seen.add(name)

        context = _SPRING_ANNOTATION_CONTEXT.get(name, "")
        if context:
            queries.append(f"@{name} {context}")
        else:
            queries.append(f"@{name} annotation")

    if queries:
        logger.info(f"[annotation_queries] Annotations détectées : {queries}")
    return queries


# ──────────────────────────────────────────────────────────────
# Nettoyage du bruit dans les PDFs format slides
# ──────────────────────────────────────────────────────────────

# Patterns récurrents dans les PDFs de type présentation/cours
_SLIDE_NOISE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b\d{2}:\d{2}:\d{2}\b"),  # timestamps (08:16:59)
    re.compile(r"Programmation Web\s+\d{4}[\-–]\d{4}", re.I),  # "Programmation Web 2012-2013"
    re.compile(r"^\s*\d{1,3}\s*$", re.MULTILINE),  # numéros de page seuls
    re.compile(r"^[\s\-–_=]{3,}$", re.MULTILINE),  # lignes de séparation vides
]


def clean_slide_text(text: str) -> str:
    """
    Supprime le bruit récurrent des PDFs format slides/cours
    (timestamps, footers répétitifs, numéros de page isolés).

    Utilisé dans loader.py pour améliorer la qualité des chunks
    issus de documents de type présentation.
    """
    for pattern in _SLIDE_NOISE_PATTERNS:
        text = pattern.sub("", text)
    # Nettoyer les lignes vides multiples générées par les suppressions
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ──────────────────────────────────────────────────────────────
# Enrichissement sémantique des concepts juridiques
# ──────────────────────────────────────────────────────────────

# Paires (pattern de détection dans la question, requête enrichie pour FAISS)
# Activées uniquement si le concept apparaît textuellement dans la question.
_LEGAL_CONCEPTS: list[tuple[re.Pattern, str]] = [
    # ── Droit du travail (Code du Travail) ──────────────────────
    (
        re.compile(r"\blicenci(?:ement|er|é|és)\b", re.I),
        "licenciement motif cause réelle sérieuse procédure lettre préavis",
    ),
    (
        re.compile(r"\brupture\s+conventionnelle\b", re.I),
        "rupture conventionnelle contrat travail homologation formulaire",
    ),
    (
        re.compile(r"\bheures?\s+suppl[eé]mentaires?\b", re.I),
        "heures supplémentaires durée travail majoration contingent annuel",
    ),
    (
        re.compile(r"\bcong[eé]\s+(?:parental|maternit[eé]|paternit[eé]|pay[eé])\b", re.I),
        "congé parental maternité paternité payé protection emploi durée",
    ),
    (
        re.compile(r"\bharc[eè]lement\b", re.I),
        "harcèlement moral sexuel définition obligation employeur sanctions pénales",
    ),
    (
        re.compile(r"\bdiscrimination\b", re.I),
        "discrimination emploi interdiction critères protégés égalité traitement",
    ),
    (
        re.compile(r"\bpr[eé]avis\b", re.I),
        "préavis licenciement démission durée délai dispense rémunération",
    ),
    (
        re.compile(r"\bindemni(?:t[eé]|sation)\s+(?:de\s+)?licenciement\b", re.I),
        "indemnité licenciement calcul ancienneté barème légal",
    ),
    (
        re.compile(r"\bprud[''']?hommes?\b", re.I),
        "conseil prud'hommes compétence procédure saisine conciliation jugement",
    ),
    (
        re.compile(r"\bp[eé]riode\s+d[''']essai\b", re.I),
        "période essai durée renouvellement rupture conditions CDI CDD",
    ),
    (
        re.compile(r"\bgrève\b", re.I),
        "grève droit exercice préavis service minimum réquisition",
    ),
    (
        re.compile(r"\bsyndicat\b", re.I),
        "syndicat représentativité droits délégué section syndicale",
    ),
    (
        re.compile(r"\bcomit[eé]\s+social\b", re.I),
        "comité social économique CSE attributions consultation représentation",
    ),
    # ── Droit civil (Code Civil) ─────────────────────────────────
    (
        re.compile(r"\bdivorce\b", re.I),
        "divorce causes procédure consentement mutuel faute effets patrimoniaux",
    ),
    (
        re.compile(r"\bmariage\b", re.I),
        "mariage conditions célébration effets régime matrimonial époux",
    ),
    (
        re.compile(r"\bsuccession\b", re.I),
        "succession héritage héritiers réserve héréditaire quotité disponible",
    ),
    (
        re.compile(r"\btestament\b", re.I),
        "testament formes validité olographe authentique legs légataire",
    ),
    (
        re.compile(r"\bdonation\b", re.I),
        "donation conditions effets révocation réduction rapport succession",
    ),
    (
        re.compile(r"\bresponsabilit[eé]\s+civile\b", re.I),
        "responsabilité civile délictuelle contractuelle faute dommage réparation",
    ),
    (
        re.compile(r"\bprescription\b", re.I),
        "prescription délai extinction droit action civile interruption",
    ),
    (
        re.compile(r"\bgarde\s+(?:d[''']?enfant|alternée)\b", re.I),
        "garde enfant autorité parentale résidence alternée droit visite",
    ),
    (
        re.compile(r"\btutelle\b", re.I),
        "tutelle curatelle mesure protection majeur incapacité tribunal",
    ),
    (
        re.compile(r"\badoption\b", re.I),
        "adoption plénière simple conditions effets filiation",
    ),
    (
        re.compile(r"\bhypoth[eè]que\b", re.I),
        "hypothèque sûreté réelle immeuble inscription créancier privilège",
    ),
    (
        re.compile(r"\bnullit[eé]\s+(?:d[eu][s]?\s+)?contrat\b", re.I),
        "nullité contrat vices consentement dol erreur violence relative absolue",
    ),
    # ── Droit pénal (Code Pénal) ─────────────────────────────────
    (
        re.compile(r"\bgarde\s+[aà]\s+vue\b", re.I),
        "garde à vue droits durée renouvellement notification avocat silence",
    ),
    (
        re.compile(r"\bmise\s+en\s+examen\b", re.I),
        "mise en examen instruction judiciaire juge indices graves charges",
    ),
    (
        re.compile(r"\bd[eé]tention\s+provisoire\b", re.I),
        "détention provisoire conditions durée liberté présomption innocence",
    ),
    (
        re.compile(r"\bl[eé]gitime\s+d[eé]fense\b", re.I),
        "légitime défense conditions proportionnalité nécessité riposte infraction",
    ),
    (
        re.compile(r"\bcomplicit[eé]\b", re.I),
        "complicité aide assistance infraction peine auteur principal",
    ),
    (
        re.compile(r"\br[eé]cidive\b", re.I),
        "récidive aggravation peine circonstances définition délai",
    ),
    (
        re.compile(r"\bhomicide\b", re.I),
        "homicide involontaire volontaire meurtre assassinat peine réclusion",
    ),
    (
        re.compile(r"\bvol\s+(?:qualifi[eé]|avec\s+violence|aggrav[eé])\b", re.I),
        "vol qualifié violence arme bande organisée circonstances aggravantes peine",
    ),
    (
        re.compile(r"\bextorsion\b", re.I),
        "extorsion violence menace contrainte bien signature peine crime",
    ),
    # ── Droit pénal — compléments ────────────────────────────────
    (
        re.compile(r"\bviol\b|\bagression\s+sexuelle\b|\batteinte\s+sexuelle\b", re.I),
        "viol agression sexuelle atteinte mineur consentement peine crime",
    ),
    (
        re.compile(r"\bescroquerie\b", re.I),
        "escroquerie tromperie manœuvres frauduleuses remise bien peine",
    ),
    (
        re.compile(r"\babus\s+de\s+confiance\b", re.I),
        "abus confiance détournement bien remis usage déterminé peine",
    ),
    (
        re.compile(r"\bterrorisme\b|\bacte\s+terroriste\b", re.I),
        "terrorisme acte infraction association malfaiteurs financement peine",
    ),
    (
        re.compile(r"\bcrime[s]?\b|\bcrim(?:inel|inelle|inels)\b", re.I),
        "crime classification infraction peine réclusion cour d'assises",
    ),
    (
        re.compile(r"\bd[eé]lit[s]?\b", re.I),
        "délit infraction tribunal correctionnel peine emprisonnement amende",
    ),
    (
        re.compile(r"\bcontravention[s]?\b", re.I),
        "contravention infraction tribunal police amende classe",
    ),
    # ── Droit civil — compléments ────────────────────────────────
    (
        re.compile(r"\bPACS\b|\bpacte\s+civil\s+de\s+solidarit[eé]\b", re.I),
        "PACS pacte civil solidarité enregistrement effets rupture régime",
    ),
    (
        re.compile(r"\bfiliation\b|\b[eé]tablissement\s+de\s+la\s+filiation\b", re.I),
        "filiation reconnaissance légitimité paternité maternité acte naissance",
    ),
    (
        re.compile(r"\bobligation\s+alimentaire\b|\bpension\s+alimentaire\b", re.I),
        "obligation alimentaire pension alimentaire créancier débiteur calcul",
    ),
    (
        re.compile(r"\bbail\b|\blocataire\b|\bpropri[eé]taire\b|\blocatif\b", re.I),
        "bail loyer locataire bailleur congé préavis dépôt garantie charges",
    ),
    (
        re.compile(r"\bcopropri[eé]t[eé]\b|\bsyndicat\s+de\s+copropri[eé]taires\b", re.I),
        "copropriété lot tantièmes assemblée générale syndic charges règlement",
    ),
    (
        re.compile(
            r"\bcontrat\s+de\s+vente\b|\bvente\s+(?:immobili[eè]re|d[''']un\s+bien)\b", re.I
        ),
        "contrat vente prix livraison transfert propriété garanties défauts",
    ),
    # ── Droit du travail — compléments ──────────────────────────
    (
        re.compile(r"\b35\s*heures?\b|\bdur[eé]e\s+l[eé]gale\b|\btemps\s+de\s+travail\b", re.I),
        "durée légale travail 35 heures semaine dépassement contingent annuel",
    ),
    (
        re.compile(r"\bt[eé]l[eé]travail\b|\btravail\s+[aà]\s+distance\b", re.I),
        "télétravail accord conditions matériel frais prise en charge employeur",
    ),
    (
        re.compile(r"\bapprentissage\b|\bcontrat\s+d[''']apprentissage\b", re.I),
        "apprentissage contrat apprenti maître d'apprentissage rémunération formation",
    ),
    (
        re.compile(r"\bformation\s+professionnelle\b|\bCPF\b", re.I),
        "formation professionnelle CPF plan développement compétences financement OPCO",
    ),
    (
        re.compile(r"\bconvention\s+de\s+forfait\b|\bforfait\s+jours?\b", re.I),
        "convention forfait jours cadre accord collectif renonciation RTT",
    ),
    # ── Droits fondamentaux (DDHC / Constitution) ────────────────
    (
        re.compile(r"\blibert[eé]\s+d[''']expression\b", re.I),
        "liberté expression presse opinion droits fondamentaux déclaration",
    ),
    (
        re.compile(r"\b[eé]galit[eé]\s+(?:devant\s+la\s+loi|des\s+droits|des\s+citoyens)\b", re.I),
        "égalité droits citoyens loi principe constitutionnel",
    ),
    (
        re.compile(r"\bpropri[eé]t[eé]\s+(?:priv[eé]e|droit|inviolable)\b", re.I),
        "propriété droit inviolable sacré expropriation utilité publique",
    ),
    (
        re.compile(r"\bpr[eé]somption\s+d[''']innocence\b", re.I),
        "présomption innocence droits défense principe fondamental accusé",
    ),
    (
        re.compile(r"\bsouverainet[eé]\b|\bsouverain\b", re.I),
        "souveraineté nationale peuple délégation représentants élections",
    ),
    (
        re.compile(r"\blibert[eé]\s+(?:individuelle|personnelle|fondamentale)\b", re.I),
        "liberté individuelle droits naturels inaliénables déclaration",
    ),
    (
        re.compile(r"\bdr(?:oit|oits)\s+de\s+l[''']homme\b|\bDDHC\b", re.I),
        "droits de l'homme citoyen 1789 déclaration principes naturels liberté égalité",
    ),
    # ── Droit constitutionnel (Constitution du 4 octobre 1958) ──
    (
        re.compile(r"\b49[\s\-]3\b|\barticle\s+49\b", re.I),
        "article 49 engagement responsabilité gouvernement texte vote confiance censure",
    ),
    (
        re.compile(r"\bmotion\s+de\s+censure\b", re.I),
        "motion censure Assemblée nationale renversement gouvernement vote",
    ),
    (
        re.compile(r"\bdissolution\b|\bdissoudre\s+l[''']Assembl[eé]e\b", re.I),
        "dissolution Assemblée nationale Président République décret élections législatives",
    ),
    (
        re.compile(r"\br[eé]vision\s+constitutionnelle\b|\bmodifier\s+la\s+Constitution\b", re.I),
        "révision Constitution article 89 initiative parlement référendum congrès",
    ),
    (
        re.compile(r"\b[eé]tat\s+d[''']urgence\b|\barticle\s+16\b", re.I),
        "état urgence pouvoirs exceptionnels article 16 Président République menace",
    ),
    (
        re.compile(r"\bConseil\s+constitutionnel\b", re.I),
        "Conseil constitutionnel contrôle conformité loi Constitution QPC membres",
    ),
    (
        re.compile(r"\bQuestion\s+[Pp]rioritaire\s+de\s+[Cc]onstitutionnalit[eé]\b|\bQPC\b", re.I),
        "QPC question prioritaire constitutionnalité droits fondamentaux contrôle",
    ),
    (
        re.compile(r"\bPremier\s+ministre\b|\bchef\s+du\s+gouvernement\b", re.I),
        "Premier ministre chef gouvernement nomination responsabilité Assemblée",
    ),
    (
        re.compile(r"\bPr[eé]sident\s+de\s+la\s+R[eé]publique\b|\bpr[eé]sidentiel\b", re.I),
        "Président République pouvoirs élection quinquennat promulgation loi",
    ),
    (
        re.compile(r"\bs[eé]paration\s+des\s+pouvoirs?\b", re.I),
        "séparation pouvoirs exécutif législatif judiciaire équilibre Constitution",
    ),
    (
        re.compile(r"\bparlement\b|\bAssembl[eé]e\s+nationale\b|\bS[eé]nat\b", re.I),
        "Parlement Assemblée nationale Sénat vote loi bicamérisme navette",
    ),
    # ── Convention collective (RH) ────────────────────────────────
    (
        re.compile(r"\bgrille\s+salariale\b|\bclassification\s+(?:profession|\s)", re.I),
        "grille salariale classification coefficient catégorie emploi échelon",
    ),
    (
        re.compile(r"\bsal(?:aire|aris[eé]s?)\s+(?:minimum|de\s+base|brut|net)\b", re.I),
        "salaire minimum base brut net coefficient classification grille rémunération",
    ),
    (
        re.compile(r"\bprime\s+(?:d[''']anciennet[eé]|de\s+treizi[eè]me|annuelle)\b", re.I),
        "prime ancienneté treizième mois annuelle conditions calcul versement",
    ),
    (
        re.compile(r"\bconvention\s+collective\b", re.I),
        "convention collective accord branche entreprise salaires classification préavis",
    ),
    (
        re.compile(
            r"\bpr[eé]avis\s+(?:de\s+)?(?:d[eé]mission|licenciement)\b.*convention\b"
            r"|convention\b.*\bpr[eé]avis\b",
            re.I,
        ),
        "préavis démission licenciement durée convention collective catégorie cadre",
    ),
    (
        re.compile(r"\bmutuelle\b|\bcompl[eé]mentaire\s+sant[eé]\b|\bprevoyance\b", re.I),
        "mutuelle complémentaire santé prévoyance cotisation employeur salarié",
    ),
    (
        re.compile(r"\bretraite\s+compl[eé]mentaire\b|\bARRCO\b|\bAGIRC\b", re.I),
        "retraite complémentaire ARRCO AGIRC points cotisation taux",
    ),
    (
        re.compile(
            r"\bavantage[s]?\s+en\s+nature\b|\bticketing?\s+restaurant\b|\bvéhicule\s+de\s+fonction\b",
            re.I,
        ),
        "avantages en nature ticket restaurant véhicule de fonction évaluation cotisations",
    ),
    (
        re.compile(r"\bintéressement\b|\bparticipation\b|\bépargne\s+salariale\b", re.I),
        "intéressement participation épargne salariale accord bénéfices répartition",
    ),
    (
        re.compile(
            r"\bclassification\s+(?:convention|convention\s+collective|emploi|poste)\b"
            r"|niveau\s+(?:de\s+classification|d[''']emploi)\b",
            re.I,
        ),
        "classification emploi poste niveau coefficient critères classement",
    ),
]


def extract_legal_concept_queries(question: str) -> list[str]:
    """
    Détecte les concepts juridiques dans la question et génère des requêtes
    enrichies avec le vocabulaire légal technique correspondant.

    Couvre : Code du Travail, Code Civil, Code Pénal, Constitution 1958,
    DDHC 1789 et Convention collective (RH).

    Principe : la question « comment se passe un licenciement ? » ne contient
    pas les termes « cause réelle sérieuse » ou « préavis » qui apparaissent dans
    les chunks du Code du Travail. La requête enrichie les injecte pour améliorer
    la similarité vectorielle avec les bons chunks.

    Exemples :
        "comment se passe un licenciement ?"
            → ["licenciement motif cause réelle sérieuse procédure lettre préavis"]

        "qu'est-ce qu'une garde à vue ?"
            → ["garde à vue droits durée renouvellement notification avocat silence"]

        "quelle est la grille salariale ?"
            → ["grille salariale classification coefficient catégorie emploi échelon"]

    Retourne une liste vide si aucun concept juridique n'est détecté.
    """
    queries: list[str] = []
    seen: set[str] = set()

    for pattern, enriched in _LEGAL_CONCEPTS:
        if pattern.search(question) and enriched not in seen:
            seen.add(enriched)
            queries.append(enriched)

    if queries:
        logger.info(f"[legal_concept_queries] Concepts juridiques : {queries}")
    return queries


# ──────────────────────────────────────────────────────────────
# Enrichissement sémantique des concepts techniques (JS / PHP)
# ──────────────────────────────────────────────────────────────

# Paires (pattern de détection dans la question, requête enrichie pour FAISS)
# Complémentaire aux annotations Spring Boot — couvre le JS (Cours_Javascript.pdf)
# et PHP (Php.pdf) dont les concepts ne bénéficient d'aucun enrichissement natif.
_TECH_CONCEPTS: list[tuple[re.Pattern, str]] = [
    # ── JavaScript ───────────────────────────────────────────────
    (
        re.compile(r"\bclosure[s]?\b", re.I),
        "closure portée variable fonction contexte lexical environnement",
    ),
    (
        re.compile(r"\bhoisting\b|\bremonté[eés]?\b.*(?:var|déclaration)\b", re.I),
        "hoisting remontée déclaration variable var let const portée",
    ),
    (
        re.compile(r"\bpromesse[s]?\b|\bpromise[s]?\b", re.I),
        "promise promesse then catch finally resolve reject état pending",
    ),
    (
        re.compile(r"\basync\b.*\bawait\b|\bawait\b.*\basync\b|\basync\/await\b", re.I),
        "async await promesse asynchrone fonction mot-clé JavaScript",
    ),
    (
        re.compile(r"\bDOM\b|\bdocument\s+object\s+model\b|\bmanipulation\s+(?:du\s+)?DOM\b", re.I),
        "DOM document object model manipulation élément nœud sélecteur",
    ),
    (
        re.compile(r"\b(?:gestionnaire\s+d['''])?[eé]v[eé]nement[s]?\b|\baddEventListener\b", re.I),
        "événement addEventListener gestionnaire callback clic souris clavier",
    ),
    (
        re.compile(r"\bprototype\b", re.I),
        "prototype héritage chaîne objet JavaScript __proto__ Object",
    ),
    (
        re.compile(r"\bmodule[s]?\s+(?:ES6|javascript|js)\b|\bimport\b.*\bfrom\b", re.I),
        "module import export ES6 CommonJS ESM default named",
    ),
    (
        re.compile(r"\bfetch\b|\bXMLHttpRequest\b", re.I),
        "fetch XMLHttpRequest requête HTTP API JSON asynchrone réponse",
    ),
    (
        re.compile(r"\blocal\s*storage\b|\bsession\s*storage\b", re.I),
        "localStorage sessionStorage stockage navigateur clé valeur persistance",
    ),
    (
        re.compile(r"\bdestructuration\b|\bdestructuring\b", re.I),
        "destructuration tableau objet affectation ES6 spread rest",
    ),
    (
        re.compile(r"\bclasse[s]?\s+(?:javascript|js|ES6)\b|\bclass\b.*\bextends\b", re.I),
        "classe ES6 constructeur héritage extends super méthodes JavaScript",
    ),
    (
        re.compile(r"\bportée\b|\bscope\b", re.I),
        "portée scope variable let const var bloc fonction globale",
    ),
    (
        re.compile(r"\bcallback[s]?\b|\bfonction\s+de\s+rappel\b", re.I),
        "callback fonction rappel asynchrone paramètre exécution",
    ),
    (
        re.compile(r"\bspread\b|\brest\b.*param[eè]tres?\b|\bop[eé]rateur\s+\.\.\.", re.I),
        "spread rest opérateur décomposition tableau objet paramètres",
    ),
    # ── PHP ──────────────────────────────────────────────────────
    (
        re.compile(r"\bPDO\b|\bbase\s+de\s+donn[eé]es\s+PHP\b|\bconnexion\s+PHP\b", re.I),
        "PDO connexion base données PHP requête préparée prepare execute fetch",
    ),
    (
        re.compile(r"\bsession[s]?\s+PHP\b|\b\$_SESSION\b|\bsession_start\b", re.I),
        "session PHP $_SESSION session_start stockage variable côté serveur",
    ),
    (
        re.compile(r"\bcookie[s]?\s+PHP\b|\bsetcookie\b|\b\$_COOKIE\b", re.I),
        "cookie PHP setcookie $_COOKIE lecture expiration sécurité",
    ),
    (
        re.compile(r"\btableau[x]?\s+PHP\b|\barray\b.*\bPHP\b|\bPHP\b.*\barray\b", re.I),
        "tableau array PHP fonctions array_map array_filter sort count",
    ),
    (
        re.compile(r"\bclasse[s]?\s+PHP\b|\bhéritage\s+PHP\b|\bextends\b.*PHP\b", re.I),
        "classe PHP héritage extends constructeur __construct méthodes public private",
    ),
    (
        re.compile(r"\bformulaire[s]?\s+PHP\b|\b\$_POST\b|\b\$_GET\b", re.I),
        "formulaire PHP $_POST $_GET traitement validation données utilisateur",
    ),
    (
        re.compile(r"\bnamespace[s]?\s+PHP\b|\buse\b.*\\\w", re.I),
        "namespace PHP espace noms autoload use Composer PSR",
    ),
    (
        re.compile(r"\binclude\b.*PHP\b|\brequire\b.*PHP\b|\bPHP\b.*\binclude\b", re.I),
        "include require include_once require_once fichier PHP modularité",
    ),
    (
        re.compile(r"\binterface\s+PHP\b|\btrait[s]?\s+PHP\b|\babstrait[e]?\b.*PHP\b", re.I),
        "interface trait classe abstraite PHP contrat implémentation",
    ),
    (
        re.compile(r"\bgestion\s+(?:d['''])?erreur[s]?\s+PHP\b|\btry\b.*\bcatch\b.*PHP\b", re.I),
        "exception erreur PHP try catch finally throw Exception gestion",
    ),
]


def extract_tech_concept_queries(question: str) -> list[str]:
    """
    Détecte les concepts techniques JavaScript/PHP dans la question et génère
    des requêtes enrichies avec le vocabulaire technique correspondant.

    Couvre les documents :
    - Cours_Javascript.pdf : closures, DOM, promesses, async/await, classes ES6…
    - Php.pdf : PDO, sessions, tableaux, classes PHP, formulaires…

    Principe identique à extract_legal_concept_queries : la question
    « comment créer une promesse ? » ne contient pas les mots « then », « catch »,
    « resolve » qui apparaissent dans les chunks du cours. La requête enrichie
    les injecte pour améliorer la similarité vectorielle.

    Exemples :
        "comment fonctionne async/await ?"
            → ["async await promesse asynchrone fonction mot-clé JavaScript"]

        "comment se connecter à une BDD en PHP ?"
            → ["PDO connexion base données PHP requête préparée prepare execute fetch"]

    Retourne une liste vide si aucun concept technique n'est détecté.
    """
    queries: list[str] = []
    seen: set[str] = set()

    for pattern, enriched in _TECH_CONCEPTS:
        if pattern.search(question) and enriched not in seen:
            seen.add(enriched)
            queries.append(enriched)

    if queries:
        logger.info(f"[tech_concept_queries] Concepts techniques JS/PHP : {queries}")
    return queries
