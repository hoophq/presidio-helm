"""Local Presidio extensions package.

Re-exports recognizer classes so they're registered into
``EntityRecognizer.__subclasses__()`` as soon as the package is imported.
"""

from .br_cpf import BrCpfRecognizer

__all__ = ["BrCpfRecognizer"]
