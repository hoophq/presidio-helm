FROM mcr.microsoft.com/presidio-analyzer

# Install Flair and its dependencies
RUN poetry run pip install flair torch
# Install Flair models

COPY ./install_flair_models.py /usr/bin/presidio-analyzer/
RUN poetry run python install_flair_models.py --models flair/ner-english-large

# default app path from presidio analyzer base image
COPY ./flair_recognizer.py /usr/bin/presidio-analyzer

# override the main application that creates the flask api
COPY ./app.py /usr/bin/presidio-analyzer/app.py
