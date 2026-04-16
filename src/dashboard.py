"""Tableau de bord Streamlit du Pipeline de génération de contenu automatisé."""

import json
import math
import re
import html
from collections import Counter
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from src.config import GENERATED_ARTICLES_LIMIT


PALETTE = {
    "primary": "#1b6b63",
    "secondary": "#2d5ea6",
    "accent": "#c26a32",
    "neutral": "#7f8f85",
    "danger": "#b23a48",
    "ink": "#10212b",
}


st.set_page_config(
    page_title="Pipeline de génération de contenu automatisé",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,500;8..60,700&display=swap');

    :root {
        --bg-0: #f6f8fb;
        --bg-1: #edf1f7;
        --ink-0: #142033;
        --ink-1: #42566f;
        --line: #d5dee9;
        --card: #ffffff;
        --accent-a: #1f4b99;
        --accent-b: #29686a;
        --accent-c: #204f7a;
    }

    html, body, [class*="css"] {
        font-family: 'Space Grotesk', sans-serif;
    }

    .app-shell {
        background: linear-gradient(180deg, var(--bg-0) 0%, var(--bg-1) 100%);
        padding: 1.15rem 1.15rem 0.7rem 1.15rem;
        border: 1px solid var(--line);
        border-radius: 10px;
        margin-bottom: 1rem;
    }

    .title-block h1 {
        margin: 0;
        font-size: 2.45rem;
        color: var(--ink-0);
        letter-spacing: 0.1px;
        font-family: 'Source Serif 4', serif;
    }

    .title-block p {
        margin: 0.25rem 0 0 0;
        color: var(--ink-1);
        font-size: 0.96rem;
        max-width: 920px;
    }

    .section-label {
        color: var(--ink-0);
        font-weight: 700;
        font-size: 1.25rem;
        margin-top: 0.9rem;
        margin-bottom: 0.4rem;
    }

    .plot-title {
        color: var(--ink-0);
        font-weight: 600;
        font-size: 0.98rem;
        margin-top: 0.15rem;
        margin-bottom: 0.35rem;
    }

    .plot-subtitle {
        color: var(--ink-1);
        font-size: 0.8rem;
        line-height: 1.35;
        margin-top: -0.15rem;
        margin-bottom: 0.45rem;
    }

    .chip-row {
        display: flex;
        gap: 0.45rem;
        flex-wrap: wrap;
        margin-top: 0.65rem;
    }

    .chip {
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.96);
        color: var(--ink-1);
        border-radius: 999px;
        padding: 0.18rem 0.62rem;
        font-size: 0.78rem;
        font-weight: 600;
    }

    .kpi-panel {
        border: 1px solid var(--line);
        border-radius: 10px;
        background: var(--card);
        padding: 0.7rem 0.9rem;
        margin-top: 0.3rem;
        margin-bottom: 0.6rem;
    }

    .insight-card {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 10px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
        color: var(--ink-0);
    }

    .footnote {
        color: #5a6a61;
        text-align: center;
        font-size: 0.84rem;
        margin-top: 1rem;
    }

    .article-meta {
        color: var(--ink-1);
        font-size: 0.82rem;
        margin-bottom: 0.6rem;
    }

    .summary-card {
        border: 1px solid var(--line);
        border-radius: 10px;
        background: #ffffff;
        padding: 0.62rem 0.72rem;
        min-height: 84px;
    }

    .summary-label {
        color: var(--ink-1);
        font-size: 0.9rem;
        margin-bottom: 0.15rem;
        font-weight: 600;
    }

    .summary-value {
        color: var(--ink-0);
        font-weight: 700;
        font-size: 1.2rem;
        line-height: 1.35;
        white-space: normal;
        word-break: break-word;
        overflow-wrap: anywhere;
    }

    .summary-delta {
        margin-top: 0.22rem;
        color: var(--ink-1);
        font-size: 0.88rem;
    }

    .article-block {
        background: rgba(255, 255, 255, 1);
        border: 1px solid var(--line);
        border-radius: 10px;
        padding: 0.9rem;
        margin-bottom: 0.8rem;
    }

    .article-block h4 {
        margin: 0 0 0.35rem 0;
        color: var(--ink-0);
        font-size: 1.06rem;
        white-space: normal;
        word-break: break-word;
    }

    .nav-shell {
        border: 1px solid var(--line);
        border-radius: 10px;
        background: #fff;
        padding: 0.5rem 0.6rem;
        margin-bottom: 0.85rem;
    }

    .stRadio > div {
        flex-direction: row;
        gap: 0.45rem;
        flex-wrap: wrap;
    }

    .stRadio [role="radiogroup"] {
        flex-direction: row;
        gap: 0.45rem;
        flex-wrap: wrap;
    }

    .stRadio [data-baseweb="radio"] {
        margin: 0;
        background: #f8fbff;
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: 0.35rem 0.72rem;
        color: var(--ink-1);
        font-weight: 600;
    }

    .stRadio [aria-checked="true"] {
        border-color: var(--accent-a);
        color: var(--accent-a);
        background: #eef4ff;
    }

    .pro-text {
        text-align: justify;
        line-height: 1.7;
        color: var(--ink-0);
        margin-bottom: 0.6rem;
        white-space: normal;
        word-break: break-word;
    }

    .linkedin-card {
        border: 1px solid var(--line);
        background: #fbfdff;
        border-radius: 10px;
        padding: 0.85rem 0.95rem;
        text-align: justify;
        line-height: 1.7;
        color: var(--ink-0);
        white-space: pre-wrap;
        word-break: break-word;
    }

    @media (max-width: 900px) {
        .app-shell {
            padding: 0.9rem 0.85rem 0.55rem 0.85rem;
            border-radius: 12px;
        }

        .title-block h1 {
            font-size: 1.9rem;
            line-height: 1.2;
        }

        .title-block p {
            font-size: 0.89rem;
        }

        .section-label {
            font-size: 1.12rem;
            margin-top: 0.75rem;
        }

        .plot-title {
            font-size: 0.92rem;
        }

        .plot-subtitle {
            font-size: 0.74rem;
        }

        .chip {
            font-size: 0.73rem;
        }

        .kpi-panel {
            padding: 0.55rem 0.65rem;
        }
    }
</style>
""",
    unsafe_allow_html=True,
)


def load_data(filepath: str):
    """Charger un fichier JSON en toute sécurité."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def run_full_pipeline_from_ui():
    """Exécuter le pipeline complet depuis l'interface."""
    try:
        from src.automation_pipeline import AutomationPipeline

        with st.spinner("Exécution du pipeline en cours. Cela peut prendre 20 à 40 secondes..."):
            pipeline = AutomationPipeline()
            results = pipeline.run_complete_pipeline()

        st.session_state["last_pipeline_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.success("Pipeline exécuté avec succès.")
        st.json(results)
    except Exception as e:
        st.error(f"Échec du pipeline: {str(e)}")


def _truncate_label(value: str, max_len: int = 42) -> str:
    text = str(value)
    return text if len(text) <= max_len else text[:max_len - 1] + "..."


def _trend_dataframe(analysis: dict) -> pd.DataFrame:
    trend_dict = analysis.get("analyse_tendances", {}).get("articles_par_jour", {}) if analysis else {}
    if not trend_dict:
        return pd.DataFrame()
    trend_df = pd.DataFrame({"date": list(trend_dict.keys()), "articles": list(trend_dict.values())})
    trend_df["date"] = pd.to_datetime(trend_df["date"], errors="coerce")
    trend_df = trend_df.dropna().sort_values("date")
    return trend_df


def _source_dataframe(analysis: dict) -> pd.DataFrame:
    src = analysis.get("analyse_sources", {}).get("toutes_sources", {}) if analysis else {}
    if not src:
        return pd.DataFrame()
    src_df = pd.DataFrame({"source": list(src.keys()), "articles": list(src.values())})
    src_df = src_df.sort_values("articles", ascending=False)
    src_df["part"] = src_df["articles"] / src_df["articles"].sum()
    src_df["part_cumulee"] = src_df["part"].cumsum()
    return src_df


def _render_justified_text(text: str, css_class: str = "pro-text"):
    value = str(text or "").strip()
    if not value:
        return
    escaped = html.escape(value).replace("\n", "<br>")
    st.markdown(f'<div class="{css_class}">{escaped}</div>', unsafe_allow_html=True)


def _render_stat_card(label: str, value: object, delta: str = ""):
    safe_label = html.escape(str(label or "").strip() or "N/D")
    safe_value = html.escape(str(value if value is not None else "N/D").strip() or "N/D")
    safe_delta = html.escape(str(delta or "").strip())
    delta_block = f'<div class="summary-delta">{safe_delta}</div>' if safe_delta else ""
    st.markdown(
        f"""
<div class="summary-card">
    <div class="summary-label">{safe_label}</div>
    <div class="summary-value">{safe_value}</div>
    {delta_block}
</div>
""",
        unsafe_allow_html=True,
    )


def _render_clickable_stat_card(label: str, value: object, delta: str = "", description: str = ""):
    safe_label = html.escape(str(label or "").strip() or "N/D")
    safe_value = html.escape(str(value if value is not None else "N/D").strip() or "N/D")
    safe_delta = html.escape(str(delta or "").strip())
    safe_description = html.escape(str(description or "").strip())
    delta_block = f'<div class="summary-delta">{safe_delta}</div>' if safe_delta else ""
    components.html(
        f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<style>
    html, body {{
        margin: 0;
        padding: 0;
        background: transparent;
        font-family: 'Space Grotesk', sans-serif;
    }}
    details {{
        width: 100%;
    }}
    summary {{
        list-style: none;
        cursor: pointer;
        outline: none;
    }}
    summary::-webkit-details-marker {{
        display: none;
    }}
    .summary-card {{
        border: 1px solid #d5dee9;
        border-radius: 10px;
        background: #ffffff;
        padding: 0.62rem 0.72rem;
        min-height: 84px;
        box-sizing: border-box;
    }}
    .summary-label {{
        color: #42566f;
        font-size: 0.9rem;
        margin-bottom: 0.15rem;
        font-weight: 600;
    }}
    .summary-value {{
        color: #142033;
        font-weight: 700;
        font-size: 1.2rem;
        line-height: 1.35;
        white-space: normal;
        word-break: break-word;
        overflow-wrap: anywhere;
    }}
    .summary-delta {{
        margin-top: 0.22rem;
        color: #42566f;
        font-size: 0.88rem;
    }}
    .summary-help {{
        margin-top: 0.42rem;
        padding: 0.5rem 0.7rem;
        border-left: 3px solid #1f4b99;
        background: #f8fbff;
        border-radius: 0 8px 8px 0;
        color: #42566f;
        font-size: 0.8rem;
        line-height: 1.35;
    }}
</style>
</head>
<body>
    <details title="{safe_description}">
        <summary>
            <div class="summary-card">
                <div class="summary-label">{safe_label}</div>
                <div class="summary-value">{safe_value}</div>
                {delta_block}
            </div>
        </summary>
        <div class="summary-help">{safe_description}</div>
    </details>
</body>
</html>
""",
        height=170,
        scrolling=False,
    )


def _quality_dataframe(generated: list) -> pd.DataFrame:
    if not generated:
        return pd.DataFrame()
    qual_df = pd.DataFrame(generated)
    if "score_qualite" not in qual_df.columns:
        return pd.DataFrame()
    qual_df["score_qualite"] = pd.to_numeric(qual_df["score_qualite"], errors="coerce")
    qual_df = qual_df.dropna(subset=["score_qualite"])
    return qual_df


def _generated_dataframe(generated: list) -> pd.DataFrame:
    """Normaliser les sorties de génération (legacy + topic-synthesis)."""
    if not generated:
        return pd.DataFrame()

    df = pd.DataFrame(generated)
    if df.empty:
        return df

    for col, default in {
        "topic_frequent": "non-defini",
        "resume_genere": "",
        "linkedin_post": "",
        "type_generation": "article-standard",
        "statut_generation": "N/D",
        "score_qualite": None,
    }.items():
        if col not in df.columns:
            df[col] = default

    df["score_qualite"] = pd.to_numeric(df["score_qualite"], errors="coerce")
    return df


def _article_search_text(row: pd.Series) -> str:
    parts = [
        row.get("titre_original", ""),
        row.get("contenu_genere", ""),
        row.get("resume_genere", ""),
        row.get("linkedin_post", ""),
        row.get("topic_frequent", ""),
        row.get("secteur_ia", ""),
        row.get("angle_editorial", ""),
        row.get("mots_cles", []),
    ]
    normalized_parts = []
    for part in parts:
        if isinstance(part, list):
            normalized_parts.extend(str(item) for item in part if str(item).strip())
        elif isinstance(part, str) and part.strip():
            normalized_parts.append(part)
    return " ".join(normalized_parts)


def _prepare_article_search_frame(generated: list) -> pd.DataFrame:
    df = _generated_dataframe(generated)
    if df.empty:
        return df

    if "score_qualite" not in df.columns:
        df["score_qualite"] = pd.NA
    df["score_qualite"] = pd.to_numeric(df["score_qualite"], errors="coerce")
    df["recherche_texte"] = df.apply(_article_search_text, axis=1)
    return df


def _normalize_structured_article(article: dict) -> dict:
    """Normaliser le payload structuré pour un rendu propre dans le tableau de bord."""
    if not isinstance(article, dict):
        return {}

    payload = article.get("contenu_structure")
    if not isinstance(payload, dict):
        return {}

    title = str(payload.get("title", "")).strip()
    introduction = str(payload.get("introduction", "")).strip()
    conclusion = str(payload.get("conclusion", "")).strip()

    sections = []
    raw_sections = payload.get("sections", [])
    if isinstance(raw_sections, list):
        for item in raw_sections:
            if isinstance(item, dict):
                sec_title = str(item.get("title", "")).strip()
                sec_content = str(item.get("content", "")).strip()
            else:
                sec_title = ""
                sec_content = str(item).strip()
            if sec_content:
                sections.append({"title": sec_title, "content": sec_content})

    insights = payload.get("insights", [])
    if not isinstance(insights, list):
        insights = []
    insights = [str(item).strip() for item in insights if str(item).strip()]

    if not title or not introduction or not conclusion:
        return {}

    return {
        "title": title,
        "introduction": introduction,
        "sections": sections,
        "conclusion": conclusion,
        "insights": insights,
    }


def _tokenize_search_text(text: str) -> list:
    tokens = re.findall(r"[a-zA-ZÀ-ÿ0-9]+", str(text or "").lower())
    stop_words = {
        "the", "and", "for", "with", "from", "that", "this", "are", "was", "were",
        "will", "into", "over", "after", "about", "have", "has", "had", "also", "more",
        "le", "la", "les", "de", "des", "du", "un", "une", "et", "en", "dans",
        "sur", "pour", "par", "au", "aux", "est", "sont", "ce", "cette", "ces",
    }
    return [token for token in tokens if len(token) > 2 and token not in stop_words]


def _cosine_score(tokens_a: list, tokens_b: list) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    counts_a = Counter(tokens_a)
    counts_b = Counter(tokens_b)
    shared = set(counts_a) & set(counts_b)
    dot_product = float(sum(counts_a[token] * counts_b[token] for token in shared))
    norm_a = math.sqrt(sum(value * value for value in counts_a.values()))
    norm_b = math.sqrt(sum(value * value for value in counts_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def _score_article_relevance(article_df: pd.DataFrame, query: str) -> pd.DataFrame:
    if article_df.empty:
        return article_df

    query_text = str(query or "").strip()
    scored_df = article_df.copy()
    if not query_text:
        scored_df["relevance_score"] = 0.0
        return scored_df

    corpus = scored_df["recherche_texte"].fillna("").astype(str).tolist()
    if not any(text.strip() for text in corpus):
        scored_df["relevance_score"] = 0.0
        return scored_df

    query_tokens = _tokenize_search_text(query_text)
    scored_df["relevance_score"] = [
        _cosine_score(_tokenize_search_text(value), query_tokens)
        for value in corpus
    ]

    query_token_set = set(query_tokens)

    def _matched_terms(value: str) -> str:
        if not query_token_set:
            return ""
        value_tokens = set(_tokenize_search_text(value))
        matches = [term for term in query_token_set if term in value_tokens]
        return ", ".join(matches[:5])

    scored_df["matched_terms"] = scored_df["recherche_texte"].apply(_matched_terms)
    return scored_df.sort_values(["relevance_score", "score_qualite"], ascending=[False, False])


def _related_articles(article_df: pd.DataFrame, row_index: int, top_n: int = 3) -> pd.DataFrame:
    if article_df.empty or row_index not in article_df.index:
        return pd.DataFrame()

    corpus = article_df["recherche_texte"].fillna("").astype(str).tolist()
    if len(corpus) < 2 or not any(text.strip() for text in corpus):
        return pd.DataFrame()

    position = article_df.index.get_loc(row_index)
    reference_tokens = _tokenize_search_text(corpus[position])
    candidate_df = article_df.copy()
    candidate_df["related_score"] = [
        _cosine_score(_tokenize_search_text(text), reference_tokens)
        for text in corpus
    ]
    candidate_df = candidate_df.drop(index=row_index, errors="ignore")
    candidate_df = candidate_df.sort_values("related_score", ascending=False).head(top_n)
    return candidate_df


def _topic_distribution_dataframe(generated_df: pd.DataFrame) -> pd.DataFrame:
    if generated_df.empty or "topic_frequent" not in generated_df.columns:
        return pd.DataFrame()
    topic_counts = generated_df["topic_frequent"].astype(str).value_counts().reset_index()
    topic_counts.columns = ["topic", "articles"]
    return topic_counts


def _quality_by_article_dataframe(generated: list) -> pd.DataFrame:
    if not generated:
        return pd.DataFrame()
    rows = []
    for i, article in enumerate(generated):
        rows.append(
            {
                "article": f"Article {i + 1}",
                "article_index": i,
                "score_qualite": article.get("score_qualite"),
            }
        )
    df = pd.DataFrame(rows)
    if "score_qualite" not in df.columns:
        return pd.DataFrame()
    df["score_qualite"] = pd.to_numeric(df["score_qualite"], errors="coerce")
    df = df.dropna(subset=["score_qualite"])
    return df


def _sector_dataframe(analysis: dict) -> pd.DataFrame:
    sectors = analysis.get("analyse_secteurs", {}).get("repartition_secteurs", {}) if analysis else {}
    if not sectors:
        return pd.DataFrame()
    sector_df = pd.DataFrame({"secteur": list(sectors.keys()), "articles": list(sectors.values())})
    sector_df = sector_df.sort_values("articles", ascending=False)
    return sector_df


def _pipeline_stage_dataframe(execution: dict) -> pd.DataFrame:
    if not execution:
        return pd.DataFrame()
    stages = execution.get("etapes", [])
    if not stages:
        return pd.DataFrame()
    rows = []
    for stage in stages:
        rows.append(
            {
                "etape": stage.get("etape", "N/D"),
                "statut": stage.get("statut", "N/D"),
                "duree_secondes": float(stage.get("duree_secondes", 0) or 0),
            }
        )
    return pd.DataFrame(rows)


def _quality_band_dataframe(qual_df: pd.DataFrame) -> pd.DataFrame:
    if qual_df.empty:
        return pd.DataFrame()
    bins = [0, 60, 75, 90, 100]
    labels = ["Faible (0-60)", "Correct (61-75)", "Bon (76-90)", "Excellent (91-100)"]
    band_series = pd.cut(qual_df["score_qualite"], bins=bins, labels=labels, include_lowest=True)
    counts = band_series.value_counts().reindex(labels, fill_value=0)
    return pd.DataFrame({"bande": counts.index, "articles": counts.values})


def _build_recommendations(analysis: dict, src_df: pd.DataFrame, qual_df: pd.DataFrame, exec_data: dict) -> list:
    reco = []

    if not src_df.empty and src_df["part"].iloc[0] > 0.35:
        dominant = src_df.iloc[0]["source"]
        reco.append(f"Réduire la dépendance à la source dominante: {dominant} (>35%).")

    if not qual_df.empty and float(qual_df["score_qualite"].mean()) < 80:
        reco.append("Renforcer la structure éditoriale (titre/chapeau/développements/impact/conclusion) pour augmenter la qualité moyenne.")

    if analysis:
        sectors = analysis.get("analyse_secteurs", {}).get("repartition_secteurs", {})
        if sectors and len(sectors) < 8:
            reco.append("Élargir les sujets couverts: la diversité sectorielle reste limitée.")

    if exec_data:
        failed_sources = 0
        for stage in exec_data.get("etapes", []):
            if stage.get("etape") == "collecte":
                failed_sources = int(stage.get("sources_en_echec", 0) or 0)
                break
        if failed_sources > 0:
            reco.append(f"Nettoyer les flux RSS en échec ({failed_sources}) pour stabiliser la collecte.")

    if not reco:
        reco.append("Le pipeline est globalement sain; priorité à l'optimisation de la vitesse de génération pour monter en volume.")

    return reco


def _status_label(value: float, good_threshold: float, watch_threshold: float, reverse: bool = False) -> str:
    """Retourner un statut simple: Bon / À surveiller / Critique."""
    if reverse:
        if value <= good_threshold:
            return "Bon"
        if value <= watch_threshold:
            return "À surveiller"
        return "Critique"

    if value >= good_threshold:
        return "Bon"
    if value >= watch_threshold:
        return "À surveiller"
    return "Critique"


analysis_data = load_data("output/analysis_kpis.json")
generated_data = load_data("output/generated_articles.json")
execution_data = load_data("pipeline_execution_results.json")
generated_df = _generated_dataframe(generated_data)


st.markdown(
    """
<div class="app-shell">
    <div class="title-block">
        <h1>Pipeline de génération de contenu automatisé</h1>
        <p>Mini système de production IA pour la veille, l'analyse et la génération de contenu.</p>
        <div class="chip-row">
            <span class="chip">Génération de contenu</span>
            <span class="chip">Articles et publications</span>
            <span class="chip">Système de production IA</span>
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

nav_options = ["Tableau de bord", "Articles générés", "À propos"]
st.markdown('<div class="nav-shell">', unsafe_allow_html=True)
page = st.radio("Navigation", nav_options, index=0, horizontal=True, label_visibility="collapsed")
st.markdown('</div>', unsafe_allow_html=True)


if page == "Tableau de bord":
    exec_col1, exec_col2, exec_col3, exec_col4 = st.columns(4)
    with exec_col1:
        if st.button("Exécuter le pipeline complet", type="primary", use_container_width=True):
            run_full_pipeline_from_ui()

    with exec_col2:
        if st.button("Exécuter l'analyse seule", use_container_width=True):
            try:
                from src.config import ANALYSIS_FILE, CLEANED_DATA_FILE
                from src.data_analysis import DataAnalyzer

                analyzer = DataAnalyzer()
                df = analyzer.load_cleaned_data(str(CLEANED_DATA_FILE))
                report = analyzer.generate_report(df)
                analyzer.save_report(report, str(ANALYSIS_FILE))
                st.success("Analyse exécutée avec succès.")
            except Exception as e:
                st.error(f"Échec de l'analyse: {str(e)}")

    with exec_col3:
        if st.button("Générer des articles", use_container_width=True):
            try:
                from src.automation_pipeline import AutomationPipeline

                with st.spinner("Génération de la synthèse par thèmes en cours..."):
                    pipeline = AutomationPipeline()
                    result = pipeline.run_generation_stage()

                if result.get("statut") == "succes":
                    st.success(
                        f"Génération terminée: {result.get('articles_generes', 0)} article(s) sur "
                        f"{result.get('nombre_topics_selectionnes', 0)} thème(s)."
                    )
                else:
                    st.warning(f"Génération non finalisée: {result.get('statut', 'N/D')}")
                st.json(result)
            except Exception as e:
                st.error(f"Échec de la génération d'articles: {str(e)}")

    with exec_col4:
        if st.button("Actualiser", use_container_width=True):
            st.rerun()

    st.markdown('<div class="section-label">Aperçu instantané</div>', unsafe_allow_html=True)
    status_col1, status_col2, status_col3, status_col4 = st.columns(4)
    last_update_label = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_run_status = execution_data.get("statut_pipeline", "N/D") if execution_data else "N/D"
    status_label_map = {
        "termine": "Terminé",
        "terminé": "Terminé",
        "succes": "Succès",
        "succès": "Succès",
        "echec": "Échec",
        "échec": "Échec",
        "en_cours": "En cours",
        "en cours": "En cours",
    }
    status_key = str(last_run_status).strip().lower()
    display_run_status = status_label_map.get(status_key, str(last_run_status))
    if execution_data and execution_data.get("duree_secondes") is not None:
        last_run_duration = f"{float(execution_data.get('duree_secondes', 0) or 0):.1f} s"
    else:
        last_run_duration = "N/D"

    st.markdown('<div class="kpi-panel">', unsafe_allow_html=True)
    with status_col1:
        _render_clickable_stat_card(
            "État du système",
            "Actif",
            description="Indique si l'application est disponible et prête à être utilisée.",
        )
    with status_col2:
        _render_clickable_stat_card(
            "Dernière mise à jour",
            last_update_label,
            description="Horodatage de la dernière actualisation automatique des données affichées.",
        )
    with status_col3:
        _render_clickable_stat_card(
            "Statut du dernier run",
            display_run_status,
            description="Résultat de la dernière exécution du pipeline: terminé, en cours, succès ou échec.",
        )
    with status_col4:
        _render_clickable_stat_card(
            "Durée du dernier run",
            last_run_duration,
            description="Temps total nécessaire pour compléter la dernière exécution du pipeline.",
        )
    st.markdown('</div>', unsafe_allow_html=True)

    m1, m2, m3 = st.columns(3)
    if analysis_data:
        stats = analysis_data.get("statistiques_base", {})
        source_stats = analysis_data.get("analyse_sources", {})
        trend_up = analysis_data.get("analyse_tendances", {}).get("tendance_haussiere", False)
        trend_label = "Hausse" if trend_up else "Stable/Baisse"

        st.markdown('<div class="kpi-panel">', unsafe_allow_html=True)
        with m1:
            _render_clickable_stat_card(
                "Articles totaux",
                stats.get("articles_totaux", "N/D"),
                description="Nombre total d'articles disponibles dans le corpus analysé.",
            )
        with m2:
            _render_clickable_stat_card(
                "Sources uniques",
                source_stats.get("sources_uniques", "N/D"),
                description="Nombre de sources distinctes utilisées pour alimenter les analyses.",
            )
        with m3:
            _render_clickable_stat_card(
                "Signal tendance",
                trend_label,
                description="Lecture synthétique de la tendance globale observée sur les derniers jours.",
            )
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.warning("Aucune donnée d'analyse trouvée. Lancez le pipeline pour générer les sorties.")

    trend_df = _trend_dataframe(analysis_data)
    src_df = _source_dataframe(analysis_data)
    sector_df = _sector_dataframe(analysis_data)
    qual_df = _quality_dataframe(generated_df.to_dict("records"))
    quality_article_df = _quality_by_article_dataframe(generated_df.to_dict("records"))
    topic_df = _topic_distribution_dataframe(generated_df)
    stage_df = _pipeline_stage_dataframe(execution_data)

    st.markdown('<div class="section-label">Résumé exécutif</div>', unsafe_allow_html=True)
    summary_col1, summary_col2, summary_col3 = st.columns([1.2, 1, 1])
    with summary_col1:
        if execution_data:
            exec_status_raw = str(execution_data.get("statut_pipeline", "N/D")).strip().lower()
            exec_status = status_label_map.get(exec_status_raw, str(execution_data.get("statut_pipeline", "N/D")))
            exec_duration = round(float(execution_data.get("duree_secondes", 0) or 0), 1)
            _render_clickable_stat_card(
                "Exécution",
                execution_data.get("run_id", "N/D"),
                f"Statut: {exec_status} | Durée: {exec_duration} s",
                description="Identifiant de la dernière exécution avec son statut et sa durée complète.",
            )
        else:
            _render_clickable_stat_card(
                "Exécution",
                "N/D",
                "Aucun journal d'exécution détecté",
                description="Aucun historique d'exécution n'est disponible pour le moment.",
            )
    with summary_col2:
        if not src_df.empty:
            top_source = src_df.iloc[0]
            _render_clickable_stat_card(
                "Source dominante",
                str(top_source["source"]),
                f"Part: {top_source['part'] * 100:.1f}%",
                description="Source la plus représentée dans le corpus et son poids relatif.",
            )
    with summary_col3:
        if not sector_df.empty:
            top_sector = sector_df.iloc[0]
            _render_clickable_stat_card(
                "Secteur dominant",
                top_sector["secteur"],
                f"Articles: {int(top_sector['articles'])}",
                description="Secteur qui concentre le plus grand volume d'articles dans l'analyse.",
            )

    st.markdown('<div class="section-label">Tableau KPI</div>', unsafe_allow_html=True)
    scorecard_col1, scorecard_col2, scorecard_col3, scorecard_col4 = st.columns(4)

    freshness_24h = 0.0
    source_hhi = 0.0
    keyword_signal = 0.0
    trend_growth = 0.0
    if analysis_data:
        freshness_24h = float(analysis_data.get("statistiques_base", {}).get("fraicheur", {}).get("taux_24h_pct", 0) or 0)
        source_hhi = float(analysis_data.get("analyse_sources", {}).get("concentration", {}).get("hhi", 0) or 0)
        keyword_signal = float(analysis_data.get("analyse_mots_cles", {}).get("qualite_signal", {}).get("signal_pct", 0) or 0)
        trend_growth = float(analysis_data.get("analyse_tendances", {}).get("croissance_7j_pct", 0) or 0)

    freshness_status = _status_label(freshness_24h, good_threshold=60, watch_threshold=35)
    concentration_status = _status_label(source_hhi, good_threshold=0.10, watch_threshold=0.16, reverse=True)
    signal_status = _status_label(keyword_signal, good_threshold=85, watch_threshold=70)
    growth_status = _status_label(trend_growth, good_threshold=15, watch_threshold=0)

    with scorecard_col1:
        _render_clickable_stat_card(
            "Fraîcheur 24h",
            f"{freshness_24h:.1f}%",
            freshness_status,
            description="Pourcentage d'articles publiés au cours des dernières 24 heures.",
        )
    with scorecard_col2:
        _render_clickable_stat_card(
            "Concentration HHI",
            f"{source_hhi:.3f}",
            concentration_status,
            description="Indice de concentration des sources: plus il est élevé, plus quelques sources dominent le corpus.",
        )
    with scorecard_col3:
        _render_clickable_stat_card(
            "Qualité du signal",
            f"{keyword_signal:.1f}%",
            signal_status,
            description="Part estimée du contenu utile par rapport au bruit dans l'analyse des mots-clés.",
        )
    with scorecard_col4:
        _render_clickable_stat_card(
            "Croissance 7j",
            f"{trend_growth:.1f}%",
            growth_status,
            description="Variation du volume d'articles sur les sept derniers jours.",
        )

    st.markdown('<div class="section-label">Pilotage opérationnel</div>', unsafe_allow_html=True)
    ops_col1, ops_col2 = st.columns([1.2, 1])
    with ops_col1:
        st.markdown('<div class="plot-title">Santé du pipeline</div>', unsafe_allow_html=True)
        if not stage_df.empty:
            stage_df = stage_df.copy()
            stage_df["duree_cumulee_secondes"] = stage_df["duree_secondes"].cumsum()

            total_runtime = float(
                execution_data.get("duree_secondes", stage_df["duree_cumulee_secondes"].iloc[-1])
            ) if execution_data else float(stage_df["duree_cumulee_secondes"].iloc[-1])

            st.caption(
                f"Temps total d'exécution: {total_runtime:.2f} s ({total_runtime / 60:.2f} min)"
            )

            status_color = {
                "succes": PALETTE["primary"],
                "echec": PALETTE["danger"],
                "ignore": PALETTE["accent"],
            }
            stage_fig = go.Figure()
            stage_fig.add_trace(
                go.Bar(
                    x=stage_df["etape"],
                    y=stage_df["duree_secondes"],
                    name="Temps par étape",
                    marker_color=[status_color.get(s, PALETTE["neutral"]) for s in stage_df["statut"]],
                    text=stage_df["statut"],
                    textposition="outside",
                )
            )
            stage_fig.add_trace(
                go.Bar(
                    x=stage_df["etape"],
                    y=stage_df["duree_cumulee_secondes"],
                    name="Temps cumulé",
                    marker_color="rgba(31, 75, 153, 0.25)",
                    text=[f"{value:.1f}s" for value in stage_df["duree_cumulee_secondes"]],
                    textposition="inside",
                )
            )
            stage_fig.update_layout(
                template="plotly_white",
                height=340,
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis_title="Étape",
                yaxis_title="Durée (s)",
                barmode="overlay",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(stage_fig, use_container_width=True)
        else:
            st.info("Aucune métrique d'exécution disponible.")

    with ops_col2:
        st.markdown('<div class="plot-title">Évolution quotidienne</div>', unsafe_allow_html=True)
        st.markdown('<div class="plot-subtitle">Tendance des volumes publiés par jour.</div>', unsafe_allow_html=True)
        if not trend_df.empty:
            trend_fig = go.Figure()
            trend_fig.add_trace(
                go.Scatter(
                    x=trend_df["date"],
                    y=trend_df["articles"],
                    mode="lines+markers",
                    line=dict(color=PALETTE["primary"], width=3),
                    marker=dict(size=7, color=PALETTE["accent"]),
                    fill="tozeroy",
                    fillcolor="rgba(27,107,99,0.14)",
                    name="Articles"
                )
            )
            trend_fig.update_layout(
                template="plotly_white",
                height=340,
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis_title="Date",
                yaxis_title="Articles"
            )
            st.plotly_chart(trend_fig, use_container_width=True)
        else:
            st.info("Aucune série temporelle disponible.")

    st.markdown('<div class="section-label">Performance de génération</div>', unsafe_allow_html=True)
    perf_col1, perf_col2 = st.columns(2)
    with perf_col1:
        st.markdown('<div class="plot-title">Thèmes principaux</div>', unsafe_allow_html=True)
        st.markdown('<div class="plot-subtitle">Thèmes les plus couverts dans la génération.</div>', unsafe_allow_html=True)
        if not generated_df.empty and "topic_frequent" in generated_df.columns:
            if "articles_sources_topic" in generated_df.columns:
                top_topics_df = (
                    generated_df[["topic_frequent", "articles_sources_topic"]]
                    .copy()
                    .rename(columns={"topic_frequent": "topic", "articles_sources_topic": "articles_scrappes"})
                )
                top_topics_df["articles_scrappes"] = pd.to_numeric(top_topics_df["articles_scrappes"], errors="coerce").fillna(0)
                top_topics_df = (
                    top_topics_df.groupby("topic", as_index=False)["articles_scrappes"]
                    .max()
                    .sort_values("articles_scrappes", ascending=False)
                )
            else:
                top_topics_df = generated_df["topic_frequent"].astype(str).value_counts().reset_index()
                top_topics_df.columns = ["topic", "articles_scrappes"]

            if not top_topics_df.empty:
                topic_fig = px.bar(
                    top_topics_df,
                    x="articles_scrappes",
                    y="topic",
                    orientation="h",
                    color="articles_scrappes",
                    color_continuous_scale="Teal",
                    text="articles_scrappes",
                )
                topic_fig.update_layout(
                    template="plotly_white",
                    height=330,
                    margin=dict(l=20, r=20, t=20, b=20),
                    xaxis_title="Nombre d'articles scrapés",
                    yaxis_title="Thème",
                    coloraxis_showscale=False,
                )
                st.plotly_chart(topic_fig, use_container_width=True)
            else:
                st.info("Aucun thème disponible pour l'affichage.")
        else:
            st.info("Les thèmes principaux apparaîtront après la génération par synthèse.")

    with perf_col2:
        st.markdown('<div class="plot-title">Scores de génération par article</div>', unsafe_allow_html=True)
        st.markdown('<div class="plot-subtitle">Niveau de qualité de chaque article.</div>', unsafe_allow_html=True)
        if not quality_article_df.empty:
            score_fig = px.bar(
                quality_article_df,
                x="score_qualite",
                y="article",
                orientation="h",
                color="score_qualite",
                color_continuous_scale="Teal",
                text="score_qualite",
            )
            score_fig.update_layout(
                template="plotly_white",
                height=330,
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis_title="Score qualité",
                yaxis_title="Articles",
                coloraxis_showscale=False,
            )
            score_fig.update_xaxes(range=[0, 100])
            st.plotly_chart(score_fig, use_container_width=True)
        else:
            st.info("Le score de qualité apparaîtra après une génération récente.")

    st.markdown('<div class="section-label">Couverture et concentration</div>', unsafe_allow_html=True)
    coverage_col1, coverage_col2 = st.columns(2)
    with coverage_col1:
        st.markdown('<div class="plot-title">Répartition des sources</div>', unsafe_allow_html=True)
        st.markdown('<div class="plot-subtitle">Poids relatif de chaque source.</div>', unsafe_allow_html=True)
        if not src_df.empty:
            src_fig = px.pie(
                src_df,
                values="articles",
                names="source",
                hole=0.58,
                color_discrete_sequence=["#1b6b63", "#2d5ea6", "#c26a32", "#7f8f85", "#a3b4ab"]
            )
            src_fig.update_layout(
                template="plotly_white",
                height=360,
                margin=dict(l=20, r=20, t=20, b=20),
                showlegend=False,
            )
            st.plotly_chart(src_fig, use_container_width=True)
        else:
            st.info("Aucune distribution source disponible.")

    with coverage_col2:
        st.markdown('<div class="plot-title">Concentration des sources (Pareto)</div>', unsafe_allow_html=True)
        st.markdown('<div class="plot-subtitle">Cumul de contribution des sources majeures.</div>', unsafe_allow_html=True)
        pareto_src_df = _source_dataframe(analysis_data)
        if not pareto_src_df.empty:
            pareto_fig = go.Figure()
            pareto_fig.add_trace(
                go.Bar(
                    x=pareto_src_df["source"],
                    y=pareto_src_df["articles"],
                    name="Volume",
                    marker_color=PALETTE["primary"],
                )
            )
            pareto_fig.add_trace(
                go.Scatter(
                    x=pareto_src_df["source"],
                    y=pareto_src_df["part_cumulee"] * 100,
                    mode="lines+markers",
                    name="Part cumulée",
                    yaxis="y2",
                    line=dict(color=PALETTE["accent"], width=2.5),
                )
            )
            pareto_fig.update_layout(
                template="plotly_white",
                height=360,
                margin=dict(l=20, r=20, t=20, b=20),
                yaxis=dict(title="Articles"),
                yaxis2=dict(title="Part cumulée (%)", overlaying="y", side="right", range=[0, 110]),
                xaxis_title="Source",
            )
            st.plotly_chart(pareto_fig, use_container_width=True)
        else:
            st.info("Aucune source à analyser.")

    st.markdown('<div class="section-label">Analyse du contenu</div>', unsafe_allow_html=True)
    content_col1, content_col2 = st.columns(2)
    with content_col1:
        st.markdown('<div class="plot-title">Répartition sectorielle</div>', unsafe_allow_html=True)
        st.markdown('<div class="plot-subtitle">Distribution des articles par secteur.</div>', unsafe_allow_html=True)
        if not sector_df.empty:
            sector_fig = px.bar(
                sector_df.head(12),
                x="articles",
                y="secteur",
                orientation="h",
                color="articles",
                color_continuous_scale="Teal",
            )
            sector_fig.update_layout(
                template="plotly_white",
                height=330,
                margin=dict(l=20, r=20, t=20, b=20),
                yaxis_title="Secteur",
                xaxis_title="Articles",
            )
            st.plotly_chart(sector_fig, use_container_width=True)
        else:
            st.info("Aucune analyse sectorielle disponible.")

    with content_col2:
        st.markdown('<div class="plot-title">Qualité du signal mots-clés</div>', unsafe_allow_html=True)
        st.markdown('<div class="plot-subtitle">Part de signal utile versus bruit.</div>', unsafe_allow_html=True)
        signal_data = analysis_data.get("analyse_mots_cles", {}).get("qualite_signal", {}) if analysis_data else {}
        signal_pct = float(signal_data.get("signal_pct", 0) or 0)
        noise_pct = float(signal_data.get("bruit_pct", 0) or 0)
        if signal_pct > 0 or noise_pct > 0:
            signal_fig = px.pie(
                values=[signal_pct, noise_pct],
                names=["Signal", "Bruit"],
                hole=0.6,
                color=["Signal", "Bruit"],
                color_discrete_map={"Signal": PALETTE["primary"], "Bruit": PALETTE["danger"]},
            )
            signal_fig.update_traces(textposition="inside", textinfo="percent+label")
            signal_fig.update_layout(
                template="plotly_white",
                height=330,
                margin=dict(l=20, r=20, t=20, b=20),
                showlegend=False,
            )
            st.plotly_chart(signal_fig, use_container_width=True)
        else:
            st.info("Aucune mesure signal/bruit disponible.")

    st.markdown('<div class="plot-title">Principaux mots-clés</div>', unsafe_allow_html=True)
    st.markdown('<div class="plot-subtitle">Mots-clés les plus fréquents dans le corpus.</div>', unsafe_allow_html=True)
    keywords = analysis_data.get("analyse_mots_cles", {}).get("mots_cles_principaux", {}) if analysis_data else {}
    if keywords:
        sorted_keywords = sorted(keywords.items(), key=lambda item: item[1], reverse=True)[:15]
        keyword_labels = [item[0] for item in sorted_keywords]
        keyword_values = [item[1] for item in sorted_keywords]
        keywords_fig = go.Figure(
            data=[
                go.Bar(
                    y=keyword_labels,
                    x=keyword_values,
                    orientation="h",
                    marker_color=PALETTE["primary"],
                )
            ]
        )
        keywords_fig.update_layout(
            xaxis_title="Fréquence",
            yaxis_title="Mot-clé",
            template="plotly_white",
            height=420,
            margin=dict(l=20, r=20, t=20, b=20),
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(keywords_fig, use_container_width=True)
    else:
        st.info("Aucun mot-clé disponible.")

    st.markdown('<div class="section-label">Points clés</div>', unsafe_allow_html=True)
    if analysis_data and "insights_metier" in analysis_data:
        for insight in analysis_data["insights_metier"]:
            st.markdown(f'<div class="insight-card">{insight}</div>', unsafe_allow_html=True)
    else:
        st.info("Les points clés apparaîtront ici après la création du rapport d'analyse.")

elif page == "Articles générés":
    st.markdown('<div class="section-label">Articles générés</div>', unsafe_allow_html=True)
    if not generated_df.empty:
        search_df = _prepare_article_search_frame(generated_df.to_dict("records"))
        display_limit = min(len(search_df), max(10, GENERATED_ARTICLES_LIMIT))
        st.caption(f"Affichage de {display_limit} article(s) sur {len(search_df)}.")

        search_col1, search_col2, search_col3 = st.columns([1.6, 1, 1])
        with search_col1:
            search_query = st.text_input(
                "Rechercher dans les articles",
                placeholder="Ex: chaîne logistique, énergie, automatisation, IA industrielle...",
            )
        with search_col2:
            topic_options = ["Tous"] + sorted(search_df["topic_frequent"].astype(str).unique().tolist())
            selected_topic = st.selectbox("Filtrer par thème", topic_options, index=0)
        with search_col3:
            sort_choice = st.selectbox(
                "Trier par",
                ["Pertinence", "Score qualité", "Plus récent"],
                index=0,
            )

        filtered_df = search_df.copy()
        if selected_topic != "Tous":
            filtered_df = filtered_df[filtered_df["topic_frequent"].astype(str) == selected_topic]

        if "publication_originale" in filtered_df.columns:
            filtered_df["publication_originale_dt"] = pd.to_datetime(filtered_df["publication_originale"], errors="coerce")
        else:
            filtered_df["publication_originale_dt"] = pd.NaT

        filtered_df = _score_article_relevance(filtered_df, search_query)

        if sort_choice == "Score qualité":
            filtered_df = filtered_df.sort_values(["score_qualite", "relevance_score"], ascending=[False, False])
        elif sort_choice == "Plus récent":
            filtered_df = filtered_df.sort_values(["publication_originale_dt", "relevance_score"], ascending=[False, False])

        if search_query.strip():
            top_matches = filtered_df[filtered_df["relevance_score"] > 0].head(display_limit)
        else:
            top_matches = filtered_df.head(display_limit)

        st.markdown('<div class="kpi-panel">', unsafe_allow_html=True)
        summary_cols = st.columns(4)
        with summary_cols[0]:
            st.metric("Articles générés", len(filtered_df))
        with summary_cols[1]:
            st.metric("Correspondances pertinentes", len(top_matches))
        with summary_cols[2]:
            avg_score = float(filtered_df["score_qualite"].dropna().mean()) if not filtered_df.empty and filtered_df["score_qualite"].notna().any() else 0.0
            st.metric("Score moyen", f"{avg_score:.1f}" if avg_score else "N/D")
        with summary_cols[3]:
            st.metric("Thèmes visibles", filtered_df["topic_frequent"].astype(str).nunique())
        st.markdown('</div>', unsafe_allow_html=True)

        if search_query.strip() and not top_matches.empty:
            st.markdown('<div class="section-label">Résultats de recherche</div>', unsafe_allow_html=True)
            for _, result_row in top_matches.head(display_limit).iterrows():
                topic_txt = str(result_row.get("topic_frequent", "N/D"))
                title_txt = str(result_row.get("titre_original", "Sans titre"))
                score_val = result_row.get("score_qualite")
                score_txt = f"{float(score_val):.0f}" if pd.notna(score_val) else "N/D"
                rel_txt = f"{float(result_row.get('relevance_score', 0) or 0):.3f}"
                common_txt = str(result_row.get("matched_terms", "")).strip() or "-"
                st.markdown(
                    f"- Thème: **{topic_txt}** | Titre: **{title_txt}** | Score: **{score_txt}** | Pertinence: **{rel_txt}** | Mots communs: {common_txt}"
                )

        for i, row in top_matches.head(display_limit).iterrows():
            article = row.to_dict()
            topic_name = str(article.get("topic_frequent", "N/D"))
            title = article.get("titre_original", "Sans titre")
            score = article.get("score_qualite")
            score_text = f"{score:.0f}" if pd.notna(score) else "N/D"
            relevance = float(article.get("relevance_score", 0) or 0)
            relevance_text = f"{relevance:.3f}" if search_query.strip() else "N/D"

            with st.expander(f"{topic_name.title()} | {title}"):
                st.markdown(
                    f"""
<div class="article-block">
    <h4>{title}</h4>
    <div class="article-meta">Source: {article.get('source_originale', 'N/D')} | Publication: {article.get('publication_originale', 'N/D')} | Statut: {article.get('statut_generation', 'N/D')} | Score: {score_text} | Pertinence: {relevance_text}</div>
    <div class="article-meta">Type de génération: {article.get('type_generation', 'N/D')} | Sources du sujet: {article.get('articles_sources_topic', 'N/D')} | Fournisseur: {article.get('source_llm', 'N/D')}</div>
</div>
""",
                    unsafe_allow_html=True,
                )

                structured_view = _normalize_structured_article(article)
                st.markdown("Contenu généré")
                if structured_view:
                    st.markdown(f"### **{structured_view.get('title', 'Sans titre')}**")
                    _render_justified_text(structured_view.get("introduction", ""))

                    for section_index, section in enumerate(structured_view.get("sections", []), start=1):
                        section_title = section.get("title", "").strip() or f"Section {section_index}"
                        st.markdown(f"**{section_index}. {section_title}**")
                        _render_justified_text(section.get("content", ""))

                    st.markdown("**Conclusion**")
                    _render_justified_text(structured_view.get("conclusion", ""))

                    if structured_view.get("insights"):
                        st.markdown("**Points clés**")
                        for insight in structured_view["insights"]:
                            st.markdown(f"- {insight}")
                else:
                    st.markdown(f"### **{title}**")
                    _render_justified_text(article.get("contenu_genere", "Aucun contenu généré disponible."))

                if st.button("Détails", key=f"details_{i}"):
                    st.json(article)

                resume = str(article.get("resume_genere", "")).strip()
                if resume:
                    st.markdown("Résumé")
                    _render_justified_text(resume)

                linkedin_post = str(article.get("linkedin_post", "")).strip()
                if linkedin_post:
                    st.markdown("Publication LinkedIn")
                    _render_justified_text(linkedin_post, css_class="linkedin-card")

                related_df = _related_articles(top_matches, i, top_n=3)
                if not related_df.empty:
                    st.markdown("Articles proches")
                    for _, related in related_df.iterrows():
                        related_score = float(related.get("related_score", 0) or 0)
                        st.markdown(
                            f"- **{related.get('titre_original', 'Sans titre')}** · {related.get('topic_frequent', 'N/D')} · similarité {related_score:.3f}"
                        )
    else:
        st.warning("Aucun fichier d'articles générés trouvé. Lancez d'abord le pipeline.")

elif page == "À propos":
    st.markdown('<div class="section-label">À propos de ce projet</div>', unsafe_allow_html=True)
    st.markdown(
        """
Ce tableau de bord pilote un Pipeline de génération de contenu automatisé pour :

- la collecte de données RSS,
- le nettoyage et la structuration des données,
- l'extraction de KPI et l'analyse des tendances,
- la génération assistée de contenus et leur enrichissement IA.

L'objectif est d'aider les équipes éditoriales et communication à produire plus vite des contenus pilotés par la donnée, avec une automatisation fiable.
"""
    )


st.divider()
st.markdown('<div class="footnote">Pipeline de génération de contenu automatisé | Tableau de bord v1.0 | 2026</div>', unsafe_allow_html=True)
