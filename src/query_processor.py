"""
query_processor.py — Utilitaires génériques d'enrichissement de requête (refonte v2).

Toute la logique domaine-spécifique (extraction d'articles juridiques, lookups
RH, annotations Spring Boot, etc.) a été supprimée. Le système est désormais
agnostique du domaine et s'appuie sur :

1. expand_acronyms()      — Expansion des acronymes courants (multi-domaines, latence nulle).
2. contextualize_query()  — Réécriture contextuelle via LLM, uniquement si nécessaire
                            (pronoms anaphoriques ou question très courte).
3. decompose_comparative_query() — Décomposition « X vs Y » en sous-requêtes.

Les autres signaux (numéros d'articles, mots-clés rares) sont captés par
l'index BM25 hybride, plus aucune extraction codée en dur n'est nécessaire.
"""

import logging
import re

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Dictionnaire d'acronymes courants (FR/EN, multi-domaines)
# ──────────────────────────────────────────────────────────────

ACRONYMS: dict[str, str] = {
    # Tech / Informatique
    "API": "interface de programmation applicative",
    "BDD": "base de données",
    "SQL": "structured query language",
    "ORM": "object-relational mapping",
    "CI": "intégration continue",
    "CD": "déploiement continu",
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
    "SSO": "single sign-on",
    "MFA": "authentification multi-facteurs",
    "DNS": "domain name system",
    "VPN": "réseau privé virtuel",
    "VM": "machine virtuelle",
    "IaC": "infrastructure as code",
    "DOM": "document object model",
    "JS": "javascript",
    "TS": "typescript",
    "HTML": "hypertext markup language",
    "CSS": "cascading style sheets",
    "SPA": "single page application",
    "PWA": "progressive web application",
    "SSR": "server-side rendering",
    "CSR": "client-side rendering",
    "JVM": "java virtual machine",
    "JDK": "java development kit",
    "JPA": "java persistence api",
    "JDBC": "java database connectivity",
    "DTO": "data transfer object",
    "DAO": "data access object",
    "TDD": "test driven development",
    "DDD": "domain driven design",
    "JSON": "javascript object notation",
    "XML": "extensible markup language",
    "YAML": "yaml ain't markup language",
    "CSV": "comma separated values",
    "RAG": "retrieval augmented generation",
    "LLM": "large language model",
    "IA": "intelligence artificielle",
    "AI": "artificial intelligence",
    # Java / Spring Boot
    "IoC": "inversion of control",
    "AOP": "aspect oriented programming",
    "POJO": "plain old java object",
    "JSP": "java server pages",
    "JPQL": "java persistence query language",
    "HQL": "hibernate query language",
    "SDK": "software development kit",
    "CLI": "command line interface",
    "OOP": "object oriented programming",
    "JAR": "java archive",
    "WAR": "web application archive",
    "EAR": "enterprise archive",
    "JEE": "java enterprise edition",
    "CDI": "contexts and dependency injection",
    # Business / RH (sans biais)
    "CDD": "contrat à durée déterminée",
    "RH": "ressources humaines",
    "PME": "petite et moyenne entreprise",
    "ETI": "entreprise de taille intermédiaire",
    "CA": "chiffre d'affaires",
    "RGPD": "règlement général sur la protection des données",
    "GDPR": "general data protection regulation",
    "CGU": "conditions générales d'utilisation",
    "CGV": "conditions générales de vente",
    "SLA": "service level agreement",
    "KPI": "key performance indicator",
    "ROI": "return on investment",
    "B2B": "business to business",
    "B2C": "business to consumer",
    # Droit / Juridique FR
    "SMIC": "salaire minimum interprofessionnel de croissance",
    "CPF": "compte personnel de formation",
    "PACS": "pacte civil de solidarité",
    "IDCC": "identifiant de convention collective",
    "JO": "journal officiel",
    "CSE": "comité social et économique",
    "CHSCT": "comité d'hygiène de sécurité et des conditions de travail",
    "DDHC": "déclaration des droits de l'homme et du citoyen",
    "TJ": "tribunal judiciaire",
    "TGI": "tribunal de grande instance",
    "CPP": "code de procédure pénale",
    "CPC": "code de procédure civile",
    "CC": "code civil",
    "CT": "code du travail",
    "CP": "code pénal",
    "CE": "conseil d'état",
    "QPC": "question prioritaire de constitutionnalité",
    "CEDH": "convention européenne des droits de l'homme",
    "CJUE": "cour de justice de l'union européenne",
}

# Marqueurs anaphoriques signalant une question dépendante du contexte
_ANAPHORA = re.compile(
    r"\b(il|elle|ils|elles|son|sa|ses|leur|leurs|"
    r"ce|cet|cette|ces|celui|celle|ceux|celles|"
    r"y|en|ça|cela|ceci|lequel|laquelle|lesquels|lesquelles|"
    r"dont|duquel|de laquelle|"
    r"le même|la même|les mêmes|"
    r"les deux|tous les deux|toutes les deux|"
    r"l'un et l'autre|l'une et l'autre|"
    r"chacun|chacune|l'un|l'une|l'autre|"
    r"it|its|them|they|their|both|the same|each|either)\b",
    re.IGNORECASE,
)

# Détection des questions comparatives
_COMPARATIVE_RE: list[re.Pattern] = [
    re.compile(r"\bdiff[eé]rence[s]?\s+entre\s+(.+?)\s+et\s+(.+?)(?=\s*\?|$)", re.IGNORECASE),
    re.compile(r"\bcompar(?:er|aison|ez)\s+(?:entre\s+)?(.+?)\s+et\s+(.+?)(?=\s*\?|$)", re.IGNORECASE),
    re.compile(r"\b(.+?)\s+(?:versus|vs\.?)\s+(.+?)(?=\s*\?|$)", re.IGNORECASE),
    re.compile(r"\bdistin(?:guer|ction)\s+(?:entre\s+|de\s+)?(.+?)\s+(?:et|de)\s+(.+?)(?=\s*\?|$)", re.IGNORECASE),
    re.compile(r"\bdifference[s]?\s+between\s+(.+?)\s+and\s+(.+?)(?=\s*\?|$)", re.IGNORECASE),
    re.compile(r"\bcompare\s+(.+?)\s+(?:and|with|to)\s+(.+?)(?=\s*\?|$)", re.IGNORECASE),
]

_REWRITE_PROMPT = """\
Tu es un assistant de reformulation. Réécris la question de l'utilisateur \
pour qu'elle soit autonome et précise, en tenant compte du contexte ci-dessous.
Ne donne QUE la question reformulée, sans explication ni ponctuation finale.

Règles impératives :
- Conserve EXACTEMENT les numéros d'articles juridiques (ex: L1234-5, 111-1, Article 1er, L.1237-19).
- Conserve EXACTEMENT les identifiants techniques (numéros de version, noms de classes, annotations).
- Remplace les pronoms anaphoriques (il, elle, ce, cela…) par le nom explicite qu'ils désignent.
- Ne supprime ni n'abrège aucun terme clé déjà présent dans la question originale.

Contexte (derniers échanges) :
{context}

Question originale : {question}
Question reformulée :"""


# ──────────────────────────────────────────────────────────────
# Expansion des acronymes
# ──────────────────────────────────────────────────────────────


def expand_acronyms(text: str) -> str:
    """
    Remplace les acronymes connus par « ACRONYME (forme longue) ».
    Capture les majuscules pures (CDI, API, REST) et mixed-case (IoC, NoSQL).
    """

    def _replace(match: re.Match) -> str:
        token = match.group(0)
        key = token if token in ACRONYMS else token.upper()
        if key in ACRONYMS:
            return f"{token} ({ACRONYMS[key]})"
        return token

    return re.sub(r"\b[A-Z][A-Za-z0-9]{1,8}\b", _replace, text)


# ──────────────────────────────────────────────────────────────
# Réécriture contextuelle via LLM
# ──────────────────────────────────────────────────────────────


def _needs_contextualization(question: str, has_history: bool) -> bool:
    if not has_history:
        return False
    q = question.strip()
    return bool(_ANAPHORA.search(q)) or len(q.split()) <= 5


def contextualize_query(question: str, history_text: str, llm, *, max_history_chars: int = 600) -> str:
    has_history = bool(history_text and history_text.strip())
    if not _needs_contextualization(question, has_history):
        return question

    context_snippet = history_text[-max_history_chars:] if has_history else ""

    try:
        from langchain_core.messages import HumanMessage

        prompt_text = _REWRITE_PROMPT.format(context=context_snippet, question=question)
        result = llm.invoke([HumanMessage(content=prompt_text)])
        if not isinstance(result.content, str):
            return question
        rewritten = result.content.strip().strip('"').strip("'")
        if not rewritten or len(rewritten) > 400:
            return question
        logger.info(f"Query rewritten: «{question}» → «{rewritten}»")
        return rewritten
    except Exception as e:
        logger.warning(f"Query rewriting ignoré : {e}")
        return question


async def contextualize_query_async(
    question: str, history_text: str, llm, *, max_history_chars: int = 600
) -> str:
    has_history = bool(history_text and history_text.strip())
    if not _needs_contextualization(question, has_history):
        return question

    context_snippet = history_text[-max_history_chars:] if has_history else ""

    try:
        from langchain_core.messages import HumanMessage

        prompt_text = _REWRITE_PROMPT.format(context=context_snippet, question=question)
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
    « différence entre X et Y » → 3 sous-requêtes : X, Y, et la comparaison.
    Retourne une liste vide si aucun motif comparatif n'est détecté.
    """
    cleaned = re.sub(
        r"^(quelle est|quelles sont|qu'est-ce que|comment|pourquoi|what is|what are|how|why)\s+",
        "",
        question.strip(),
        flags=re.IGNORECASE,
    )
    for pattern in _COMPARATIVE_RE:
        m = pattern.search(cleaned)
        if m:
            x = m.group(1).strip().rstrip(".,;:")
            y = m.group(2).strip().rstrip(".,;:")
            if len(x) < 2 or len(y) < 2:
                continue
            x_exp = expand_acronyms(x)
            y_exp = expand_acronyms(y)
            sub_queries = [
                f"{x_exp} définition caractéristiques",
                f"{y_exp} définition caractéristiques",
                f"différences {x_exp} {y_exp}",
            ]
            logger.info(f"[decompose] «{x}» vs «{y}» → {len(sub_queries)} sous-requêtes")
            return sub_queries
    return []


# ──────────────────────────────────────────────────────────────
# Détection de numéros d'articles juridiques
# ──────────────────────────────────────────────────────────────

# Patterns : L1234-5, R123-4, D12-3, L.1234-5, Article 111-1, Art. 2, 1er alinéa, etc.
_ARTICLE_RE = re.compile(
    r"\b(?:article|art\.?)\s*([A-Z]\.?\d[\d.-]*)"  # Article L1234-5 ou Art. R12-3
    r"|\b([LRD]\.?\d[\d.-]+)\b"                     # L1234-5 seul dans le texte
    r"|\barticle\s+(\d[\d.-]*(?:er|ème|ième)?)\b",  # Article 111-1, Article 1er
    re.IGNORECASE,
)


def extract_article_queries(question: str) -> list[str]:
    """
    Détecte les références à des articles juridiques dans la question et
    génère des sous-requêtes ciblées (ex: "Article L1234-5 texte contenu").
    Retourne une liste vide si aucun article n'est détecté.
    """
    sub_queries: list[str] = []
    seen: set[str] = set()
    for m in _ARTICLE_RE.finditer(question):
        ref = (m.group(1) or m.group(2) or m.group(3) or "").strip().upper()
        if not ref or ref in seen:
            continue
        seen.add(ref)
        sub_queries.append(f"article {ref}")
        sub_queries.append(f"article {ref} texte disposition")
    if sub_queries:
        logger.debug(f"[article_detect] {len(seen)} article(s) détecté(s) : {list(seen)}")
    return sub_queries


# ──────────────────────────────────────────────────────────────
# Pipeline complet (utilisé par chain.py)
# ──────────────────────────────────────────────────────────────


def build_search_query(question: str, history_text: str, llm) -> str:
    expanded = expand_acronyms(question)
    return contextualize_query(expanded, history_text, llm)


async def build_search_query_async(question: str, history_text: str, llm) -> str:
    expanded = expand_acronyms(question)
    return await contextualize_query_async(expanded, history_text, llm)
