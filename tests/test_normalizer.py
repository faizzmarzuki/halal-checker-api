from halal_scanner.normalizer import normalize


def test_lowercases_and_trims():
    assert normalize("  Gelatin  ") == "gelatin"


def test_collapses_internal_whitespace():
    assert normalize("soy   lecithin") == "soy lecithin"


def test_strips_punctuation_to_spaces():
    assert normalize("mono- & diglycerides") == "mono diglycerides"


def test_parentheses_become_spaces():
    assert normalize("gelatin (fish)") == "gelatin fish"


def test_enumber_with_space_is_joined():
    assert normalize("E 471") == "e471"


def test_enumber_in_parentheses():
    assert normalize("L-cysteine (E920)") == "l cysteine e920"


def test_already_clean_enumber():
    assert normalize("e471") == "e471"


def test_empty_and_non_string():
    assert normalize("   ") == ""
    assert normalize(None) == ""
