"""Automated AI Content Intelligence Pipeline: orchestration complete du workflow Data/IA."""

import logging
from datetime import datetime
from typing import Dict
from collections import Counter
import re
import math
import schedule
import time
import json
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.data_collection import NewsCollector
from src.data_cleaning import DataCleaner
from src.data_analysis import DataAnalyzer
from src.config import (
    RAW_DATA_FILE, CLEANED_DATA_FILE, ANALYSIS_FILE, GENERATED_ARTICLES_FILE,
    IA_EXAMPLES_FILE,
    SCHEDULE_INTERVAL, SCHEDULE_TIME, TARGETED_RSS_QUERIES,
    ENABLE_GENERATION, FAST_GENERATION_MODE, MAX_LLM_ARTICLES,
    TARGET_MIN_ARTICLES, TARGET_MAX_ARTICLES, TOP_TOPICS_TO_GENERATE,
    MAX_WORKERS,
    VALIDATION_CLEANED_DATA_FILE,
    validate_config
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AutomationPipeline:
    """Orchestre un mini systeme de production IA pour la content intelligence."""
    SNIPPET_SIMILARITY_THRESHOLD = 0.90
    
    def __init__(self):
        validate_config()
        self.statut = "initialise"
        self.derniere_execution = None
        self.journal_execution = []
        self.run_id = None

    @staticmethod
    def _log_event(event: str, **payload):
        """Log structuré JSON pour faciliter le monitoring en production."""
        message = {"event": event, **payload}
        logger.info(json.dumps(message, ensure_ascii=False))

    @staticmethod
    def _split_sentences(text: str):
        if not isinstance(text, str):
            return []
        return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]

    @staticmethod
    def _safe_mean(group_df, column_name: str, default: float = 0.0) -> float:
        if column_name not in group_df.columns:
            return default
        series = group_df[column_name]
        if series.empty:
            return default
        try:
            numeric = series.astype(float)
            return float(numeric.mean()) if len(numeric) else default
        except Exception:
            return default

    @staticmethod
    def _safe_nunique(group_df, column_name: str, default: int = 0) -> int:
        if column_name not in group_df.columns:
            return default
        series = group_df[column_name]
        if series.empty:
            return default
        try:
            return int(series.nunique())
        except Exception:
            return default

    @staticmethod
    def _build_text_embedding(text: str) -> Dict[str, float]:
        """Construit un embedding sparse lexical simple pour comparer les snippets."""
        if not isinstance(text, str):
            return {}

        tokens = re.findall(r"[a-zA-ZÀ-ÿ0-9]+", text.lower())
        if not tokens:
            return {}

        stop_words = {
            "le", "la", "les", "de", "des", "du", "un", "une", "et", "en", "dans", "sur", "pour", "par",
            "au", "aux", "est", "sont", "ce", "cette", "ces", "the", "and", "for", "with", "from", "that",
            "this", "are", "was", "were", "will",
        }
        filtered = [token for token in tokens if len(token) > 2 and token not in stop_words]
        if not filtered:
            return {}

        counts = Counter(filtered)
        norm = math.sqrt(sum(value * value for value in counts.values()))
        if norm == 0:
            return {}
        return {token: value / norm for token, value in counts.items()}

    @staticmethod
    def _cosine_similarity_sparse(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
        if not vec_a or not vec_b:
            return 0.0
        shared = set(vec_a.keys()) & set(vec_b.keys())
        return float(sum(vec_a[token] * vec_b[token] for token in shared))

    def _is_semantic_duplicate_snippet(self, snippet: str, existing_embeddings: list[Dict[str, float]]) -> bool:
        snippet_embedding = self._build_text_embedding(snippet)
        if not snippet_embedding:
            return False

        for existing in existing_embeddings:
            similarity = self._cosine_similarity_sparse(snippet_embedding, existing)
            if similarity >= self.SNIPPET_SIMILARITY_THRESHOLD:
                return True
        return False

    def _classify_topics_parallel(self, df, generator):
        """Classification parallèle des topics pour accelérer la préparation des données."""
        records = df.to_dict("records")
        max_workers = max(1, min(MAX_WORKERS, len(records))) if records else 1
        if not records:
            return []

        def _classify_row(row):
            return generator.classify_editorial_sector(row)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            topics = list(executor.map(_classify_row, records))
        return topics

    def _score_topic_quality(self, group_df):
        article_count = len(group_df)
        avg_words = self._safe_mean(group_df, "nombre_mots", default=0.0) if article_count else 0.0
        source_diversity = self._safe_nunique(group_df, "source", default=0) if article_count else 0
        avg_source_quality = self._safe_mean(group_df, "score_qualite_source", default=0.0) if article_count else 0.0

        volume_score = min(article_count / 6.0, 1.0)
        depth_score = min(avg_words / 240.0, 1.0)
        diversity_score = min(source_diversity / 3.0, 1.0)
        quality_score = min(avg_source_quality, 1.0)

        return (
            volume_score * 0.40 +
            depth_score * 0.25 +
            diversity_score * 0.20 +
            quality_score * 0.15
        )

    def _select_top_topics_dynamic(self, df, top_n: int = TOP_TOPICS_TO_GENERATE):
        if df.empty or "topic_classe" not in df.columns:
            return []

        excluded_topics = {
            "other",
            "autre",
            "general",
            "misc",
            "unknown",
            "nan",
            "semantic_noise",
            "uncategorized",
        }
        candidates = []

        for topic, group in df.groupby("topic_classe"):
            topic_clean = str(topic).strip().lower()
            if topic_clean in excluded_topics or not topic_clean:
                continue

            count = len(group)
            avg_words = self._safe_mean(group, "nombre_mots", default=0.0) if count else 0.0
            quality_score = self._score_topic_quality(group)

            # Garde-fou qualite: minimum de volume et de profondeur, adapte aux news courtes.
            if count < 2 or avg_words < 12:
                continue

            candidates.append(
                {
                    "topic": topic,
                    "count": count,
                    "avg_words": avg_words,
                    "quality_score": quality_score,
                }
            )

        if not candidates:
            return []

        candidates.sort(key=lambda x: (x["quality_score"], x["count"], x["avg_words"]), reverse=True)
        return [row["topic"] for row in candidates[:top_n]]

    def _smart_merge_topic_articles(self, topic_df, topic: str) -> Dict:
        """Fusion intelligente: synthese par signaux cles, sans concat brute."""
        if topic_df.empty:
            return {
                "titre": f"Synthese {topic}",
                "contenu": "Aucun contenu disponible.",
                "etiquettes": [topic],
                "source": "multi-source",
                "publie": datetime.now().isoformat(),
            }

        if "score_qualite_source" not in topic_df.columns:
            topic_df = topic_df.copy()
            topic_df["score_qualite_source"] = 0.0
        if "nombre_mots" not in topic_df.columns:
            topic_df = topic_df.copy()
            if "contenu" in topic_df.columns:
                topic_df["nombre_mots"] = topic_df["contenu"].astype(str).apply(lambda x: len(x.split()))
            else:
                topic_df["nombre_mots"] = 0

        ranked = topic_df.sort_values(
            by=["score_qualite_source", "nombre_mots"], ascending=False
        ).head(8)

        title_tokens = []
        source_signals = []
        key_points = []
        keyword_candidates = []
        snippet_embeddings = []

        for _, row in ranked.iterrows():
            title = str(row.get("titre", "")).strip()
            content = str(row.get("contenu", "")).strip()
            source = str(row.get("source", "Source"))

            title_tokens.extend(re.findall(r"[a-zA-Z]{4,}", title.lower()))
            keyword_candidates.extend(row.get("etiquettes", []) if isinstance(row.get("etiquettes", []), list) else [])

            sentences = self._split_sentences(content)
            if not sentences:
                continue

            snippet = ". ".join(sentences[:2])[:320]
            norm_snippet = re.sub(r"\s+", " ", snippet.lower()).strip()
            if self._is_semantic_duplicate_snippet(norm_snippet, snippet_embeddings):
                continue
            snippet_embeddings.append(self._build_text_embedding(norm_snippet))

            source_signals.append(f"- [{source}] {title}")
            key_points.append(f"- {snippet}")

        top_title_tokens = [w for w, _ in Counter(title_tokens).most_common(4)]
        top_keywords = [k for k, _ in Counter(keyword_candidates).most_common(6)]

        smart_title = (
            f"{topic.title()}: {' | '.join(top_title_tokens[:2])}"
            if top_title_tokens else
            f"Synthese strategique: {topic.title()}"
        )

        merged_content = (
            f"Theme prioritaire: {topic}\n\n"
            "Signaux editoriaux consolides:\n"
            f"{'\n'.join(source_signals[:6])}\n\n"
            "Points saillants (synthese multi-source):\n"
            f"{'\n'.join(key_points[:6])}\n\n"
            "Instruction: rediger une analyse business coherente en evitant toute repetition et sans copier les formulations d'origine."
        )

        return {
            "titre": smart_title,
            "contenu": merged_content,
            "etiquettes": top_keywords if top_keywords else [topic],
            "source": "multi-source",
            "publie": datetime.now().isoformat(),
            "topic": topic,
            "volume_sources": len(ranked),
        }
    
    def run_collection_stage(self) -> Dict:
        """Etape 1: collecte des donnees brutes."""
        logger.info("=" * 50)
        logger.info("ETAPE 1: COLLECTE DES DONNEES")
        logger.info("=" * 50)
        
        stage_start = datetime.now()
        try:
            collector = NewsCollector()
            self._log_event(
                "collection_started",
                run_id=self.run_id,
                target_min=TARGET_MIN_ARTICLES,
                target_max=TARGET_MAX_ARTICLES,
                query_count=len(TARGETED_RSS_QUERIES),
            )

            # Collecte stricte via requetes RSS ciblees.
            collector.collect_from_targeted_multi_query_rss(
                TARGETED_RSS_QUERIES,
                target_min=TARGET_MIN_ARTICLES,
                target_max=TARGET_MAX_ARTICLES,
            )

            if len(collector.articles) < TARGET_MIN_ARTICLES:
                raise ValueError(
                    f"Volume collecte insuffisant: {len(collector.articles)} < {TARGET_MIN_ARTICLES}"
                )

            if len(collector.articles) > TARGET_MAX_ARTICLES:
                collector.articles = collector.articles[:TARGET_MAX_ARTICLES]

            if not collector.articles:
                raise ValueError("Aucun article collecte depuis les sources en ligne")

            collector.save_to_json(str(RAW_DATA_FILE))
            
            summary = collector.get_collection_summary()
            logger.info(f"Collecte terminee: {summary['articles_totaux']} articles")
            self._log_event(
                "collection_completed",
                run_id=self.run_id,
                status="success",
                articles_collected=summary["articles_totaux"],
                failed_sources=summary["sources_en_echec"],
            )
            
            return {
                "etape": "collecte",
                "statut": "succes",
                "articles_collectes": summary['articles_totaux'],
                "cible_articles": f"{TARGET_MIN_ARTICLES}-{TARGET_MAX_ARTICLES}",
                "sources_en_echec": summary['sources_en_echec'],
                "details_sources_en_echec": summary['details_sources_en_echec'],
                "horodatage": datetime.now().isoformat(),
                "duree_secondes": (datetime.now() - stage_start).total_seconds(),
                "run_id": self.run_id,
            }
        except Exception as e:
            logger.error(f"Echec de collecte: {str(e)}")
            self._log_event("collection_completed", run_id=self.run_id, status="failed", error=str(e))
            return {
                "etape": "collecte",
                "statut": "echec",
                "erreur": str(e),
                "horodatage": datetime.now().isoformat(),
                "duree_secondes": (datetime.now() - stage_start).total_seconds(),
                "run_id": self.run_id,
            }
    
    def run_cleaning_stage(self) -> Dict:
        """Etape 2: nettoyage et pretraitement."""
        logger.info("\n" + "=" * 50)
        logger.info("ETAPE 2: NETTOYAGE DES DONNEES")
        logger.info("=" * 50)
        
        stage_start = datetime.now()
        try:
            cleaner = DataCleaner()
            df = cleaner.clean_pipeline(str(RAW_DATA_FILE))
            cleaner.save_cleaned_data(
                df,
                str(CLEANED_DATA_FILE),
                str(VALIDATION_CLEANED_DATA_FILE),
            )
            
            report = cleaner.get_cleaning_report()
            logger.info(f"Nettoyage termine: {report['enregistrements_finaux']} enregistrements apres traitement")
            
            return {
                "etape": "nettoyage",
                "statut": "succes",
                "enregistrements_traites": report['enregistrements_finaux'],
                "rapport_nettoyage": report,
                "fichier_validation_nettoye": str(VALIDATION_CLEANED_DATA_FILE),
                "horodatage": datetime.now().isoformat(),
                "duree_secondes": (datetime.now() - stage_start).total_seconds(),
                "run_id": self.run_id,
            }
        except Exception as e:
            logger.error(f"Echec du nettoyage: {str(e)}")
            return {
                "etape": "nettoyage",
                "statut": "echec",
                "erreur": str(e),
                "horodatage": datetime.now().isoformat(),
                "duree_secondes": (datetime.now() - stage_start).total_seconds(),
                "run_id": self.run_id,
            }
    
    def run_analysis_stage(self) -> Dict:
        """Etape 3: analyse et extraction d'insights."""
        logger.info("\n" + "=" * 50)
        logger.info("ETAPE 3: ANALYSE DES DONNEES")
        logger.info("=" * 50)
        
        stage_start = datetime.now()
        try:
            analyzer = DataAnalyzer()
            df = analyzer.load_cleaned_data(str(CLEANED_DATA_FILE))
            report = analyzer.generate_report(df)
            analyzer.save_report(report, str(ANALYSIS_FILE))
            
            logger.info("Analyse terminee")
            logger.info(f"  • Articles totaux: {report['statistiques_base']['articles_totaux']}")
            logger.info(f"  • Sources uniques: {report['analyse_sources']['sources_uniques']}")
            logger.info("  Insights cles:")
            for insight in report['insights_metier']:
                logger.info(f"    - {insight}")
            
            return {
                "etape": "analyse",
                "statut": "succes",
                "kpis": report['kpis'],
                "insights": report['insights_metier'],
                "horodatage": datetime.now().isoformat(),
                "duree_secondes": (datetime.now() - stage_start).total_seconds(),
                "run_id": self.run_id,
            }
        except Exception as e:
            logger.error(f"Echec de l'analyse: {str(e)}")
            return {
                "etape": "analyse",
                "statut": "echec",
                "erreur": str(e),
                "horodatage": datetime.now().isoformat(),
                "duree_secondes": (datetime.now() - stage_start).total_seconds(),
                "run_id": self.run_id,
            }
    
    def run_generation_stage(self) -> Dict:
        """Etape 4: generation et enrichissement IA des contenus."""
        logger.info("\n" + "=" * 50)
        logger.info("ETAPE 4: GENERATION IA DES ARTICLES")
        logger.info("=" * 50)
        
        stage_start = datetime.now()

        if not ENABLE_GENERATION:
            logger.info("Generation desactivee via ENABLE_GENERATION=false")
            self._log_event("generation_skipped", run_id=self.run_id, reason="disabled_by_config")
            return {
                "etape": "generation",
                "statut": "ignore",
                "raison": "Generation desactivee par configuration",
                "horodatage": datetime.now().isoformat(),
                "duree_secondes": (datetime.now() - stage_start).total_seconds(),
                "run_id": self.run_id,
            }

        try:
            import pandas as pd
            from src.ai_generation import ArticleGenerator
            
            df = pd.read_json(str(CLEANED_DATA_FILE))
            if df.empty:
                raise ValueError("Aucun article disponible pour la generation")

            # Compatibilite ascendante: rendre exploitable un fichier nettoye ancien format.
            if "nombre_mots" not in df.columns:
                if "contenu" in df.columns:
                    df["nombre_mots"] = df["contenu"].astype(str).apply(lambda x: len(x.split()))
                else:
                    df["nombre_mots"] = 0
            if "score_qualite_source" not in df.columns:
                normalized_words = (df["nombre_mots"].astype(float).clip(upper=300) / 300).fillna(0.0)
                df["score_qualite_source"] = normalized_words.round(4)
            if "etiquettes" not in df.columns:
                df["etiquettes"] = [[] for _ in range(len(df))]
            else:
                df["etiquettes"] = df["etiquettes"].apply(
                    lambda x: x if isinstance(x, list) else ([str(x)] if str(x).strip() else [])
                )

            # Le mode rapide limite surtout le volume, pas le moteur de generation.
            preview_rows = min(len(df), 40)
            use_fast_mode = FAST_GENERATION_MODE and preview_rows > MAX_LLM_ARTICLES
            if use_fast_mode:
                logger.info(
                    f"Mode rapide active: limitation du volume de sujets (seuil LLM={MAX_LLM_ARTICLES})"
                )
            
            generator = ArticleGenerator()

            if "topic_classe" not in df.columns:
                self._log_event("classification_started", run_id=self.run_id, records=len(df), max_workers=MAX_WORKERS)
                df["topic_classe"] = self._classify_topics_parallel(df, generator)
                self._log_event("classification_completed", run_id=self.run_id, records=len(df), status="success")

            logger.info("Workflow cible: classification -> 3 sujets principaux -> fusion -> article + resume + publication LinkedIn")

            top_topics = self._select_top_topics_dynamic(df, top_n=3)
            if not top_topics:
                raise ValueError("Impossible d'identifier des topics frequents de qualite")

            if len(top_topics) > 3:
                top_topics = top_topics[:3]

            generated_articles = []
            generation_errors = []
            topic_frames = {topic: df[df["topic_classe"] == topic].copy() for topic in top_topics}
            max_workers_topics = max(1, min(MAX_WORKERS, len(top_topics)))

            self._log_event(
                "generation_started",
                run_id=self.run_id,
                topics=len(top_topics),
                max_workers=max_workers_topics,
            )

            def _generate_for_topic(topic_name: str):
                local_generator = ArticleGenerator()
                topic_df = topic_frames[topic_name]
                merged_payload = self._smart_merge_topic_articles(topic_df, topic_name)

                article = local_generator.generate_article(merged_payload, max_new_tokens=420)
                summary = local_generator.generate_summary(article.get("contenu_genere", ""))
                linkedin_post = local_generator.generate_linkedin_post(
                    article.get("contenu_genere", ""),
                    topic_name,
                    merged_payload.get("etiquettes", []),
                )

                article["topic_frequent"] = topic_name
                article["articles_sources_topic"] = int(len(topic_df))
                article["resume_genere"] = summary
                article["linkedin_post"] = linkedin_post
                article["type_generation"] = "topic-synthesis"
                return article

            with ThreadPoolExecutor(max_workers=max_workers_topics) as executor:
                futures = {executor.submit(_generate_for_topic, topic): topic for topic in top_topics}
                for future in as_completed(futures):
                    topic = futures[future]
                    try:
                        article = future.result()
                        generated_articles.append(article)
                        self._log_event("generation_topic", run_id=self.run_id, topic=topic, status="success")
                    except Exception as exc:
                        generation_errors.append({"topic": topic, "erreur": str(exc)})
                        self._log_event("generation_topic", run_id=self.run_id, topic=topic, status="failed", error=str(exc))

            if not generated_articles:
                raise ValueError(
                    f"Aucun article genere. Erreurs: {generation_errors}"
                )

            generator.save_generated_articles(generated_articles, str(GENERATED_ARTICLES_FILE))

            ia_examples = {
                "approche_ia": {
                    "generation": "LLM instructionnel en francais avec contrainte factuelle",
                    "classification": "regles lexicales et regroupement par sujet frequent",
                    "summarization": "resume via modele de synthese + secours extractif",
                    "social": "generation d'une publication LinkedIn premium par sujet frequent",
                    "fusion": "fusion intelligente multi-source (sans concat brutale)",
                },
                "exemples_resultats": generated_articles[:3],
                "topics_selectionnes": top_topics,
            }
            with open(str(IA_EXAMPLES_FILE), "w", encoding="utf-8") as f:
                json.dump(ia_examples, f, indent=2, ensure_ascii=False)
            
            success_count = sum(1 for a in generated_articles if a.get('statut_generation') == 'succes')
            logger.info(f"Generation terminee: {success_count}/{len(generated_articles)} articles generes")
            self._log_event(
                "generation_completed",
                run_id=self.run_id,
                status="success",
                generated=len(generated_articles),
                errors=len(generation_errors),
            )
            
            return {
                "etape": "generation",
                "statut": "succes",
                "articles_generes": len(generated_articles),
                "topics_selectionnes": top_topics,
                "nombre_topics_selectionnes": len(top_topics),
                "taux_succes": f"{(success_count/len(generated_articles)*100):.1f}%",
                "erreurs_generation": generation_errors,
                "fichier_exemples_ia": str(IA_EXAMPLES_FILE),
                "horodatage": datetime.now().isoformat(),
                "duree_secondes": (datetime.now() - stage_start).total_seconds(),
                "run_id": self.run_id,
            }
        except Exception as e:
            logger.error(f"Echec de la generation: {str(e)}")
            self._log_event("generation_completed", run_id=self.run_id, status="failed", error=str(e))
            return {
                "etape": "generation",
                "statut": "echec",
                "erreur": str(e),
                "horodatage": datetime.now().isoformat(),
                "duree_secondes": (datetime.now() - stage_start).total_seconds(),
                "run_id": self.run_id,
            }
    
    def run_complete_pipeline(self) -> Dict:
        """Executer le pipeline complet."""
        logger.info("\n\n")
        logger.info("DEMARRAGE DU PIPELINE COMPLET D'AUTOMATISATION")
        logger.info(f"   Heure de debut: {datetime.now().isoformat()}")
        logger.info("=" * 50)
        
        start_time = datetime.now()
        self.run_id = f"run_{start_time.strftime('%Y%m%d_%H%M%S')}_{str(uuid4())[:8]}"
        results = {
            "run_id": self.run_id,
            "debut_pipeline": start_time.isoformat(),
            "etapes": []
        }
        
        # Executer toutes les etapes
        stages = [
            self.run_collection_stage,
            self.run_cleaning_stage,
            self.run_analysis_stage,
            self.run_generation_stage
        ]
        
        for stage_func in stages:
            stage_result = stage_func()
            results["etapes"].append(stage_result)
            
            # Arreter si une etape echoue
            if stage_result["statut"] == "echec":
                logger.error("Pipeline arrete suite a un echec d'etape")
                break
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        results["fin_pipeline"] = end_time.isoformat()
        results["duree_secondes"] = duration
        has_failure = any(stage.get("statut") == "echec" for stage in results["etapes"])
        results["statut_pipeline"] = "echec" if has_failure else "termine"
        
        logger.info("\n" + "=" * 50)
        logger.info("EXECUTION DU PIPELINE TERMINEE")
        logger.info(f"   Duree totale: {duration:.2f} secondes")
        logger.info("=" * 50 + "\n")
        
        self.derniere_execution = end_time
        self.journal_execution.append(results)
        
        return results
    
    def schedule_pipeline(self):
        """Planifier l'execution automatique du pipeline."""
        logger.info(f"Planification du pipeline: {SCHEDULE_INTERVAL} a {SCHEDULE_TIME}")
        
        if SCHEDULE_INTERVAL == "hourly":
            schedule.every().hour.at(SCHEDULE_TIME[-2:]).do(self.run_complete_pipeline)
        elif SCHEDULE_INTERVAL == "daily":
            schedule.every().day.at(SCHEDULE_TIME).do(self.run_complete_pipeline)
        elif SCHEDULE_INTERVAL == "weekly":
            schedule.every().monday.at(SCHEDULE_TIME).do(self.run_complete_pipeline)
        
        logger.info("Pipeline planifie avec succes")
        
        # Maintenir le scheduler actif
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    def get_status(self) -> Dict:
        """Recuperer l'etat courant du pipeline."""
        return {
            "statut": self.statut,
            "derniere_execution": self.derniere_execution,
            "nombre_executions": len(self.journal_execution)
        }


if __name__ == "__main__":
    # Executer le pipeline
    pipeline = AutomationPipeline()
    results = pipeline.run_complete_pipeline()
    
    # Enregistrer les resultats d'execution
    with open('pipeline_execution.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "=" * 50)
    print("RESUME D'EXECUTION DU PIPELINE")
    print("=" * 50)
    print(json.dumps(results, indent=2))
