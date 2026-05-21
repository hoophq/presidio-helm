# syntax=docker/dockerfile:1.7
FROM mcr.microsoft.com/presidio-analyzer:2.2.362

# --- Cache TLD list for the EMAIL_ADDRESS recognizer at build time. ---
# https://github.com/microsoft/presidio/issues/1205
RUN poetry run tldextract --update

# --- Add the BR_CPF extension. ---
#
# Layout in the image:
#   /app/extensions/
#     presidio_extensions.pth          -> installed into site-packages below;
#                                         processed by site.py at Python
#                                         startup, adds /app and
#                                         /app/extensions to sys.path and
#                                         imports presidio_extensions
#     presidio_extensions/             -> our package
#       __init__.py
#       br_cpf.py                      -> BrCpfRecognizer class
#     conf/
#       br-cpf-overlay.yml             -> only our additions to the registry
#       recognizers.yml                -> produced at build time below;
#                                         RECOGNIZER_REGISTRY_CONF_FILE points
#                                         here at runtime
#
# We never modify any file shipped by the upstream image. The overlay YAML
# is merged with the upstream defaults into a *new* file at a *new* path,
# and the extension is loaded via a *new* .pth file dropped into the
# interpreter's site-packages.
USER root

COPY --chown=presidio:presidio extensions/ /app/extensions/
COPY --chown=presidio:presidio conf/br-cpf-overlay.yml /app/extensions/conf/br-cpf-overlay.yml

# Install the .pth file into the interpreter's site-packages so Python's
# site.py picks it up at every interpreter startup. This is the key bit
# that makes the image truly drop-in: it doesn't matter how gunicorn is
# invoked (poetry run gunicorn, plain gunicorn, with or without --config,
# under the Hoop Helm chart that overrides command + GUNICORN_CMD_ARGS) —
# the import happens before any user code runs.
RUN python -c "import shutil, sysconfig; shutil.copy('/app/extensions/presidio_extensions.pth', sysconfig.get_paths()['purelib'])"

# Merge the upstream defaults with our overlay into a single registry file.
# Runs once at build time. PyYAML is already installed (Presidio depends on it).
RUN python <<'PY'
import yaml

UPSTREAM = "/app/presidio_analyzer/conf/default_recognizers.yaml"
OVERLAY  = "/app/extensions/conf/br-cpf-overlay.yml"
MERGED   = "/app/extensions/conf/recognizers.yml"

with open(UPSTREAM) as f:
    base = yaml.safe_load(f)
with open(OVERLAY) as f:
    overlay = yaml.safe_load(f) or {}

base.setdefault("recognizers", [])
overlay_recognizers = overlay.get("recognizers") or []

# Append only entries whose `name` isn't already present, so the overlay can
# safely be re-run without producing duplicates if a future upstream release
# adds a recognizer with the same name.
existing = {r.get("name") for r in base["recognizers"] if isinstance(r, dict)}
for r in overlay_recognizers:
    if isinstance(r, dict) and r.get("name") in existing:
        continue
    base["recognizers"].append(r)

with open(MERGED, "w") as f:
    yaml.safe_dump(base, f, sort_keys=False, allow_unicode=True)
PY

RUN chown -R presidio:presidio /app/extensions

# Point Presidio at the merged registry. The upstream image already sets
# ANALYZER_CONF_FILE and NLP_CONF_FILE; we leave those alone. Pod-level env
# in Kubernetes can still override this if needed, but the chart doesn't
# touch it.
ENV RECOGNIZER_REGISTRY_CONF_FILE=/app/extensions/conf/recognizers.yml

USER 1001
