#!/usr/bin/env python3
"""
Script to pre-download Flair models to avoid downloading at runtime.
This script should be run during Docker image build.
"""

import argparse
import logging
from typing import Dict

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_flair_models(models: Dict[str, str]):
    """
    Download Flair models specified in the models dictionary.
    
    Args:
        models: Dictionary mapping language codes to model names
    """
    try:
        from flair.models import SequenceTagger
        
        for lang, model_name in models.items():
            logger.info(f"Downloading Flair model for {lang}: {model_name}")
            try:
                # This will download and cache the model
                model = SequenceTagger.load(model_name)
                logger.info(f"Successfully downloaded {model_name}")
            except Exception as e:
                logger.error(f"Failed to download {model_name}: {e}")
                
    except ImportError as e:
        logger.error(f"Flair not installed: {e}")
        return

def main():
    parser = argparse.ArgumentParser(description="Download Flair models")
    parser.add_argument(
        "--models", 
        nargs="+", 
        default=["flair/ner-english-large"],
        help="List of Flair models to download"
    )
    
    args = parser.parse_args()
    
    # Default models from the FlairRecognizer
    default_models = {
        "en": "flair/ner-english-large",
        "es": "flair/ner-spanish-large", 
    }
    
    # Download only English model by default, or all if specified
    if args.models == ["flair/ner-english-large"]:
        models_to_download = {"en": "flair/ner-english-large"}
    else:
        models_to_download = {lang: model for lang, model in default_models.items() 
                            if model in args.models}
    
    logger.info(f"Downloading models: {models_to_download}")
    download_flair_models(models_to_download)

if __name__ == "__main__":
    main()
