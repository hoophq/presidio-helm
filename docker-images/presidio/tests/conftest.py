"""Shared pytest configuration.

Puts the sibling ``extensions/`` directory on ``sys.path`` so tests can do
``from presidio_extensions.br_cpf import BrCpfRecognizer`` without needing
to install the package. This matches how the package is loaded at runtime
inside the container (``PYTHONPATH=/app/extensions``).
"""

import sys
from pathlib import Path

EXT_DIR = Path(__file__).resolve().parent.parent / "extensions"
if str(EXT_DIR) not in sys.path:
    sys.path.insert(0, str(EXT_DIR))
