"""Point d'entree principal: execution de l'Automated AI Content Intelligence Pipeline."""

import sys
import logging
import json
import numpy as np

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline_execution.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SafeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)

def main():
    """Fonction principale d'execution."""
    from src.config import validate_config
    from src.automation_pipeline import AutomationPipeline
    
    logger.info("=" * 60)
    logger.info("AUTOMATED AI CONTENT INTELLIGENCE PIPELINE")
    logger.info("=" * 60)
    
    try:
        validate_config()

        # Initialiser et executer le pipeline
        pipeline = AutomationPipeline()
        results = pipeline.run_complete_pipeline()
        
        # Enregistrer les resultats d'execution
        with open('pipeline_execution_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, cls=SafeJSONEncoder)

        pipeline_ok = results.get("statut_pipeline") == "termine"
        
        logger.info("\n" + "=" * 60)
        logger.info("EXECUTION DU PIPELINE REUSSIE" if pipeline_ok else "EXECUTION DU PIPELINE EN ECHEC")
        logger.info("=" * 60)
        
        print("\n" + "=" * 60)
        print("RESUME D'EXECUTION")
        print("=" * 60)
        print(f"Run ID: {results.get('run_id', 'N/D')}")
        
        for etape in results['etapes']:
            status_symbol = "OK" if etape['statut'] == 'succes' else "ECHEC"
            print(f"{status_symbol} {etape.get('etape', 'N/D').upper()}: {etape['statut']}")
        
        print(f"\nDuree totale: {results['duree_secondes']:.2f} secondes")
        print("=" * 60)
        
        return 0 if pipeline_ok else 1
    
    except Exception as e:
        logger.error(f"Echec d'execution du pipeline: {str(e)}")
        print(f"\nERREUR: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
