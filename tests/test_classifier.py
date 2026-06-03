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


def test_unreadable_ingredient_is_shubhah_not_skipped():
    # Non-Latin script with no translation normalizes to "" but is NOT blank;
    # it must surface as SHUBHAH (we couldn't read it), never be dropped.
    c = make_classifier()
    v = c.classify(["돼지고기", "설탕", "닭"])  # pork, sugar, chicken (Korean)
    assert len(v.ingredients) == 3
    assert all(r.status is Status.SHUBHAH for r in v.ingredients)
    assert all(r.source is Source.NONE for r in v.ingredients)
    assert all(r.confidence is Confidence.LOW for r in v.ingredients)


def test_all_unreadable_never_returns_halal():
    c = make_classifier()
    v = c.classify(["돼지고기", "설탕", "닭"])
    assert v.verdict is Status.SHUBHAH
    assert v.verdict is not Status.HALAL


def test_no_classifiable_ingredients_defaults_to_shubhah():
    # Empty / all-blank input must NOT confidently report HALAL.
    c = make_classifier()
    assert c.classify([]).verdict is Status.SHUBHAH
    assert c.classify(["", "   ", None]).verdict is Status.SHUBHAH


def test_disclaimer_present():
    c = make_classifier()
    v = c.classify(["sugar"])
    assert "not a religious ruling" in v.disclaimer.lower()
