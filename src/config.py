"""Module de configuration de l'Automated AI Content Intelligence Pipeline."""
import os
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

# Chemins
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

# Creer les dossiers s'ils n'existent pas
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)


def _parse_csv_env(var_name: str, default_values: list[str]) -> list[str]:
    raw_value = os.getenv(var_name, "")
    if not raw_value.strip():
        return [str(v).strip() for v in default_values if str(v).strip()]
    return [item.strip() for item in raw_value.split(",") if item.strip()]

# Strategie multi-query RSS (niveau pro):
# - chaque theme produit son flux Google News RSS via:
#   https://news.google.com/rss/search?q=<query>
# - cela donne une collecte ciblee, plus coherente et plus exploitable pour l'IA.
RSS_QUERY_PACKS = {
    "tech": [
        "technologie entreprise",
        "transformation digitale",
        "cloud entreprise",
    ],
    "ia": [
        "intelligence artificielle",
        "intelligence artificielle entreprise",
        "automatisation intelligente",
    ],
    "data": [
        "data analytics",
        "gouvernance des donnees",
        "business intelligence",
    ],
    "marketing": [
        "marketing digital",
        "growth marketing",
        "strategie de contenu",
    ],
    "business": [
        "strategie business",
        "croissance entreprise",
        "transformation des entreprises",
    ],
    "startup": [
        "startup",
        "levee de fonds startup",
        "ecosysteme startup",
    ],
    "innovation": [
        "innovation",
        "innovation industrielle",
        "transformation numerique",
    ],
    "finance": [
        "finance entreprise",
        "financement startup",
        "investissement innovation",
    ],
}

ACTIVE_RSS_QUERY_THEMES = _parse_csv_env(
    "ACTIVE_RSS_QUERY_THEMES",
    ["tech", "ia", "data", "marketing", "business", "startup", "innovation", "finance"],
)
CUSTOM_RSS_QUERIES = _parse_csv_env("CUSTOM_RSS_QUERIES", [])

_targeted_queries = []
for theme in ACTIVE_RSS_QUERY_THEMES:
    _targeted_queries.extend(RSS_QUERY_PACKS.get(theme, []))
_targeted_queries.extend(CUSTOM_RSS_QUERIES)

# Requetes RSS ciblees dedupliquees (ordre preserve).
TARGETED_RSS_QUERIES = list(dict.fromkeys(q.strip() for q in _targeted_queries if q.strip()))

# Pages web a scraper en complement (optionnel, francophone)
WEB_SCRAPE_URLS = [
    "https://www.lesechos.fr/",
    "https://www.bfmtv.com/economie/",
]

# Activite principale et secteurs couverts
ACTIVITE_PRINCIPALE = "creation_contenu"
SECTEURS_CIBLES = [
    "tech",
    "data",
    "ia",
    "marketing",
    "business",
    "startup",
    "innovation",
    "finance",
]

# Configuration IA par API (Groq principal, Gemini en fallback)
AI_PROVIDER_CHAIN = os.getenv("AI_PROVIDER_CHAIN", "groq,gemini")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", os.getenv("GROK_API_KEY", ""))
GROQ_API_BASE = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME", "openai/gpt-oss-20b")
GROQ_TIMEOUT_SECONDS = int(os.getenv("GROQ_TIMEOUT_SECONDS", "45"))

# Alias de compatibilite temporaire pour les variables historiques
GROK_API_KEY = GROQ_API_KEY
GROK_API_BASE = GROQ_API_BASE
GROK_MODEL_NAME = GROQ_MODEL_NAME
GROK_TIMEOUT_SECONDS = GROQ_TIMEOUT_SECONDS

GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")
GEMINI_API_BASE = os.getenv("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")
GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "45"))

GENERATION_MAX_NEW_TOKENS = 320
GENERATION_TEMPERATURE = 0.45
# Nombre d'articles a generer par run (configurable via variable d'environnement)
GENERATED_ARTICLES_LIMIT = int(os.getenv("GENERATED_ARTICLES_LIMIT", "20"))
FAST_GENERATION_MODE = os.getenv("FAST_GENERATION_MODE", "true").strip().lower() == "true"
MAX_LLM_ARTICLES = int(os.getenv("MAX_LLM_ARTICLES", "5"))
GENERATION_STRICT_FACTUAL = True
# Variable dediee pour eviter qu'un ancien env var local desactive la generation sans le vouloir.
ENABLE_GENERATION = os.getenv("PIPELINE_ENABLE_GENERATION", "true").strip().lower() == "true"

# Configuration des articles
MIN_ARTICLE_LENGTH = 100
MAX_ARTICLE_LENGTH = 2000
LANGUAGE = "fr"
FRENCH_ONLY = True
TARGET_MIN_ARTICLES = int(os.getenv("TARGET_MIN_ARTICLES", "20"))
TARGET_MAX_ARTICLES = int(os.getenv("TARGET_MAX_ARTICLES", "30"))
MAX_ARTICLES_PER_QUERY = int(os.getenv("MAX_ARTICLES_PER_QUERY", "6"))
TOP_TOPICS_TO_GENERATE = int(os.getenv("TOP_TOPICS_TO_GENERATE", "3"))

# Traitement
BATCH_SIZE = 4
MAX_WORKERS = 4
TREND_WINDOW_DAYS = 30

# Stockage des donnees
RAW_DATA_FILE = DATA_DIR / "raw_articles.json"
CLEANED_DATA_FILE = DATA_DIR / "cleaned_articles.json"
VALIDATION_CLEANED_DATA_FILE = OUTPUT_DIR / "cleaned_articles_validation.json"
ANALYSIS_FILE = OUTPUT_DIR / "analysis_kpis.json"
GENERATED_ARTICLES_FILE = OUTPUT_DIR / "generated_articles.json"
IA_EXAMPLES_FILE = OUTPUT_DIR / "ia_examples.json"

# Planification
SCHEDULE_INTERVAL = "daily"  # Options: "hourly", "daily", "weekly"
SCHEDULE_TIME = "09:00"  # Format HH:MM


def _is_valid_schedule_time(value: str) -> bool:
    try:
        datetime.strptime(value, "%H:%M")
        return True
    except ValueError:
        return False


def validate_config() -> None:
    """Valider la configuration critique au demarrage."""
    valid_intervals = {"hourly", "daily", "weekly"}
    if SCHEDULE_INTERVAL not in valid_intervals:
        raise ValueError(
            f"SCHEDULE_INTERVAL invalide: {SCHEDULE_INTERVAL}. Valeurs attendues: {sorted(valid_intervals)}"
        )

    if not _is_valid_schedule_time(SCHEDULE_TIME):
        raise ValueError(
            f"SCHEDULE_TIME invalide: {SCHEDULE_TIME}. Format attendu: HH:MM"
        )

    if GENERATED_ARTICLES_LIMIT < 0:
        raise ValueError("GENERATED_ARTICLES_LIMIT doit etre >= 0")

    if GENERATED_ARTICLES_LIMIT > 500:
        raise ValueError("GENERATED_ARTICLES_LIMIT doit etre <= 500 pour eviter une surcharge")

    if MAX_LLM_ARTICLES < 0:
        raise ValueError("MAX_LLM_ARTICLES doit etre >= 0")

    if TARGET_MIN_ARTICLES < 1:
        raise ValueError("TARGET_MIN_ARTICLES doit etre >= 1")

    if TARGET_MAX_ARTICLES < TARGET_MIN_ARTICLES:
        raise ValueError("TARGET_MAX_ARTICLES doit etre >= TARGET_MIN_ARTICLES")

    if TOP_TOPICS_TO_GENERATE < 1:
        raise ValueError("TOP_TOPICS_TO_GENERATE doit etre >= 1")

    if not TARGETED_RSS_QUERIES:
        raise ValueError(
            "TARGETED_RSS_QUERIES est vide. Configurez ACTIVE_RSS_QUERY_THEMES ou CUSTOM_RSS_QUERIES"
        )

    if GROQ_TIMEOUT_SECONDS <= 0:
        raise ValueError("GROQ_TIMEOUT_SECONDS doit etre > 0")

    if GEMINI_TIMEOUT_SECONDS <= 0:
        raise ValueError("GEMINI_TIMEOUT_SECONDS doit etre > 0")

    allowed_providers = {"groq", "grok", "gemini"}
    deprecated_providers = {"local_rules"}
    parsed_chain = []
    for item in AI_PROVIDER_CHAIN.split(","):
        provider = item.strip().lower()
        if provider == "grok":
            provider = "groq"
        if provider in deprecated_providers:
            continue
        if provider:
            parsed_chain.append(provider)
    if not parsed_chain:
        raise ValueError("AI_PROVIDER_CHAIN ne doit pas etre vide")

    invalid = [item for item in parsed_chain if item not in allowed_providers]
    if invalid:
        raise ValueError(
            f"AI_PROVIDER_CHAIN contient des valeurs invalides: {invalid}. Valeurs autorisees: {sorted(allowed_providers)}"
        )
