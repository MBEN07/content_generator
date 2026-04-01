"""Module de collecte des donnees (RSS et scraping web)."""

import json
import requests
import re
import time
from urllib.parse import quote_plus
from urllib.parse import urlparse
from datetime import datetime
from typing import List, Dict
import logging

from src.config import (
    FRENCH_ONLY,
    TARGET_MIN_ARTICLES,
    TARGET_MAX_ARTICLES,
    MAX_ARTICLES_PER_QUERY,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsCollector:
    """Collecte des actualites depuis des flux RSS et des pages web."""

    @staticmethod
    def _get_feedparser():
        try:
            import feedparser
            return feedparser
        except Exception as exc:
            raise ImportError(
                "feedparser est requis pour la collecte RSS"
            ) from exc

    @staticmethod
    def _get_beautiful_soup():
        try:
            from bs4 import BeautifulSoup
            return BeautifulSoup
        except Exception as exc:
            raise ImportError(
                "beautifulsoup4 est requis pour le scraping web"
            ) from exc
    
    def __init__(self):
        self.articles = []
        self.failed_sources = []

    @staticmethod
    def _normalize_text(value: str) -> str:
        if not isinstance(value, str):
            return ""
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _is_http_url(value: str) -> bool:
        return isinstance(value, str) and value.startswith(("http://", "https://"))

    @staticmethod
    def _is_external_article_url(value: str) -> bool:
        if not NewsCollector._is_http_url(value):
            return False
        return "google" not in urlparse(value).netloc.lower()

    def _extract_html_text(self, html_content: bytes, limit: int = 5000) -> str:
        if isinstance(html_content, bytes):
            # Evite la detection d'encodage couteuse sur de gros payloads.
            try:
                html_text = html_content.decode("utf-8", errors="ignore")
            except Exception:
                html_text = html_content.decode("latin-1", errors="ignore")
        else:
            html_text = str(html_content)

        html_text = html_text[:300000]
        BeautifulSoup = self._get_beautiful_soup()
        soup = BeautifulSoup(html_text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        candidate_texts = []

        for selector in ["meta[name='description']", "meta[property='og:description']", "meta[property='og:title']", "title"]:
            node = soup.select_one(selector)
            if node:
                candidate = node.get("content", "") if node.name == "meta" else node.get_text(" ", strip=True)
                candidate = self._normalize_text(candidate)
                if candidate:
                    candidate_texts.append(candidate)

        for selector in ["article", "main"]:
            node = soup.select_one(selector)
            if node:
                candidate = self._normalize_text(node.get_text(" ", strip=True))
                if candidate:
                    candidate_texts.append(candidate)

        if not candidate_texts:
            paragraphs = [self._normalize_text(p.get_text(" ", strip=True)) for p in soup.find_all("p")]
            candidate_texts.extend([text for text in paragraphs if text])

        merged = self._normalize_text(" ".join(candidate_texts))
        return merged[:limit]

    def _resolve_article_url(self, article_url: str) -> str:
        if not self._is_http_url(article_url):
            return article_url

        try:
            response = self._fetch_with_retry(article_url)
            BeautifulSoup = self._get_beautiful_soup()
            soup = BeautifulSoup(response.content, "html.parser")

            candidate_urls = []
            for selector in ["link[rel='canonical']", "meta[property='og:url']"]:
                node = soup.select_one(selector)
                if node:
                    candidate = node.get("href") or node.get("content")
                    if self._is_external_article_url(candidate):
                        candidate_urls.append(candidate)

            for link in soup.find_all("a", href=True):
                href = link.get("href")
                if self._is_external_article_url(href):
                    candidate_urls.append(href)

            for candidate in candidate_urls:
                return candidate

            return response.url or article_url
        except Exception:
            return article_url

    def _fetch_article_body(self, article_url: str) -> str:
        if not self._is_http_url(article_url):
            return ""

        try:
            response = self._fetch_with_retry(article_url)
            return self._extract_html_text(response.content)
        except Exception:
            return ""

    def _is_french_text(self, text: str) -> bool:
        """Heuristique legere de detection de texte francophone."""
        txt = self._normalize_text(text).lower()
        if not txt:
            return False

        french_markers = {
            " le ", " la ", " les ", " des ", " une ", " un ", " dans ", " pour ",
            " avec ", " sur ", " que ", " qui ", " par ", " au ", " aux ", " est ",
            " sont ", " ce ", " cette ", " ces ", " france ", " maroc "
        }
        marker_hits = sum(1 for marker in french_markers if marker in f" {txt} ")
        accent_hits = sum(txt.count(ch) for ch in "éèàùâêîôûçëïü")

        return marker_hits >= 2 or accent_hits >= 1

    def _infer_secteur(self, title: str, content: str) -> str:
        text = self._normalize_text(f"{title} {content}").lower()
        rules = {
            "geopolitique": ["guerre", "conflit", "sanctions", "diplomatie", "geopolitique"],
            "politique": ["election", "gouvernement", "politique", "parlement", "ministre"],
            "economie": ["economie", "inflation", "pib", "recession", "commerce"],
            "business": ["entreprise", "societe", "strategie", "marche", "croissance"],
            "finance": ["banque", "financement", "investissement", "bourse", "credit"],
            "energie": ["energie", "petrole", "gaz", "renouvelable", "electricite"],
            "climat": ["climat", "emissions", "carbone", "rechauffement", "durabilite"],
            "industrie": ["industrie", "manufacturier", "usine", "production", "site"],
            "automobile": ["automobile", "voiture", "vehicule", "electrique", "mobilite"],
            "aerospatial": ["aerospatial", "aviation", "avion", "airbus", "boeing"],
            "transport": ["transport", "rail", "fret", "port", "logistique"],
            "logistique": ["logistique", "entrepot", "livraison", "approvisionnement", "chaine d'approvisionnement"],
            "immobilier": ["immobilier", "propriete", "logement", "hypotheque", "construction"],
            "commerce": ["commerce", "distribution", "consommateur", "vente", "achat"],
            "telecom": ["telecom", "5g", "operateur", "reseau", "bande passante"],
            "tech": ["technologie", "ia", "intelligence artificielle", "logiciel", "cloud", "donnees"],
            "cybersecurite": ["cyber", "securite", "rancongiciel", "malware", "faille"],
            "media": ["media", "journalisme", "edition", "audience", "plateforme"],
            "marketing": ["marketing", "campagne", "marque", "publicite", "influenceur"],
            "education": ["education", "ecole", "universite", "apprentissage", "etudiant"],
            "sante": ["sante", "hopital", "medecine", "patient", "soins"],
            "pharma": ["pharma", "medicament", "clinique", "essai", "autorite"],
            "agriculture": ["agriculture", "agricole", "culture", "alimentaire", "recolte"],
            "tourisme": ["tourisme", "voyage", "hotel", "compagnie aerienne", "destination"],
            "sports": ["sport", "football", "olympiques", "match", "ligue"],
            "culture": ["culture", "cinema", "musique", "art", "festival"],
            "emploi": ["emploi", "travail", "salaire", "recrutement", "embauche"],
            "defense": ["defense", "militaire", "armee", "missile", "securite"],
            "science": ["science", "recherche", "etude", "laboratoire", "innovation"],
            "space": ["espace", "nasa", "satellite", "fusée", "orbite"],
        }
        for secteur, keywords in rules.items():
            if any(k in text for k in keywords):
                return secteur
        return "general"

    def _extract_rss_article(self, entry: Dict, source_name: str) -> Dict:
        title = self._normalize_text(entry.get("title", "N/D"))
        summary = self._normalize_text(entry.get("summary", ""))
        content = summary

        if not content and entry.get("content"):
            content_items = entry.get("content", [])
            if content_items and isinstance(content_items, list):
                content = self._normalize_text(content_items[0].get("value", ""))

        article_url = entry.get("link", "")
        resolved_url = self._resolve_article_url(article_url)
        full_text = self._fetch_article_body(resolved_url)
        if len(full_text) > len(content) and len(full_text) >= 120:
            content = full_text

        article = {
            "titre": title,
            "contenu": content,
            "source": source_name,
            "lien": resolved_url or article_url,
            "publie": entry.get("published", datetime.now().isoformat()),
            "auteurs": entry.get("author", "Inconnu"),
            "etiquettes": [tag.term for tag in entry.get("tags", [])],
            "date_collecte": datetime.now().isoformat(),
            "source_donnee": "RSS",
            "secteur_estime": self._infer_secteur(title, content),
        }
        return article

    @staticmethod
    def _build_query_rss_url(query: str) -> str:
        encoded_query = quote_plus(query)
        return (
            "https://news.google.com/rss/search?"
            f"q={encoded_query}&hl=fr&gl=FR&ceid=FR:fr"
        )

    def _fetch_with_retry(self, url: str, max_attempts: int = 3, timeout: int = 15) -> requests.Response:
        """Recuperer une URL avec retry/backoff exponentiel simple."""
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.get(
                    url,
                    timeout=timeout,
                    headers={"User-Agent": "Mozilla/5.0 (IndustrialAINewsEngine/1.0)"},
                )
                response.raise_for_status()
                return response
            except requests.exceptions.Timeout as exc:
                last_error = exc
                logger.warning(f"Timeout tentative {attempt}/{max_attempts} pour {url}")
            except requests.exceptions.ConnectionError as exc:
                last_error = exc
                logger.warning(f"Erreur reseau tentative {attempt}/{max_attempts} pour {url}")
            except requests.exceptions.HTTPError:
                # Les erreurs HTTP 4xx/5xx ne sont pas toujours recuperables: arret immediat.
                raise

            if attempt < max_attempts:
                sleep_seconds = 2 ** (attempt - 1)
                time.sleep(sleep_seconds)

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Echec inconnu de recuperation URL: {url}")
    
    def collect_from_targeted_multi_query_rss(
        self,
        queries: List[str],
        target_min: int = TARGET_MIN_ARTICLES,
        target_max: int = TARGET_MAX_ARTICLES,
        max_articles_per_query: int = MAX_ARTICLES_PER_QUERY,
    ) -> List[Dict]:
        """Collecter des articles RSS via requetes ciblees jusqu'a une plage de volume."""
        articles = []
        seen_links = set()

        logger.info(
            "Demarrage collecte RSS multi-query: %s requetes, cible=%s-%s, max_par_requete=%s",
            len(queries),
            target_min,
            target_max,
            max_articles_per_query,
        )

        for query_index, query in enumerate(queries, 1):
            query_url = self._build_query_rss_url(query)
            try:
                logger.info(
                    "[%s/%s] Recuperation RSS multi-query: %s",
                    query_index,
                    len(queries),
                    query,
                )
                response = self._fetch_with_retry(query_url)
                feedparser = self._get_feedparser()
                feed = feedparser.parse(response.content)

                if getattr(feed, "bozo", False):
                    raise ValueError(f"Flux RSS multi-query invalide pour '{query}'")

                source_name = f"Google Actualites - {query}"
                accepted_for_query = 0
                duplicate_count = 0
                too_short_count = 0
                french_rejected_count = 0
                parsed_entries = len(getattr(feed, "entries", []) or [])

                logger.info(
                    "[%s/%s] Flux analyse: %s entrees detectees pour '%s'",
                    query_index,
                    len(queries),
                    parsed_entries,
                    query,
                )

                for entry in feed.entries:
                    article = self._extract_rss_article(entry, source_name)
                    article["query_rss"] = query

                    if not article.get("lien") or article["lien"] in seen_links:
                        duplicate_count += 1
                        continue

                    if len(article["contenu"]) < 120:
                        too_short_count += 1
                        continue

                    if FRENCH_ONLY:
                        fr_candidate = f"{article['titre']} {article['contenu']}"
                        if not self._is_french_text(fr_candidate):
                            french_rejected_count += 1
                            continue

                    seen_links.add(article["lien"])
                    articles.append(article)
                    accepted_for_query += 1

                    logger.info(
                        "[%s/%s] Article accepte (%s/%s) | titre='%s' | source='%s'",
                        query_index,
                        len(queries),
                        accepted_for_query,
                        max_articles_per_query,
                        article["titre"][:90],
                        article["source"],
                    )

                    if accepted_for_query >= max_articles_per_query:
                        logger.info(
                            "[%s/%s] Limite atteinte pour '%s': %s articles gardes",
                            query_index,
                            len(queries),
                            query,
                            accepted_for_query,
                        )
                        break

                    if len(articles) >= target_max:
                        logger.info(
                            "Limite globale atteinte: %s/%s articles",
                            len(articles),
                            target_max,
                        )
                        break

                logger.info(
                    "[%s/%s] Resume '%s': detectes=%s, gardes=%s, doublons=%s, trop_courts=%s, non_francais=%s, total_courant=%s",
                    query_index,
                    len(queries),
                    query,
                    parsed_entries,
                    accepted_for_query,
                    duplicate_count,
                    too_short_count,
                    french_rejected_count,
                    len(articles),
                )

                if len(articles) >= target_max:
                    break

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                logger.error(f"Erreur reseau RSS multi-query '{query}': {str(e)}")
                self.failed_sources.append({
                    "source": query_url,
                    "type_erreur": "reseau",
                    "query": query,
                    "error": str(e),
                    "horodatage": datetime.now().isoformat(),
                })
            except requests.exceptions.HTTPError as e:
                logger.error(f"Erreur HTTP RSS multi-query '{query}': {str(e)}")
                self.failed_sources.append({
                    "source": query_url,
                    "type_erreur": "http",
                    "query": query,
                    "error": str(e),
                    "horodatage": datetime.now().isoformat(),
                })
            except ValueError as e:
                logger.error(f"Erreur parsing RSS multi-query '{query}': {str(e)}")
                self.failed_sources.append({
                    "source": query_url,
                    "type_erreur": "parsing",
                    "query": query,
                    "error": str(e),
                    "horodatage": datetime.now().isoformat(),
                })

        if len(articles) < target_min:
            raise ValueError(
                "Volume multi-query inferieur a la cible minimale: "
                f"{len(articles)} / {target_min}"
            )

        self.articles.extend(articles)
        logger.info(
            "Collecte RSS multi-query terminee: %s articles ajoutes, %s liens uniques, %s sources en echec",
            len(articles),
            len(seen_links),
            len(self.failed_sources),
        )
        return articles
    
    def collect_from_web(self, urls: List[str]) -> List[Dict]:
        """
        Collecter des articles depuis des pages web.
        
        Args:
            urls: Liste d'URLs a scraper.
            
        Returns:
            Liste de dictionnaires d'articles.
        """
        articles = []
        
        for url in urls:
            try:
                logger.info("Scraping de la page: %s", url)
                response = requests.get(
                    url,
                    timeout=15,
                    headers={"User-Agent": "Mozilla/5.0 (IndustrialAINewsEngine/1.0)"},
                )
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extraction generique de contenu
                title = soup.find('h1')
                content = soup.find('article') or soup.find('main')
                
                if title and content:
                    title_text = self._normalize_text(title.get_text(strip=True))
                    content_text = self._normalize_text(content.get_text(strip=True)[:2500])

                    if FRENCH_ONLY and not self._is_french_text(f"{title_text} {content_text}"):
                        logger.info("Scraping ignore (non francais): %s", url)
                        continue

                    article = {
                        "titre": title_text,
                        "contenu": content_text,
                        "source": url.split('/')[2],  # Nom de domaine
                        "lien": url,
                        "publie": datetime.now().isoformat(),
                        "auteurs": "Scraping Web",
                        "etiquettes": [],
                        "date_collecte": datetime.now().isoformat(),
                        "source_donnee": "Scraping Web",
                        "secteur_estime": self._infer_secteur(title_text, content_text),
                    }
                    articles.append(article)
                    logger.info(
                        "Scraping accepte: titre='%s' | domaine='%s'",
                        title_text[:90],
                        article["source"],
                    )
                    
            except Exception as e:
                logger.error(f"Erreur de scraping {url}: {str(e)}")
                self.failed_sources.append({"source": url, "error": str(e)})
        
        self.articles.extend(articles)
        logger.info(
            "Collecte web terminee: %s articles ajoutes, %s URLs traitees, %s sources en echec",
            len(articles),
            len(urls),
            len(self.failed_sources),
        )
        return articles
    
    def get_all_articles(self) -> List[Dict]:
        """Retourner tous les articles collectes."""
        return self.articles
    
    def save_to_json(self, filepath: str):
        """Enregistrer les articles collectes dans un fichier JSON."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.articles, f, indent=2, ensure_ascii=False)
        logger.info(
            "Sauvegarde terminee: %s articles enregistres dans %s",
            len(self.articles),
            filepath,
        )
    
    def get_collection_summary(self) -> Dict:
        """Obtenir un resume du processus de collecte."""
        return {
            "articles_totaux": len(self.articles),
            "sources_en_echec": len(self.failed_sources),
            "date_collecte": datetime.now().isoformat(),
            "details_sources_en_echec": self.failed_sources
        }


if __name__ == "__main__":
    # Exemple d'utilisation
    from src.config import RAW_DATA_FILE, TARGETED_RSS_QUERIES
    
    logger.info("Lancement du module data_collection en mode autonome")
    collector = NewsCollector()
    collector.collect_from_targeted_multi_query_rss(TARGETED_RSS_QUERIES)
    collector.save_to_json(str(RAW_DATA_FILE))
    
    logger.info("Resume collecte: %s", collector.get_collection_summary())
    print(collector.get_collection_summary())
