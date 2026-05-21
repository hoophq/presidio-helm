"""Regression tests for ``BrCpfRecognizer``.

Run with:

    cd presidio-overlay
    pip install presidio-analyzer pytest
    pytest -v tests/

These tests don't need a spaCy model or a running Presidio server. They
exercise the recognizer class directly: ``PatternRecognizer.analyze``
accepts ``nlp_artifacts=None`` and the regex + checksum path is fully
synchronous.

All CPF values in this file are mathematically valid (the mod-11 checksum
passes) but are well-known test/example values documented in Brazilian
developer references — they are not real people's CPFs.
"""

import pytest

from presidio_extensions.br_cpf import BrCpfRecognizer


# --------------------------------------------------------------------------- #
#                              Fixtures / data                                #
# --------------------------------------------------------------------------- #

VALID_CPFS_FORMATTED = [
    "111.444.777-35",
    "390.533.447-05",
    "295.379.955-93",
    "529.982.247-25",
    "123.456.789-09",
]

VALID_CPFS_UNFORMATTED = [
    "11144477735",
    "39053344705",
    "29537995593",
    "52998224725",
    "12345678909",
]

# Same first 9 digits as a valid CPF but with one of the check digits
# altered. The checksum must reject these.
INVALID_CHECKSUMS = [
    "111.444.777-36",   # d2 off by one
    "111.444.777-25",   # d1 off by one
    "12345678900",
    "39053344704",
    "00000000001",      # one digit flipped from all-zeros
]

# All-same-digit strings. Each one passes the checksum *arithmetic* (both
# check digits compute back to the repeated digit), so they must be
# rejected by the explicit all-same-digit guard, not by the checksum.
ALL_SAME_DIGIT = [f"{d}" * 11 for d in range(10)]

MALFORMED = [
    "",
    "1234567890",          # 10 digits
    "123456789012",        # 12 digits
    "abcdefghijk",
    "111.444.777",         # truncated
    "111.444.777-XY",
    "           ",
    "11144477 35",         # space inside
]

# Non-ASCII digit shapes that Python's ``str.isdigit`` accepts but that we
# don't want to recognize as CPFs.
NON_ASCII_DIGITS = [
    "\uff11\uff11\uff11\uff14\uff14\uff14\uff17\uff17\uff17\uff13\uff15",  # full-width "11144477735"
    "\u0661\u0661\u0661\u0664\u0664\u0664\u0667\u0667\u0667\u0663\u0665",  # arabic-indic "11144477735"
]


@pytest.fixture(scope="module")
def recognizer():
    return BrCpfRecognizer()


# --------------------------------------------------------------------------- #
#                          validate_result (unit)                             #
# --------------------------------------------------------------------------- #


class TestValidateResult:
    """Direct tests of the mod-11 checksum and rejection rules."""

    @pytest.mark.parametrize(
        "cpf", VALID_CPFS_FORMATTED + VALID_CPFS_UNFORMATTED
    )
    def test_valid_cpf_passes(self, recognizer, cpf):
        assert recognizer.validate_result(cpf) is True

    @pytest.mark.parametrize("cpf", INVALID_CHECKSUMS)
    def test_invalid_checksum_fails(self, recognizer, cpf):
        assert recognizer.validate_result(cpf) is False

    @pytest.mark.parametrize("cpf", ALL_SAME_DIGIT)
    def test_all_same_digit_rejected(self, recognizer, cpf):
        # Passes checksum arithmetic; must be rejected by explicit guard.
        assert recognizer.validate_result(cpf) is False

    @pytest.mark.parametrize("text", MALFORMED)
    def test_malformed_input_rejected(self, recognizer, text):
        assert recognizer.validate_result(text) is False

    @pytest.mark.parametrize("text", NON_ASCII_DIGITS)
    def test_non_ascii_digits_rejected(self, recognizer, text):
        # CPFs are issued with ASCII digits only. Full-width and Arabic-
        # Indic digits must not be treated as CPFs even though Python's
        # ``str.isdigit`` returns True for them.
        assert recognizer.validate_result(text) is False

    def test_separators_are_ignored(self, recognizer):
        # Same 11 digits in two spellings → same verdict.
        assert recognizer.validate_result("11144477735") is True
        assert recognizer.validate_result("111.444.777-35") is True

    def test_empty_string(self, recognizer):
        assert recognizer.validate_result("") is False


# --------------------------------------------------------------------------- #
#                       analyze() integration tests                           #
# --------------------------------------------------------------------------- #


class TestAnalyze:
    """End-to-end tests through ``PatternRecognizer.analyze``.

    Verifies the regex layer, the checksum layer, and the score-clamping
    behavior of ``PatternRecognizer`` work together: a passing checksum
    lifts the score to 1.0, a failing one drops the match entirely.
    """

    def test_detects_formatted_cpf(self, recognizer):
        text = "Meu CPF é 111.444.777-35, obrigado."
        results = recognizer.analyze(text, entities=["BR_CPF"])

        assert len(results) == 1
        r = results[0]
        assert r.entity_type == "BR_CPF"
        assert r.score == 1.0
        assert text[r.start : r.end] == "111.444.777-35"

    def test_detects_unformatted_cpf(self, recognizer):
        text = "CPF 11144477735 cadastrado."
        results = recognizer.analyze(text, entities=["BR_CPF"])

        assert len(results) == 1
        assert results[0].entity_type == "BR_CPF"
        assert results[0].score == 1.0
        assert text[results[0].start : results[0].end] == "11144477735"

    def test_multiple_cpfs_in_text(self, recognizer):
        text = "Dois CPFs válidos: 111.444.777-35 e 39053344705."
        results = recognizer.analyze(text, entities=["BR_CPF"])

        spans = sorted((text[r.start : r.end] for r in results))
        assert spans == ["111.444.777-35", "39053344705"]
        assert all(r.score == 1.0 for r in results)

    def test_rejects_invalid_checksum(self, recognizer):
        text = "Inválido: 111.444.777-36"
        results = recognizer.analyze(text, entities=["BR_CPF"])
        assert results == []

    def test_rejects_all_same_digit(self, recognizer):
        text = "Placeholder: 11111111111"
        results = recognizer.analyze(text, entities=["BR_CPF"])
        assert results == []

    def test_no_cpf_in_text(self, recognizer):
        text = "Apenas um texto sem nenhum CPF aqui."
        results = recognizer.analyze(text, entities=["BR_CPF"])
        assert results == []

    def test_random_11_digit_run_not_matched(self, recognizer):
        # 11 consecutive digits with an invalid checksum should not match.
        # (Note: ``98765432100`` was a tempting "obviously invalid" choice
        # for this fixture but is in fact a mathematically valid CPF —
        # picking any old 11-digit run is surprisingly likely to hit a
        # valid one. ``98765432101`` flips the last digit, breaking d2.)
        text = "Pedido número 98765432101 finalizado."
        results = recognizer.analyze(text, entities=["BR_CPF"])
        assert results == []

    def test_brazilian_phone_not_matched(self, recognizer):
        # Brazilian mobile in conventional formatting — not a CPF.
        text = "Tel: (11) 99999-1234"
        results = recognizer.analyze(text, entities=["BR_CPF"])
        assert results == []

    @pytest.mark.parametrize("non_ascii", NON_ASCII_DIGITS)
    def test_non_ascii_digits_not_matched(self, recognizer, non_ascii):
        results = recognizer.analyze(non_ascii, entities=["BR_CPF"])
        assert results == []

    def test_cpf_inside_sentence_offsets(self, recognizer):
        # The reported start/end must slice back to exactly the CPF text.
        text = "Olá, meu CPF é 111.444.777-35 e mais nada."
        results = recognizer.analyze(text, entities=["BR_CPF"])
        assert len(results) == 1
        r = results[0]
        assert text[r.start : r.end] == "111.444.777-35"
        assert r.start == text.index("111.")
        assert r.end == r.start + len("111.444.777-35")

    def test_score_is_one_for_valid(self, recognizer):
        # The score clamping behavior of PatternRecognizer.analyze means
        # a passing checksum always yields exactly MAX_SCORE = 1.0,
        # regardless of the per-pattern original score (0.6 / 0.1).
        for cpf in (VALID_CPFS_FORMATTED[0], VALID_CPFS_UNFORMATTED[0]):
            results = recognizer.analyze(cpf, entities=["BR_CPF"])
            assert len(results) == 1
            assert results[0].score == 1.0

    def test_entities_filter_irrelevant_is_safe(self, recognizer):
        # Asking the recognizer for entities it doesn't support should
        # still be safe and produce no false positives.
        text = "Meu CPF é 111.444.777-35"
        results = recognizer.analyze(text, entities=["BR_CPF", "EMAIL_ADDRESS"])
        assert len(results) == 1
        assert results[0].entity_type == "BR_CPF"


# --------------------------------------------------------------------------- #
#                       Class-level metadata / contract                       #
# --------------------------------------------------------------------------- #


class TestRecognizerMetadata:
    """Lock the public contract of the recognizer."""

    def test_country_code(self):
        assert BrCpfRecognizer.COUNTRY_CODE == "br"

    def test_default_entity_is_br_cpf(self, recognizer):
        assert recognizer.supported_entities == ["BR_CPF"]

    def test_default_language_is_en(self, recognizer):
        assert recognizer.supported_language == "en"

    def test_has_two_patterns(self, recognizer):
        names = sorted(p.name for p in recognizer.patterns)
        assert names == ["CPF (formatted)", "CPF (unformatted)"]

    def test_context_includes_cpf_keyword(self, recognizer):
        assert "cpf" in recognizer.context

    def test_custom_entity_name_supported(self):
        r = BrCpfRecognizer(supported_entity="CPF")
        assert r.supported_entities == ["CPF"]

    def test_custom_language_supported(self):
        r = BrCpfRecognizer(supported_language="pt")
        assert r.supported_language == "pt"
