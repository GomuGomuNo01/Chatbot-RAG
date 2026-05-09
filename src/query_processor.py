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

    Exemple :
        "c'est quoi un CDI ?"
        → "c'est quoi un CDI (contrat à durée indéterminée) ?"
    """

    def _replace(match: re.Match) -> str:
        token = match.group(0)
        upper = token.upper()
        if upper in ACRONYMS:
            expanded = f"{token} ({ACRONYMS[upper]})"
            logger.debug(f"Acronyme étendu : {token} → {expanded}")
            return expanded
        return token

    # Pattern : séquences de 2-6 lettres majuscules/chiffres en mot entier
    return re.sub(r"\b[A-Z][A-Z0-9]{1,5}\b", _replace, text)


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

    Principe : le modèle d'embedding paraphrase ne fait pas bien la
    correspondance entre « que dit l'article 4 » et le chunk « Article 4 \\n
    Le juge qui refusera… ». En ajoutant une requête directe « Article 4 »,
    on garantit un hit quasi-certain dans l'espace vectoriel.

    Exemples :
        "que dit l'article 4 du code civil"          → ["Article 4"]
        "quelles règles pour les articles 4 et 5 ?"  → ["Article 4", "Article 5"]
        "article L. 1234-5 du code du travail"       → ["Article L. 1234-5"]
        "expliquez les articles R. 123-1 et R. 123-2"→ ["Article R. 123-1", "Article R. 123-2"]

    Retourne une liste vide si aucune référence légale n'est trouvée.
    """
    refs: list[str] = []
    for m in _ARTICLE_NUM_RE.finditer(question):
        refs.append(m.group(1).strip())
    for m in _ARTICLE_AND_RE.finditer(question):
        refs.append(m.group(1).strip())

    # Normalise : "Article N" et déduplique (ordre préservé)
    seen: set[str] = set()
    queries: list[str] = []
    for ref in refs:
        normalized = f"Article {ref}"
        if normalized not in seen:
            seen.add(normalized)
            queries.append(normalized)

    if queries:
        logger.info(f"[article_queries] Références légales détectées : {queries}")
    return queries
