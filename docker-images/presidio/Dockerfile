FROM mcr.microsoft.com/presidio-analyzer:2.2.359

# cache publicsuffix to avoid HTTP requests when using the EMAIL_ADDRESS entity
# https://github.com/microsoft/presidio/issues/1205
RUN poetry run tldextract --update
