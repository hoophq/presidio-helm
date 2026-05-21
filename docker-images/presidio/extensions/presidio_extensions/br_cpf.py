"""Brazilian CPF (Cadastro de Pessoa Física) recognizer for Presidio Analyzer.

Registered into the analyzer registry via YAML using ``type: predefined`` and
``class_name: BrCpfRecognizer``. The class is auto-imported at interpreter
startup by ``sitecustomize.py`` (see ``extensions/sitecustomize.py``), which
puts it on ``EntityRecognizer.__subclasses__()`` so Presidio's loader can
resolve it without any modification to the upstream ``app.py``.
"""

from typing import List, Optional

from presidio_analyzer import Pattern, PatternRecognizer


class BrCpfRecognizer(PatternRecognizer):
    """Recognize Brazilian CPF numbers, with mod-11 checksum validation.

    The CPF (Cadastro de Pessoa Física) is the Brazilian individual taxpayer
    registry number: 11 digits, typically formatted as ``XXX.XXX.XXX-XX``,
    where the last two digits are check digits computed via a mod-11 algorithm
    over the first nine. The regex matches both formatted and unformatted
    runs; ``validate_result`` rejects matches that fail the checksum or that
    consist of a single repeated digit (e.g. ``11111111111``), which pass
    the checksum arithmetically but are reserved/invalid by convention.

    Because ``PatternRecognizer.analyze`` clamps the score to ``MAX_SCORE``
    when ``validate_result`` returns ``True``, any pattern match that passes
    the checksum will be reported with score 1.0. Matches that fail the
    checksum are dropped entirely.
    """

    COUNTRY_CODE = "br"

    # Use ASCII-only [0-9] rather than ``\d``: the underlying ``regex``
    # module treats ``\d`` as any Unicode decimal digit (full-width, Arabic-
    # Indic, …). CPFs are always ASCII, and accepting other scripts produces
    # spurious matches that pass the checksum (``int('１')`` is 1).
    PATTERNS = [
        Pattern(
            "CPF (formatted)",
            r"\b[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}\b",
            0.6,
        ),
        Pattern(
            "CPF (unformatted)",
            r"\b[0-9]{11}\b",
            0.1,
        ),
    ]

    # Context words in pt-BR. Presidio's lemma-based context enhancer treats
    # these as raw keywords, so they work even when the NLP engine is the
    # default English spaCy model. Include common synonyms and abbreviations.
    CONTEXT = [
        "cpf",
        "documento",
        "cadastro",
        "pessoa física",
        "pessoa fisica",
        "contribuinte",
        "receita federal",
    ]

    def __init__(
        self,
        patterns: Optional[List[Pattern]] = None,
        context: Optional[List[str]] = None,
        supported_language: str = "en",
        supported_entity: str = "BR_CPF",
        name: Optional[str] = None,
    ):
        super().__init__(
            supported_entity=supported_entity,
            patterns=patterns if patterns else self.PATTERNS,
            context=context if context else self.CONTEXT,
            supported_language=supported_language,
            name=name,
        )

    def validate_result(self, pattern_text: str) -> Optional[bool]:
        """Validate the CPF using its mod-11 checksum.

        :param pattern_text: The substring matched by the pattern; may
            include the ``.`` and ``-`` separators.
        :return: ``True`` if the 11 digits form a valid CPF, ``False``
            otherwise.
        """
        # ASCII-only on purpose: see the PATTERNS comment.
        digits = [c for c in pattern_text if "0" <= c <= "9"]
        if len(digits) != 11:
            return False

        # Reject all-same-digit CPFs (e.g., 11111111111). These pass the
        # checksum arithmetically but are reserved/invalid by convention.
        if len(set(digits)) == 1:
            return False

        nums = [int(d) for d in digits]

        # First check digit: weights 10..2 over the first 9 digits.
        s1 = sum(nums[i] * (10 - i) for i in range(9))
        d1 = 0 if s1 % 11 < 2 else 11 - (s1 % 11)
        if d1 != nums[9]:
            return False

        # Second check digit: weights 11..2 over the first 10 digits.
        s2 = sum(nums[i] * (11 - i) for i in range(10))
        d2 = 0 if s2 % 11 < 2 else 11 - (s2 % 11)
        if d2 != nums[10]:
            return False

        return True
