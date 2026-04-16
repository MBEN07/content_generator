"""Module d'analyse des donnees et de production d'insights."""

import json
import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime
from collections import Counter
import unicodedata
import re
import logging
from src.config import TREND_WINDOW_DAYS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataAnalyzer:
    """Realise l'EDA et l'extraction de KPI."""
    
    def __init__(self):
        self.kpis = {}
        self.insights = []
        self.stop_words_fr = {
            "le", "la", "les", "de", "des", "du", "un", "une", "et", "en", "dans",
            "sur", "pour", "par", "au", "aux", "est", "sont", "ce", "cette", "ces",
            "avec", "plus", "apres", "avant", "dans", "vers", "comme", "dont", "que",
            "qui", "se", "sa", "son", "ses", "leur", "leurs", "il", "elle", "ils", "elles"
        }
        self.stop_words_en = {
            "the", "and", "for", "with", "from", "that", "this", "are", "was", "were",
            "will", "into", "over", "after", "about", "have", "has", "had", "also", "more"
        }
        self.generic_noise_tokens = {
            "news", "world", "from", "says", "today", "update", "latest", "breaking",
            "infos", "actualite", "derniere", "monde", "aujourd'hui", "alerte"
        }

    @staticmethod
    def _safe_numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
        if column not in df.columns:
            return pd.Series(dtype='float64')
        return pd.to_numeric(df[column], errors='coerce').dropna()
    
    def load_cleaned_data(self, filepath: str) -> pd.DataFrame:
        """Charger les donnees nettoyees depuis un fichier JSON."""
        df = pd.read_json(filepath)
        return df

    @staticmethod
    def _normalize_unicode_text(text: str) -> str:
        if not isinstance(text, str):
            return ""
        normalized = unicodedata.normalize("NFKC", text).lower()
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized
    
    def analyze_basic_statistics(self, df: pd.DataFrame) -> Dict:
        """Extraire les statistiques de base."""
        mots = self._safe_numeric_series(df, 'nombre_mots')
        caracteres = self._safe_numeric_series(df, 'nombre_caracteres')
        dates = pd.to_datetime(df['publie'], errors='coerce', utc=True) if 'publie' in df.columns else pd.Series(dtype='datetime64[ns, UTC]')
        now_utc = pd.Timestamp.utcnow()
        freshness_24h = 0.0
        freshness_72h = 0.0
        valid_dates_count = int(dates.notna().sum()) if len(dates) > 0 else 0
        if valid_dates_count > 0:
            freshness_24h = float(((now_utc - dates).dt.total_seconds() <= 24 * 3600).fillna(False).mean() * 100)
            freshness_72h = float(((now_utc - dates).dt.total_seconds() <= 72 * 3600).fillna(False).mean() * 100)

        stats = {
            "articles_totaux": int(len(df)),
            "moyenne_mots": float(mots.mean()) if not mots.empty else 0.0,
            "mediane_mots": float(mots.median()) if not mots.empty else 0.0,
            "moyenne_caracteres": float(caracteres.mean()) if not caracteres.empty else 0.0,
            "plage_dates": {
                "premiere": str(dates.min() if valid_dates_count > 0 else "N/D"),
                "derniere": str(dates.max() if valid_dates_count > 0 else "N/D")
            },
            "fraicheur": {
                "taux_24h_pct": freshness_24h,
                "taux_72h_pct": freshness_72h,
                "dates_valides": valid_dates_count,
            },
        }
        self.kpis['statistiques_base'] = stats
        logger.info(f"Statistiques de base: {stats['articles_totaux']} articles analyses")
        return stats
    
    def analyze_sources(self, df: pd.DataFrame) -> Dict:
        """Analyser la distribution par source."""
        if 'source' not in df.columns:
            source_stats = {
                "sources_uniques": 0,
                "sources_principales": {},
                "toutes_sources": {},
                "concentration": {
                    "top_source_part_pct": 0.0,
                    "hhi": 0.0,
                    "niveau": "faible",
                },
            }
            self.kpis['analyse_sources'] = source_stats
            return source_stats

        source_counts = df['source'].value_counts().to_dict()
        total_articles = max(int(len(df)), 1)
        sorted_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)
        top_source_share_pct = float((sorted_sources[0][1] / total_articles) * 100) if sorted_sources else 0.0
        shares = [(count / total_articles) for _, count in sorted_sources]
        hhi = float(sum(s * s for s in shares))

        if hhi < 0.08:
            concentration_level = "faible"
        elif hhi < 0.16:
            concentration_level = "moderee"
        else:
            concentration_level = "elevee"

        source_stats = {
            "sources_uniques": int(len(source_counts)),
            "sources_principales": dict(sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:5]),
            "toutes_sources": source_counts,
            "concentration": {
                "top_source_part_pct": top_source_share_pct,
                "hhi": hhi,
                "niveau": concentration_level,
            },
        }
        self.kpis['analyse_sources'] = source_stats
        logger.info(f"Analyse des sources: {len(source_counts)} sources uniques")
        return source_stats

    def analyze_sectors(self, df: pd.DataFrame) -> Dict:
        """Analyser la repartition du contenu."""
        if 'secteur_estime' not in df.columns:
            sector_stats = {"secteurs_uniques": 0, "repartition_secteurs": {}}
            self.kpis['analyse_secteurs'] = sector_stats
            return sector_stats

        counts = df['secteur_estime'].value_counts().to_dict()
        sector_stats = {
            "secteurs_uniques": int(len(counts)),
            "repartition_secteurs": counts,
        }
        self.kpis['analyse_secteurs'] = sector_stats
        return sector_stats
    
    def analyze_keywords(self, df: pd.DataFrame, top_n: int = 20) -> Dict:
        """Extraire et analyser les principaux mots-cles."""
        # Extraire les tags/mots-cles
        all_keywords: List[str] = []
        if 'etiquettes' in df.columns:
            for tags in df['etiquettes']:
                if isinstance(tags, list):
                    all_keywords.extend([str(t).lower() for t in tags if str(t).strip()])
        
        # Extraire aussi les mots frequents des titres
        words: List[str] = []
        if 'titre' in df.columns:
            for title in df['titre']:
                if isinstance(title, str):
                    cleaned_title = self._normalize_unicode_text(title)
                    words.extend(cleaned_title.split())

        merged_tokens = []
        for token in all_keywords + words:
            tok = self._normalize_unicode_text(str(token))
            parts = re.findall(r"[\wÀ-ÿ]+", tok, flags=re.UNICODE)
            for part in parts:
                normalized_part = self._normalize_unicode_text(part)
                if len(normalized_part) <= 3:
                    continue
                if normalized_part in self.stop_words_fr or normalized_part in self.stop_words_en:
                    continue
                merged_tokens.append(normalized_part)
        
        keyword_counts = Counter(merged_tokens).most_common(top_n)
        keyword_dict = dict(keyword_counts)

        total_keywords = max(len(merged_tokens), 1)
        noise_count = sum(1 for t in merged_tokens if t in self.generic_noise_tokens)
        noise_ratio_pct = float((noise_count / total_keywords) * 100)
        signal_ratio_pct = float(100 - noise_ratio_pct)
        
        keyword_stats = {
            "total_mots_cles_uniques": len(keyword_dict),
            "mots_cles_principaux": keyword_dict,
            "frequence_mots_cles": keyword_dict,
            "qualite_signal": {
                "bruit_pct": noise_ratio_pct,
                "signal_pct": signal_ratio_pct,
            },
        }
        self.kpis['analyse_mots_cles'] = keyword_stats
        logger.info(f"Analyse des mots-cles: {len(keyword_dict)} mots-cles extraits")
        return keyword_stats
    
    def identify_trends(self, df: pd.DataFrame) -> Dict:
        """Identifier les tendances emergentes."""
        # Regrouper par date pour observer l'evolution
        if 'publie' in df.columns:
            try:
                dates = pd.to_datetime(df['publie'], errors='coerce', utc=True)
                dates_valides = dates.dropna()
                if dates_valides.empty:
                    trend_analysis = {"note": "Aucune date exploitable pour l'analyse des tendances"}
                    self.kpis['analyse_tendances'] = trend_analysis
                    return trend_analysis

                date_max = dates_valides.max()
                borne_basse = date_max - pd.Timedelta(days=TREND_WINDOW_DAYS)
                dates_fenetrees = dates_valides[dates_valides >= borne_basse]
                if dates_fenetrees.empty:
                    dates_fenetrees = dates_valides

                df_dates = pd.DataFrame({"date_publication": dates_fenetrees})
                daily_counts = df_dates.groupby(df_dates['date_publication'].dt.date).size()
                
                # Convertir les cles date en texte pour la serialisation JSON
                daily_dict = {str(date): int(count) for date, count in daily_counts.items()}

                full_range = pd.date_range(start=daily_counts.index.min(), end=daily_counts.index.max(), freq='D')
                daily_full = daily_counts.reindex(full_range, fill_value=0)
                rolling_7d = daily_full.rolling(window=7, min_periods=1).mean()

                if len(daily_full) >= 14:
                    prev_7 = float(daily_full.iloc[-14:-7].mean())
                    last_7 = float(daily_full.iloc[-7:].mean())
                    baseline = max(prev_7, 1.0)
                    raw_growth = ((last_7 - prev_7) / baseline) * 100
                    growth_7d_pct = float(min(max(raw_growth, -300.0), 300.0))
                else:
                    growth_7d_pct = 0.0

                volatility_cv = float(daily_full.std() / daily_full.mean()) if daily_full.mean() > 0 else 0.0
                
                trend_analysis = {
                    "articles_par_jour": daily_dict,
                    "tendance_haussiere": daily_counts.iloc[-1] > daily_counts.iloc[0] if len(daily_counts) > 1 else False,
                    "moyenne_articles_jour": float(daily_counts.mean()),
                    "fenetre_jours": TREND_WINDOW_DAYS,
                    "moyenne_mobile_7j": {str(idx.date()): float(val) for idx, val in rolling_7d.items()},
                    "croissance_7j_pct": growth_7d_pct,
                    "volatilite_cv": volatility_cv,
                }
            except:
                trend_analysis = {"note": "Impossible d'analyser les tendances a partir des dates"}
        else:
            trend_analysis = {"note": "Date de publication non disponible"}
        
        self.kpis['analyse_tendances'] = trend_analysis
        return trend_analysis
    
    def extract_insights(self, df: pd.DataFrame) -> List[str]:
        """Generer des insights metier exploitables."""
        insights = []

        if df.empty:
            insights.append("Aucun contenu exploitable apres nettoyage; verifier les sources et les regles de filtrage.")
            self.insights = insights
            logger.info("Jeu de donnees vide: insights minimaux generes")
            return insights
        
        # Insight 1: volume de couverture
        total_articles = len(df)
        insight1 = f"Couverture totale: {total_articles} contenus analyses pour la creation de contenu."
        insights.append(insight1)
        
        # Insight 2: source dominante
        if 'source' in df.columns:
            mode_series = df['source'].mode()
            if not mode_series.empty:
                top_source = mode_series.iloc[0]
                source_count = len(df[df['source'] == top_source])
                insight2 = f"Source dominante: '{top_source}' se distingue avec {source_count} articles, signe d'un fort focus editorial."
                insights.append(insight2)

        source_kpis = self.kpis.get('analyse_sources', {}).get('concentration', {})
        if source_kpis:
            insights.append(
                f"Concentration des sources: top source={source_kpis.get('top_source_part_pct', 0):.1f}% | "
                f"HHI={source_kpis.get('hhi', 0):.3f} ({source_kpis.get('niveau', 'N/D')})."
            )
        
        # Insight 3: qualite de contenu
        avg_series = self._safe_numeric_series(df, 'nombre_mots')
        avg_length = float(avg_series.mean()) if not avg_series.empty else 0.0
        if avg_length > 200:
            insight3 = f"Qualite de contenu: une longueur moyenne de {int(avg_length)} mots suggere une couverture approfondie."
        else:
            insight3 = f"Format editorial: une longueur moyenne de {int(avg_length)} mots correspond a des mises a jour rapides."
        insights.append(insight3)
        
        # Insight 4: diversite thematique
        if 'etiquettes' in df.columns:
            unique_topics = sum(1 for tags in df['etiquettes'] if isinstance(tags, list))
            insight4 = f"Diversite thematique: {unique_topics} articles etiquetes avec des sujets pertinents pour l'analyse editoriale."
            insights.append(insight4)

        freshness = self.kpis.get('statistiques_base', {}).get('fraicheur', {})
        if freshness:
            insights.append(
                f"Fraicheur des contenus: {freshness.get('taux_24h_pct', 0):.1f}% publies sous 24h, "
                f"{freshness.get('taux_72h_pct', 0):.1f}% sous 72h."
            )

        trend = self.kpis.get('analyse_tendances', {})
        if trend and 'croissance_7j_pct' in trend:
            insights.append(
                f"Dynamique recentre: croissance 7j={trend.get('croissance_7j_pct', 0):.1f}% | "
                f"volatilite CV={trend.get('volatilite_cv', 0):.2f}."
            )
        
        # Insight 5: potentiel de croissance
        insight5 = "Potentiel de croissance: la production de contenu pilotee par la donnee accelere la visibilite et la performance marketing."
        insights.append(insight5)
        
        self.insights = insights
        logger.info(f"{len(insights)} insights cles generes")
        return insights
    
    def generate_report(self, df: pd.DataFrame) -> Dict:
        """Generer un rapport d'analyse complet."""
        report = {
            "date_analyse": datetime.now().isoformat(),
            "statistiques_base": self.analyze_basic_statistics(df),
            "analyse_sources": self.analyze_sources(df),
            "analyse_secteurs": self.analyze_sectors(df),
            "analyse_mots_cles": self.analyze_keywords(df),
            "analyse_tendances": self.identify_trends(df),
            "insights_metier": self.extract_insights(df),
            "kpis": self.kpis
        }
        return report
    
    def save_report(self, report: Dict, filepath: str):
        """Sauvegarder le rapport d'analyse en JSON."""
        # Encodeur JSON personnalise pour les types speciaux
        class CustomEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, (np.integer, np.int64)):
                    return int(obj)
                if isinstance(obj, (np.floating, np.float64)):
                    return float(obj)
                if isinstance(obj, np.bool_):
                    return bool(obj)
                try:
                    iterable = iter(obj)
                except TypeError:
                    pass
                else:
                    return list(iterable)
                return json.JSONEncoder.default(self, obj)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, cls=CustomEncoder)
        logger.info(f"Rapport enregistre dans {filepath}")


if __name__ == "__main__":
    # Exemple d'utilisation
    from src.config import CLEANED_DATA_FILE, ANALYSIS_FILE
    
    analyzer = DataAnalyzer()
    df = analyzer.load_cleaned_data(str(CLEANED_DATA_FILE))
    report = analyzer.generate_report(df)
    analyzer.save_report(report, str(ANALYSIS_FILE))
    
    print("\n=== RAPPORT D'ANALYSE ===")
    print(f"Articles totaux: {report['statistiques_base']['articles_totaux']}")
    print("\nInsights cles:")
    for insight in report['insights_metier']:
        print(f"  • {insight}")
