from halal_scanner.classifier import HalalClassifier
from halal_scanner.rulebook import Rulebook
from halal_scanner.models import (
    Status, Source, Confidence, IngredientResult,
)


class FakeGemma:
    """Stand-in for GemmaClient. Returns a preset result or None."""
    def __init__(self, result=None):
        self.result = result
        self.calls = []

    def classify(self, text):
        self.calls.append(text)
        return self.result


def make_classifier(gemma=None):
    return HalalClassifier(Rulebook.load_default(), gemma_client=gemma)


def test_always_halal():
    c = make_classifier()
    v = c.classify(["sugar"])
    assert v.verdict is Status.HALAL
    assert v.ingredients[0].confidence is Confidence.HIGH


def test_always_haram():
    c = make_classifier()
    v = c.classify(["lard"])
    assert v.verdict is Status.HARAM


def test_source_dependent_silent_is_shubhah():
    c = make_classifier()
    v = c.classify(["gelatin"])
    assert v.verdict is Status.SHUBHAH
    assert v.ingredients[0].source is Source.RULEBOOK
    assert v.ingredients[0].confidence is Confidence.HIGH


def test_source_dependent_halal_qualifier():
    c = make_classifier()
    v = c.classify(["gelatin (fish)"])
    assert v.ingredients[0].status is Status.HALAL


def test_source_dependent_haram_qualifier():
    c = make_classifier()
    v = c.classify(["pork gelatin"])
    assert v.ingredients[0].status is Status.HARAM


def test_worst_status_wins_haram_dominates():
    c = make_classifier()
    v = c.classify(["sugar", "gelatin", "lard"])
    assert v.verdict is Status.HARAM


def test_worst_status_wins_shubhah_over_halal():
    c = make_classifier()
    v = c.classify(["sugar", "gelatin"])
    assert v.verdict is Status.SHUBHAH


def test_unknown_uses_gemma():
    fake = FakeGemma(IngredientResult(
        input="frobnicate", canonical="frobnicate", status=Status.HARAM,
        source=Source.GEMMA, confidence=Confidence.LOW,
        reason="x", citation="Gemma",
    ))
    c = make_classifier(gemma=fake)
    v = c.classify(["frobnicate"])
    assert v.ingredients[0].source is Source.GEMMA
    assert fake.calls == ["frobnicate"]


def test_unknown_without_gemma_is_shubhah_unverified():
    c = make_classifier(gemma=FakeGemma(result=None))
    v = c.classify(["frobnicate"])
    assert v.ingredients[0].status is Status.SHUBHAH
    assert v.ingredients[0].confidence is Confidence.LOW
    assert "could not verify" in v.ingredients[0].reason.lower()


def test_empty_inputs_are_skipped():
    c = make_classifier()
    v = c.classify(["sugar", "", "   ", None])
    assert len(v.ingredients) == 1


def test_disclaimer_present():
    c = make_classifier()
    v = c.classify(["sugar"])
    assert "not a religious ruling" in v.disclaimer.lower()
