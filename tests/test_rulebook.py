import pytest

from halal_scanner.rulebook import Rulebook, RuleEntry


@pytest.fixture
def book():
    return Rulebook.load_default()


def test_exact_lookup(book):
    e = book.lookup("sugar")
    assert isinstance(e, RuleEntry)
    assert e.nature == "always_halal"


def test_synonym_lookup(book):
    e = book.lookup("gelatine")
    assert e is not None
    assert e.key == "gelatin"


def test_enumber_synonym_lookup(book):
    e = book.lookup("e471")
    assert e is not None
    assert e.key == "diglycerides"


def test_word_subset_lookup(book):
    # "pork gelatin" should still find the gelatin entry.
    e = book.lookup("pork gelatin")
    assert e is not None
    assert e.key == "gelatin"


def test_unknown_returns_none(book):
    assert book.lookup("unobtanium") is None


def test_malformed_yaml_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: [a, valid, mapping\n", encoding="utf-8")
    with pytest.raises(ValueError):
        Rulebook.load_from(bad)


def test_ruleentry_minimal_construction():
    # reason and citation are optional; only key and nature are required.
    e = RuleEntry(key="x", nature="always_halal")
    assert e.reason == ""
    assert e.citation == ""
    assert e.synonyms == []
