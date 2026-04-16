"""Module de nettoyage et de pretraitement des donnees."""

import json
import pandas as pd
import re
import logging
import html
from typing import List, Dict
from datetime import datetime
from src.config import MIN_ARTICLE_LENGTH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataCleaner:
    """Gere le nettoyage et le pretraitement des donnees."""

    REQUIRED_COLUMNS = {
        "titre": "Sans titre",
        "contenu": "Contenu non disponible",
        "source": "Inconnue",
        "lien": "",
        "publie": "",
        "auteurs": "Inconnu",
        "etiquettes": [],
        "date_collecte": "",
        "source_donnee": "N/D",
        "secteur_estime": "general",
    }
    
    def __init__(self):
        # Mots vides courants (sans NLTK)
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might'
        }
        self.cleaning_report = {}
    
    def load_raw_data(self, filepath: str) -> pd.DataFrame:
        """Charger les donnees brutes depuis un fichier JSON."""
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        return pd.DataFrame(data)

    def ensure_required_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Garantir un schema minimal stable entre les differents modules."""
        for col, default_value in self.REQUIRED_COLUMNS.items():
            if col not in df.columns:
                df[col] = [default_value for _ in range(len(df))]
        return df

    @staticmethod
    def _safe_list(value):
        if isinstance(value, list):
            return [str(v).strip().lower() for v in value if str(v).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip().lower()]
        return []

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        if not isinstance(text, str):
            return []
        return [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]

    def deep_clean_text(self, text: str) -> str:
        """Nettoyage profond multi-etapes du texte."""
        if not isinstance(text, str):
            return ""

        cleaned = html.unescape(text)
        cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
        cleaned = re.sub(r'http\S+|www\S+', ' ', cleaned)
        cleaned = cleaned.replace('\xa0', ' ').replace('\u200b', ' ')
        cleaned = re.sub(r'\[[^\]]{1,50}\]', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    
    def remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Supprimer les articles en double."""
        initial_count = len(df)
        if 'lien' in df.columns:
            df = df.drop_duplicates(subset=['lien'], keep='first')

        df['signature_dedoublonnage'] = (
            df['titre'].astype(str).str.lower().str.strip() + "|" +
            df['contenu'].astype(str).str.lower().str.slice(0, 220).str.strip()
        )
        df = df.drop_duplicates(subset=['signature_dedoublonnage'], keep='first')
        removed = initial_count - len(df)
        self.cleaning_report['doublons_supprimes'] = removed
        logger.info(f"{removed} articles en double supprimes")
        return df
    
    def handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Traiter les valeurs manquantes."""
        missing_counts = df.isnull().sum()
        logger.info(f"Valeurs manquantes avant nettoyage:\n{missing_counts}")
        
        # Remplir les valeurs manquantes
        df['contenu'] = df['contenu'].fillna('Contenu non disponible')
        df['auteurs'] = df['auteurs'].fillna('Inconnu')
        df['etiquettes'] = df['etiquettes'].apply(self._safe_list)
        df['titre'] = df['titre'].fillna('Sans titre')
        
        self.cleaning_report['valeurs_manquantes_comblees'] = int(missing_counts.sum())
        return df
    
    def normalize_text(self, text: str) -> str:
        """Normaliser le texte pour l'analyse."""
        # Convertir en minuscules
        text = text.lower()
        # Supprimer les URLs
        text = re.sub(r'http\S+|www\S+', '', text)
        # Supprimer les caracteres speciaux
        text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
        # Supprimer les espaces multiples
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def clean_articles(self, df: pd.DataFrame) -> pd.DataFrame:
        """Nettoyer le contenu des articles."""
        df['titre'] = df['titre'].astype(str).apply(self.deep_clean_text)
        df['contenu'] = df['contenu'].astype(str).apply(self.deep_clean_text)

        # Version exploitable pour l'analyse linguistique et la generation.
        df['contenu_profond'] = df['contenu'].apply(self.deep_clean_text)
        df['titre_profond'] = df['titre'].apply(self.deep_clean_text)
        df['contenu_nettoye'] = df['contenu_profond'].apply(self.normalize_text)
        df['titre_nettoye'] = df['titre_profond'].apply(self.normalize_text)

        # Garder des etiquettes normalisees et dedoublonnees.
        df['etiquettes'] = df['etiquettes'].apply(self._safe_list).apply(
            lambda tags: list(dict.fromkeys(tags))
        )
        return df
    
    def validate_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Valider la qualite des donnees."""
        initial_count = len(df)

        strict_df = df.copy()
        # Supprimer les articles sans contenu exploitable et imposer une longueur minimale realiste.
        strict_df = strict_df[strict_df['contenu_nettoye'].str.len() >= max(60, int(MIN_ARTICLE_LENGTH * 0.6))]

        # Supprimer les articles sans titre qualitatif.
        strict_df = strict_df[strict_df['titre'].notna() & (strict_df['titre'].str.len() >= 8)]

        # Filtrer les contenus faibles en nombre de mots.
        strict_df['mots_contenu'] = strict_df['contenu_profond'].apply(lambda x: len(str(x).split()))
        strict_df = strict_df[strict_df['mots_contenu'] >= 10]

        # Filtrer les contenus trop pauvres en structure.
        strict_df['phrases_contenu'] = strict_df['contenu_profond'].apply(lambda x: len(self._split_sentences(str(x))))
        strict_df = strict_df[strict_df['phrases_contenu'] >= 1]

        df = strict_df
        
        removed = initial_count - len(df)
        self.cleaning_report['articles_invalides_supprimes'] = removed
        logger.info(f"{removed} articles invalides supprimes")

        if df.empty:
            raise ValueError("Aucun article ne satisfait les criteres stricts de qualite")
        
        return df
    
    def add_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ajouter les metadonnees calculees."""
        df['nombre_mots'] = df['contenu_profond'].apply(lambda x: len(str(x).split()))
        df['nombre_caracteres'] = df['contenu_profond'].apply(lambda x: len(str(x)))
        df['nombre_phrases'] = df['contenu_profond'].apply(
            lambda x: len(self._split_sentences(str(x)))
        )

        df['nombre_mots'] = pd.to_numeric(df['nombre_mots'], errors='coerce').fillna(0.0)
        df['nombre_caracteres'] = pd.to_numeric(df['nombre_caracteres'], errors='coerce').fillna(0.0)
        df['nombre_phrases'] = pd.to_numeric(df['nombre_phrases'], errors='coerce').fillna(0.0)

        # Signal de qualite pour la selection dynamique des themes.
        df['score_qualite_source'] = (
            (df['nombre_mots'].clip(upper=350) / 350) * 0.45 +
            (df['nombre_phrases'].clip(upper=18) / 18) * 0.35 +
            (df['nombre_caracteres'].clip(upper=2500) / 2500) * 0.20
        ).round(4)

        # Utiliser le contenu profond comme base downstream.
        df['contenu'] = df['contenu_profond']
        df['titre'] = df['titre_profond']
        
        return df
    
    def clean_pipeline(self, filepath: str) -> pd.DataFrame:
        """Executer le pipeline complet de nettoyage."""
        logger.info("Demarrage du pipeline de nettoyage...")
        
        df = self.load_raw_data(filepath)
        df = self.ensure_required_columns(df)
        initial_rows = len(df)
        logger.info(f"Nombre initial d'enregistrements: {initial_rows}")
        
        df = self.handle_missing_values(df)
        df = self.remove_duplicates(df)
        df = self.clean_articles(df)
        df = self.validate_data(df)
        df = self.add_metadata(df)
        
        final_rows = len(df)
        if 'signature_dedoublonnage' in df.columns:
            df = df.drop(columns=['signature_dedoublonnage'])

        self.cleaning_report['enregistrements_initiaux'] = initial_rows
        self.cleaning_report['enregistrements_finaux'] = final_rows
        self.cleaning_report['enregistrements_supprimes'] = initial_rows - final_rows
        self.cleaning_report['date_nettoyage'] = datetime.now().isoformat()
        
        logger.info(f"Nettoyage termine. Enregistrements finaux: {final_rows}")
        return df
    
    def save_cleaned_data(self, df: pd.DataFrame, filepath: str, validation_filepath: str = None):
        """Sauvegarder les donnees nettoyees en JSON et, si demande, une copie de validation."""
        df.to_json(filepath, orient='records', indent=2, force_ascii=False)
        logger.info(f"Donnees nettoyees enregistrees dans {filepath}")

        if validation_filepath:
            df.to_json(validation_filepath, orient='records', indent=2, force_ascii=False)
            logger.info(f"Copie de validation des donnees nettoyees enregistree dans {validation_filepath}")
    
    def get_cleaning_report(self) -> Dict:
        """Obtenir le rapport de nettoyage."""
        return self.cleaning_report


if __name__ == "__main__":
    # Exemple d'utilisation
    from src.config import RAW_DATA_FILE, CLEANED_DATA_FILE, VALIDATION_CLEANED_DATA_FILE
    
    cleaner = DataCleaner()
    df = cleaner.clean_pipeline(str(RAW_DATA_FILE))
    cleaner.save_cleaned_data(df, str(CLEANED_DATA_FILE), str(VALIDATION_CLEANED_DATA_FILE))
    
    print("\n=== RAPPORT DE NETTOYAGE ===")
    for key, value in cleaner.get_cleaning_report().items():
        print(f"{key}: {value}")
