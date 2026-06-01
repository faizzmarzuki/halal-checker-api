from halal_scanner.models import (
    Status, Source, Confidence, IngredientResult, ScanVerdict,
)


def test_status_values():
    assert Status.HALAL.value == "halal"
    assert Status.HARAM.value == "haram"
    assert Status.SHUBHAH.value == "shubhah"


def test_ingredient_result_holds_fields():
    r = IngredientResult(
        input="Gelatin",
        canonical="gelatin",
        status=Status.SHUBHAH,
        source=Source.RULEBOOK,
        confidence=Confidence.HIGH,
        reason="source not disclosed",
        citation="JAKIM MS1500:2009",
    )
    assert r.status is Status.SHUBHAH
    assert r.source is Source.RULEBOOK


def test_scan_verdict_holds_list():
    v = ScanVerdict(
        verdict=Status.HALAL,
        ingredients=[],
        summary="ok",
        disclaimer="not a ruling",
    )
    assert v.verdict is Status.HALAL
    assert v.ingredients == []
