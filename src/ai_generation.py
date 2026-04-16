"""Module de generation d'articles via API Groq/Gemini, sans fallback local."""

import json
import logging
import re
import unicodedata
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency in minimal installs
    OpenAI = None

from src.config import (
    AI_PROVIDER_CHAIN,
    GROQ_API_BASE,
    GROQ_API_KEY,
    GROQ_MODEL_NAME,
    GROQ_TIMEOUT_SECONDS,
    GEMINI_API_BASE,
    GOOGLE_GEMINI_API_KEY,
    GEMINI_MODEL_NAME,
    GEMINI_TIMEOUT_SECONDS,
    GENERATION_MAX_NEW_TOKENS,
    GENERATION_STRICT_FACTUAL,
    GENERATION_TEMPERATURE,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ArticleGenerator:
    """Genere des articles a l'aide de l'IA."""

    @staticmethod
    def _clean_text(value: str) -> str:
        if not isinstance(value, str):
            return ""
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _extract_json_object(raw_text: str) -> Optional[Dict]:
        """Extraire un objet JSON valide depuis une reponse LLM potentiellement bruitee."""
        if not isinstance(raw_text, str) or not raw_text.strip():
            return None

        candidate = raw_text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?", "", candidate, flags=re.IGNORECASE).strip()
            candidate = re.sub(r"```$", "", candidate).strip()

        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            pass

        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

        try:
            parsed = json.loads(candidate[start:end + 1])
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    @staticmethod
    def _normalize_structured_article(payload: Dict) -> Optional[Dict]:
        """Valider et normaliser le schema article structure attendu."""
        if not isinstance(payload, dict):
            return None

        title = str(payload.get("title", "")).strip()
        introduction = str(payload.get("introduction", "")).strip()
        conclusion = str(payload.get("conclusion", "")).strip()

        raw_sections = payload.get("sections", [])
        sections = []
        if isinstance(raw_sections, list):
            for item in raw_sections:
                if isinstance(item, dict):
                    section_title = str(item.get("title", "")).strip()
                    section_content = str(item.get("content", "")).strip()
                else:
                    section_title = ""
                    section_content = str(item).strip()
                if section_content:
                    sections.append({"title": section_title, "content": section_content})

        raw_insights = payload.get("insights", [])
        insights = []
        if isinstance(raw_insights, list):
            insights = [str(item).strip() for item in raw_insights if str(item).strip()]

        if not title or not introduction or len(sections) < 3 or not conclusion or len(insights) < 3:
            return None

        return {
            "title": title,
            "introduction": introduction,
            "sections": sections[:3],
            "conclusion": conclusion,
            "insights": insights[:8],
        }

    @staticmethod
    def _render_structured_article_text(structured: Dict) -> str:
        """Version texte stable pour compatibilite resume, scoring et affichage legacy."""
        lines = [f"Titre: {structured.get('title', '')}", "", "Introduction:", str(structured.get("introduction", "")).strip(), "", "Developpements cles:"]

        for index, section in enumerate(structured.get("sections", []), start=1):
            section_title = str(section.get("title", "")).strip() or f"Section {index}"
            section_content = str(section.get("content", "")).strip()
            lines.append(f"{index}. {section_title}")
            lines.append(section_content)
            lines.append("")

        lines.append("Conclusion:")
        lines.append(str(structured.get("conclusion", "")).strip())
        lines.append("")
        lines.append("Key insights:")
        for insight in structured.get("insights", []):
            lines.append(f"- {str(insight).strip()}")

        return "\n".join(lines).strip()

    def _is_mostly_french(self, text: str) -> bool:
        txt = self._clean_text(text).lower()
        if not txt:
            return False

        tokens = re.findall(r"[a-zA-Z]+", txt)
        if not tokens:
            return False

        fr_words = {
            "le", "la", "les", "de", "des", "du", "un", "une", "et", "en", "dans",
            "sur", "pour", "par", "avec", "est", "sont", "ce", "cette", "ces", "que",
            "qui", "pas", "plus", "analyse", "marche", "entreprise", "contenu", "strategie",
            "industrie", "energie", "technologie", "gouvernement", "economie", "politique",
        }
        en_words = {
            "the", "and", "for", "with", "from", "that", "this", "are", "is", "was",
            "were", "will", "market", "business", "news", "analysis", "company", "content",
        }

        fr_count = sum(1 for token in tokens if token in fr_words)
        en_count = sum(1 for token in tokens if token in en_words)
        return (fr_count >= en_count + 2) or (fr_count >= 4)

    def _contains_significant_english(self, text: str) -> bool:
        txt = self._clean_text(text).lower()
        if not txt:
            return False

        tokens = re.findall(r"[a-zA-Z]+", txt)
        if not tokens:
            return False

        en_words = {
            "the", "and", "for", "with", "from", "that", "this", "are", "is", "was",
            "were", "will", "market", "business", "news", "analysis", "company", "content",
            "official", "group", "work", "trial", "leader", "team",
        }
        en_hits = sum(1 for token in tokens if token in en_words)
        return en_hits >= 6

    def classify_editorial_sector(self, article_data: Dict) -> str:
        raw = self._clean_text(
            f"{article_data.get('titre', '')} {article_data.get('contenu', '')} {' '.join(article_data.get('etiquettes', []))}"
        ).lower()
        rules = {
            "geopolitique": ["guerre", "conflit", "sanctions", "diplomatie", "geopolitique"],
            "politique": ["election", "gouvernement", "politique", "assemblee", "ministere"],
            "economie": ["economie", "inflation", "pib", "recession", "commerce"],
            "business": ["entreprise", "societe", "strategie", "marche", "croissance"],
            "finance": ["banque", "financement", "investissement", "bourse", "credit"],
            "energie": ["energie", "petrole", "gaz", "renouvelable", "electricite"],
            "climat": ["climat", "emissions", "carbone", "rechauffement", "durabilite"],
            "industrie": ["industrie", "manufacturier", "usine", "production", "site"],
            "automobile": ["automobile", "voiture", "vehicule", "electrique", "mobilite"],
            "aerospatial": ["aerospatial", "aviation", "avion", "airbus", "boeing"],
            "transport": ["transport", "rail", "fret", "logistique", "port"],
            "logistique": ["logistique", "entrepot", "livraison", "approvisionnement", "chaine d'approvisionnement"],
            "immobilier": ["immobilier", "propriete", "logement", "hypotheque", "construction"],
            "commerce": ["commerce", "distribution", "consommateur", "vente", "achat"],
            "telecom": ["telecom", "5g", "reseau", "operateur", "bande passante"],
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
            "emploi": ["emploi", "recrutement", "travail", "salaire", "embauche"],
            "defense": ["defense", "militaire", "armee", "missile", "securite"],
            "science": ["science", "recherche", "etude", "laboratoire", "innovation"],
            "space": ["espace", "nasa", "satellite", "fusee", "orbite"],
        }
        for sector, keywords in rules.items():
            if any(keyword in raw for keyword in keywords):
                return sector
        return article_data.get("secteur_estime", "general")

    def _calculate_quality_score(self, article_content: str, source_text: str) -> int:
        quality_markers = ["Titre:", "Introduction:", "Developpements cles:", "Conclusion:", "Key insights:"]
        length_score = min(len(article_content) / 1200, 1.0) * 40
        structure_score = (sum(1 for marker in quality_markers if marker in article_content) / len(quality_markers)) * 35
        overlap_score = 0
        if source_text:
            overlap_terms = [term for term in self.generate_keywords(source_text, num_keywords=6) if term in article_content.lower()]
            overlap_score = (len(overlap_terms) / 6) * 25
        return max(0, min(100, round(length_score + structure_score + overlap_score)))

    @staticmethod
    def _normalize_provider_chain(raw_chain: str) -> List[str]:
        providers = [item.strip().lower() for item in str(raw_chain).split(",") if item.strip()]
        if not providers:
            providers = ["groq", "gemini"]
        providers = ["groq" if provider == "grok" else provider for provider in providers]
        providers = [provider for provider in providers if provider in {"groq", "gemini"}]
        return providers

    def __init__(self, model_name: str = None):
        self.provider_chain = self._normalize_provider_chain(AI_PROVIDER_CHAIN)
        self.groq_model_name = model_name or GROQ_MODEL_NAME
        self.gemini_model_name = GEMINI_MODEL_NAME
        self.model_name = self.groq_model_name

        self.groq_api_key = GROQ_API_KEY
        self.groq_api_base = GROQ_API_BASE.rstrip("/")
        self.groq_timeout = GROQ_TIMEOUT_SECONDS
        self.groq_client = None
        if self.groq_api_key and OpenAI is not None:
            self.groq_client = OpenAI(api_key=self.groq_api_key, base_url=self.groq_api_base)
        elif self.groq_api_key:
            logger.warning("Paquet openai absent: le provider Groq est desactive")

        self.gemini_api_key = GOOGLE_GEMINI_API_KEY
        self.gemini_api_base = GEMINI_API_BASE.rstrip("/")
        self.gemini_timeout = GEMINI_TIMEOUT_SECONDS

        available = []
        for provider in self.provider_chain:
            if provider == "groq" and self.groq_api_key:
                available.append("groq")
            elif provider == "gemini" and self.gemini_api_key:
                available.append("gemini")

        self.provider_chain = available
        if not self.provider_chain:
            raise ValueError(
                "Aucun provider IA disponible: configurez GROQ_API_KEY ou GOOGLE_GEMINI_API_KEY"
            )
        logger.info(f"Chaine IA active: {self.provider_chain}")

    def _call_groq(self, prompt: str, max_tokens: int, temperature: float) -> Optional[str]:
        if not self.groq_client:
            return None

        try:
            max_completion_tokens = max(900, int(max_tokens) + 700)
            response = self.groq_client.chat.completions.create(
                model=self.groq_model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=float(temperature),
                max_completion_tokens=max_completion_tokens,
                reasoning_effort="low",
            )
            choices = getattr(response, "choices", [])
            if not choices:
                return None
            text = self._clean_text(choices[0].message.content or "")
            return text or None
        except Exception as exc:
            logger.warning(f"Appel Groq indisponible: {exc}")
            return None

    def _call_gemini(self, prompt: str, max_tokens: int, temperature: float) -> Optional[str]:
        if not self.gemini_api_key:
            return None

        url = f"{self.gemini_api_base}/models/{self.gemini_model_name}:generateContent?key={self.gemini_api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": float(temperature),
                "maxOutputTokens": int(max_tokens),
                "topP": 0.9,
            },
        }

        try:
            response = requests.post(url, json=payload, timeout=self.gemini_timeout)
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "\n".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
            return self._clean_text(text) if text else None
        except requests.RequestException as exc:
            logger.warning(f"Appel Gemini indisponible: {exc}")
            return None

    def _generate_text_via_providers(self, prompt: str, max_tokens: int, temperature: float) -> Tuple[Optional[str], str]:
        for provider in self.provider_chain:
            if provider == "groq":
                text = self._call_groq(prompt, max_tokens=max_tokens, temperature=temperature)
                if text:
                    return text, "groq_api"
            elif provider == "gemini":
                text = self._call_gemini(prompt, max_tokens=max_tokens, temperature=temperature)
                if text:
                    return text, "gemini_api"
        return None, ""

    def _model_for_source(self, source_llm: str) -> str:
        if source_llm == "groq_api":
            return self.groq_model_name
        if source_llm == "gemini_api":
            return self.gemini_model_name
        return "inconnu"

    def create_prompt(self, article_data: Dict) -> str:
        title = article_data.get("titre", "Actualite")
        keywords = ", ".join(article_data.get("etiquettes", [])[:5])
        source_content = article_data.get("contenu", "")[:2000]
        sector = self.classify_editorial_sector(article_data)
        strict_rules = [
            "Ne pas inventer d'informations",
            "Ne pas copier les phrases des sources",
            "Eviter les repetitions",
            "Se concentrer sur une thematique principale",
            "Adopter un ton professionnel, analytique et oriente metier",
        ]
        if GENERATION_STRICT_FACTUAL:
            strict_rules.append("Si une information est absente, l'indiquer explicitement")
        rules_block = "\n".join(f"- {rule}" for rule in strict_rules)
        return (
            "Tu es un journaliste senior specialise dans l'analyse economique, industrielle et strategique.\n\n"
            "Objectif:\n"
            "Produire un article professionnel structure en JSON, a forte valeur ajoutee, a partir de plusieurs sources d'information.\n\n"
            "Contexte:\n"
            "Les informations fournies proviennent de plusieurs articles. Tu dois faire une synthese coherente et intelligente.\n\n"
            "Contraintes strictes:\n"
            f"{rules_block}\n\n"
            "Regles de sortie (obligatoires):\n"
            "- Retourner uniquement un objet JSON valide, sans markdown, sans texte avant/apres.\n"
            "- Respecter exactement ce schema:\n"
            "  {\n"
            "    \"title\": \"...\",\n"
            "    \"introduction\": \"...\",\n"
            "    \"sections\": [\n"
            "      {\"title\": \"...\", \"content\": \"...\"},\n"
            "      {\"title\": \"...\", \"content\": \"...\"},\n"
            "      {\"title\": \"...\", \"content\": \"...\"}\n"
            "    ],\n"
            "    \"conclusion\": \"...\",\n"
            "    \"insights\": [\"...\", \"...\", \"...\"]\n"
            "  }\n"
            "- Exactement 3 sections.\n"
            "- Au moins 3 insights concis et actionnables.\n"
            "- Ton professionnel, analytique, factuel.\n\n"
            "Contexte editorial:\n"
            f"Secteur: {sector}\n"
            f"Mots-cles: {keywords}\n\n"
            "Informations sources:\n"
            f"Titre original: {title}\n"
            f"Source principale: {article_data.get('source', 'Source')}\n\n"
            "Contenu (multi-source):\n"
            f"{source_content}\n\n"
            "JSON:\n"
        )

    def generate_article(self, article_data: Dict, max_new_tokens: int = GENERATION_MAX_NEW_TOKENS) -> Dict:
        try:
            secteur_ia = self.classify_editorial_sector(article_data)
            prompt = self.create_prompt(article_data)
            deterministic_temp = min(float(GENERATION_TEMPERATURE), 0.2)
            raw_output, source_llm = self._generate_text_via_providers(
                prompt=prompt,
                max_tokens=max_new_tokens,
                temperature=deterministic_temp,
            )

            if not raw_output:
                raise RuntimeError("Aucun contenu genere par les providers IA")

            structured = self._normalize_structured_article(
                self._extract_json_object(raw_output) or {}
            )
            if not structured:
                raise ValueError("Le provider IA n'a pas retourne un JSON article valide")

            article_content = self._render_structured_article_text(structured)

            if (
                (not self._is_mostly_french(article_content))
                or self._contains_significant_english(article_content)
            ):
                raise ValueError("Le contenu genere n'est pas suffisamment francophone")

            mots_cles = article_data.get("etiquettes", [])
            if not isinstance(mots_cles, list) or not mots_cles:
                fallback_text = " ".join([
                    self._clean_text(article_data.get("titre", "")),
                    self._clean_text(article_data.get("contenu", "")),
                    self._clean_text(article_content),
                ]).strip()
                mots_cles = self.generate_keywords(fallback_text, num_keywords=6)
            if not mots_cles:
                raise ValueError("Extraction de mots-cles insuffisante")

            quality_score = self._calculate_quality_score(article_content, self._clean_text(article_data.get("contenu", "")))
            return {
                "titre_original": article_data.get("titre"),
                "source_originale": article_data.get("source"),
                "publication_originale": article_data.get("publie"),
                "contenu_genere": article_content,
                "mots_cles": mots_cles,
                "langue": "fr",
                "date_generation": datetime.now().isoformat(),
                "modele_utilise": self._model_for_source(source_llm),
                "statut_generation": "succes",
                "score_qualite": quality_score,
                "secteur_ia": secteur_ia,
                "angle_editorial": f"Analyse {secteur_ia} orientee impact metier",
                "source_llm": source_llm,
                "contenu_structure": structured,
            }
        except Exception as exc:
            logger.error(f"Erreur pendant la generation d'article: {str(exc)}")
            raise

    def _split_sentences_for_summary(self, text: str) -> List[str]:
        if not isinstance(text, str):
            return []
        return [sentence.strip() for sentence in re.split(r"[.!?]+", text) if sentence.strip()]

    def generate_summary(self, text: str, max_length: int = 120) -> str:
        try:
            clean_text = self._clean_text(text)
            if not clean_text:
                return ""

            prompt = (
                "Resume le texte suivant en francais en 3 phrases maximum, avec un ton professionnel et factuel.\n\n"
                f"Texte:\n{clean_text[:3000]}\n\nResume:\n"
            )
            model_summary, _ = self._generate_text_via_providers(
                prompt,
                max_tokens=max(90, min(max_length + 40, 220)),
                temperature=0.3,
            )
            if model_summary:
                return model_summary

            sentences = self._split_sentences_for_summary(clean_text)
            sentence_count = max(2, min(4, len(sentences) // 3 if len(sentences) > 2 else len(sentences)))
            summary = ". ".join(sentences[:sentence_count]).strip()
            if summary and not summary.endswith("."):
                summary += "."
            return summary
        except Exception:
            return text[:max_length]

    def create_linkedin_prompt(self, generated_article: str, topic: str, keywords: Optional[List[str]] = None) -> str:
        kw = ", ".join((keywords or [])[:6])
        return f"""
Tu es un expert communication B2B sur LinkedIn.

Objectif:
Transformer l'article suivant en un post LinkedIn premium, clair et engageant.

Contraintes:
- 900 caracteres maximum
- Pas de clickbait ni d'affirmations non justifiees
- Ton professionnel, actionnable, oriente decideurs
- 1 accroche forte au debut
- 3 idees actionnables en puces courtes
- 1 question finale pour lancer la discussion
- 3 hashtags maximum, pertinents et non generiques

Contexte:
Sujet: {topic}
Mots-cles: {kw}

Texte source:
{generated_article[:2200]}

Publication LinkedIn:
"""

    def generate_linkedin_post(self, generated_article: str, topic: str, keywords: Optional[List[str]] = None) -> str:
        prompt = self.create_linkedin_prompt(generated_article, topic, keywords)
        text, _ = self._generate_text_via_providers(prompt, max_tokens=280, temperature=0.55)
        if text:
            return text[:900]

        summary = self.generate_summary(generated_article, max_length=140)
        bullets = [
            "Prioriser les signaux a impact metier immediat.",
            "Aligner les equipes operations, produit et communication.",
            "Transformer les tendances en plan d'action sous 30 jours.",
        ]
        kw = [keyword for keyword in (keywords or []) if isinstance(keyword, str) and keyword.strip()][:3]
        hashtags = " ".join(f"#{keyword.replace(' ', '')}" for keyword in kw) if kw else "#industrie #strategie #innovation"
        return (
            f"{topic.title()}: les signaux faibles deviennent des decisions fortes.\n\n"
            f"{summary}\n\n"
            f"- {bullets[0]}\n"
            f"- {bullets[1]}\n"
            f"- {bullets[2]}\n\n"
            "Quel levier activeriez-vous en premier dans votre contexte ?\n\n"
            f"{hashtags}"
        )[:900]

    def generate_keywords(self, content: str, num_keywords: int = 5) -> List[str]:
        try:
            normalized = unicodedata.normalize("NFKC", content.lower())
            normalized = normalized.replace("'", " ").replace("-", " ")
            words = []
            for raw_word in normalized.split():
                token = "".join(char for char in raw_word if char.isalpha())
                if token:
                    words.append(token)
            stop_words = {
                "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
                "le", "la", "les", "de", "des", "du", "un", "une", "et", "en", "dans", "sur",
                "avec", "pour", "par", "au", "aux", "est", "sont", "ce", "cette", "ces",
            }
            keywords = []
            for word in words:
                token = word.strip("-_")
                if not token or token in stop_words or len(token) <= 3:
                    continue
                keywords.append(token)
            return list(dict.fromkeys(keywords))[:num_keywords]
        except Exception:
            return []

    def batch_generate_articles(self, articles_data: List[Dict]) -> List[Dict]:
        generated_articles = []
        for index, article_data in enumerate(articles_data, 1):
            logger.info(f"Generation article {index}/{len(articles_data)}")
            generated_articles.append(self.generate_article(article_data))
        logger.info(f"{len(generated_articles)} articles generes dans le lot")
        return generated_articles

    def save_generated_articles(self, articles: List[Dict], filepath: str):
        with open(filepath, "w", encoding="utf-8") as handle:
            json.dump(articles, handle, indent=2, ensure_ascii=False)
        logger.info(f"{len(articles)} articles generes enregistres dans {filepath}")


if __name__ == "__main__":
    import pandas as pd
    from src.config import CLEANED_DATA_FILE, GENERATED_ARTICLES_FILE, GENERATED_ARTICLES_LIMIT

    df = pd.read_json(CLEANED_DATA_FILE)
    articles_data = df.head(GENERATED_ARTICLES_LIMIT).to_dict("records")
    generator = ArticleGenerator()
    generated = generator.batch_generate_articles(articles_data)
    generator.save_generated_articles(generated, str(GENERATED_ARTICLES_FILE))

    print("\n=== ARTICLES GENERES ===")
    for index, article in enumerate(generated, 1):
        print(f"\n{index}. {article.get('titre_original', 'N/A')}")
        print(f"   Statut: {article.get('statut_generation')}")
