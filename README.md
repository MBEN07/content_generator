# Pipeline de génération de contenu automatisé

Documentation technique de l'architecture, des outils et des methodes d'implementation.

<a id="toc"></a>
## Table des matieres

- [1) Architecture du systeme](#section-1)
- [2) Outils et dependances](#section-2)
- [3) Methodes par module](#section-3)
  - [3.1 Methodes de collecte](#section-31)
  - [3.2 Methodes de nettoyage et validation](#section-32)
  - [3.3 Methodes d'analyse](#section-33)
  - [3.4 Methodes de generation LLM](#section-34)
  - [3.5 Methodes d'orchestration](#section-35)
- [4) Runtime et configuration](#section-4)
- [5) Contrats d'artefacts](#section-5)
- [6) Execution](#section-6)

<a id="section-1"></a>
## 1) Architecture du systeme

[Retour a la Table des matieres](#toc)

Modules principaux du pipeline:
1. Collecte: [src/data_collection.py](src/data_collection.py)
2. Nettoyage et validation: [src/data_cleaning.py](src/data_cleaning.py)
3. Analyse et KPI: [src/data_analysis.py](src/data_analysis.py)
4. Generation LLM: [src/ai_generation.py](src/ai_generation.py)
5. Orchestration: [src/automation_pipeline.py](src/automation_pipeline.py)
6. Point d'entree runtime: [main.py](main.py)
7. Visualisation et controles: [src/dashboard.py](src/dashboard.py)

Configuration et constantes:
- [src/config.py](src/config.py)

### Flux de donnees

1. Les requetes RSS ciblees construisent les URLs de collecte.
2. Les articles sont recuperes, normalises, eventuellement filtres par langue, puis stockes en JSON brut.
3. Le pipeline de nettoyage impose un schema, dedoublonne, valide et enrichit les metadonnees.
4. Le module d'analyse calcule les statistiques, la concentration des sources, les secteurs, les mots-cles et les tendances.
5. L'etape de generation classe les topics, selectionne les principaux topics, fusionne les signaux et produit les sorties.
6. Le dashboard consomme les artefacts JSON pour le monitoring et l'interaction.

<a id="section-2"></a>
## 2) Outils et dependances

[Retour a la Table des matieres](#toc)

Dependances principales dans [requirements.txt](requirements.txt):
- pandas: transformations tabulaires et agregations.
- numpy: compatibilite numerique et support de conversion JSON sure.
- requests: requetes HTTP pour les pages RSS et les API LLM.
- feedparser: parsing de flux RSS.
- beautifulsoup4: parsing HTML et extraction de contenu.
- python-dotenv: chargement des variables d'environnement.
- schedule: planification periodique des taches.
- openai: client compatible Groq pour les chat completions.
- streamlit: couche interface et interaction.
- plotly: graphiques interactifs.

<a id="section-3"></a>
## 3) Methodes par module

[Retour a la Table des matieres](#toc)

<a id="section-31"></a>
### 3.1 Methodes de collecte

[Retour a la Table des matieres](#toc)

Implante dans [src/data_collection.py](src/data_collection.py):
- Strategie RSS Google News multi-requetes basee sur des chaines de requetes encodees.
- Durcissement reseau avec retry et backoff exponentiel.
- Resolution d'URL et canonicalisation avant extraction du contenu.
- Extraction full-text legere depuis HTML via selecteurs structurels et fallback paragraphe.
- Filtrage heuristique de la langue francaise.
- Estimation sectorielle basee sur des regles lexicales.

Sorties clefs:
- [data/raw_articles.json](data/raw_articles.json)

<a id="section-32"></a>
### 3.2 Methodes de nettoyage et validation

[Retour a la Table des matieres](#toc)

Implante dans [src/data_cleaning.py](src/data_cleaning.py):
- Stabilisation du schema avec colonnes obligatoires et valeurs par defaut.
- Nettoyage de texte approfondi:
	- decodage des entites HTML
	- suppression des balises
	- suppression des URL
	- normalisation des espaces
- Dedoublonnage a deux niveaux:
	- par lien
	- par signature textuelle sur titre + prefixe contenu
- Garde-fous qualite stricts:
	- longueur minimale du contenu normalise
	- longueur minimale du titre
	- nombre minimal de mots
	- structure minimale en phrases
- Enrichissement des metadonnees:
	- nombre de mots
	- nombre de caracteres
	- nombre de phrases
	- score de qualite source

Sorties clefs:
- [data/cleaned_articles.json](data/cleaned_articles.json)
- [output/cleaned_articles_validation.json](output/cleaned_articles_validation.json)

<a id="section-33"></a>
### 3.3 Methodes d'analyse

[Retour a la Table des matieres](#toc)

Implante dans [src/data_analysis.py](src/data_analysis.py):
- Statistiques descriptives de base.
- Metriques de fraicheur basees sur les horodatages de publication.
- Metriques de concentration des sources:
	- part de la source dominante
	- HHI (Herfindahl-Hirschman Index)
- Analyse de distribution sectorielle.
- Extraction de mots-cles a partir des tags et titres avec filtrage des stop words.
- Estimation signal/bruit sur les tokens extraits.
- Analyse de tendance en serie temporelle:
	- volumes journaliers
	- moyenne glissante
	- croissance sur 7 jours
	- coefficient de variation
- Generation deterministe de phrases d'insights a partir des KPI calcules.

Sorties clefs:
- [output/analysis_kpis.json](output/analysis_kpis.json)

<a id="section-34"></a>
### 3.4 Methodes de generation LLM

[Retour a la Table des matieres](#toc)

Implante dans [src/ai_generation.py](src/ai_generation.py):
- Selection de la chaine de providers via la configuration d'environnement.
- Providers principal et fallback:
	- Groq via client compatible OpenAI
	- Gemini via endpoint REST
- Prompting strict a sortie structuree (schema JSON attendu).
- Extraction et normalisation robuste du JSON depuis le texte modele.
- Garde-fous qualite sur la langue francaise du contenu genere.
- Classification editoriale sectorielle basee sur des regles.
- Scoring de qualite de generation base sur structure, longueur et recouvrement lexical.
- Generation auxiliaire:
	- resumes concis
	- posts prets pour LinkedIn

Sorties clefs:
- [output/generated_articles.json](output/generated_articles.json)
- [output/ia_examples.json](output/ia_examples.json) (artefact optionnel selon l'etat du dernier run)

<a id="section-35"></a>
### 3.5 Methodes d'orchestration

[Retour a la Table des matieres](#toc)

Implante dans [src/automation_pipeline.py](src/automation_pipeline.py):
- Orchestration des etapes de bout en bout avec comportement fail-fast.
- Journalisation d'evenements structuree et mesure de duree par etape.
- Generation d'un run ID pour la tracabilite.
- Classification de topics en parallele et generation de topics en parallele.
- Selection dynamique des top topics via criteres de qualite et de diversite.
- Methode de synthese multi-source pour la construction des payloads de topics.

Artefact d'execution:
- [pipeline_execution_results.json](pipeline_execution_results.json)

<a id="section-4"></a>
## 4) Runtime et configuration

[Retour a la Table des matieres](#toc)

Fichier de configuration:
- [src/config.py](src/config.py)

Controles runtime notables:
- Packs de themes RSS et requetes personnalisees.
- Limites de collecte: cible min/max d'articles, max articles par requete.
- Chaine de providers LLM et noms de modeles.
- Toggles et limites de generation.
- Validation de l'intervalle et de l'heure de planification.

Template d'environnement:
- [.env.example](.env.example)

<a id="section-5"></a>
## 5) Contrats d'artefacts

[Retour a la Table des matieres](#toc)

Artefacts actuels utilises par les modules et le dashboard:
- [data/raw_articles.json](data/raw_articles.json): enregistrements collectes.
- [data/cleaned_articles.json](data/cleaned_articles.json): enregistrements valides et enrichis.
- [output/cleaned_articles_validation.json](output/cleaned_articles_validation.json): copie de validation des donnees nettoyees.
- [output/analysis_kpis.json](output/analysis_kpis.json): rapport d'analyse et payload KPI.
- [output/generated_articles.json](output/generated_articles.json): articles generes et enrichissements associes.
- [pipeline_execution_results.json](pipeline_execution_results.json): trace d'execution et metriques par etape.

<a id="section-6"></a>
## 6) Execution

[Retour a la Table des matieres](#toc)

Installation:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Execution du pipeline complet:

```bash
python main.py
```

Execution du dashboard:

```bash
streamlit run src/dashboard.py
```
