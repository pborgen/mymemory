"""Entity extraction heuristics — no LLM required."""

from api.memory.entities import _heuristic_entities, normalize_key


def test_normalize_key():
    assert normalize_key("Helen") == "helen"
    assert normalize_key("Blue Bottle") == "blue-bottle"


def test_possessive_person():
    ents = _heuristic_entities("Helen's birthday is 12/12")
    keys = {e["key"] for e in ents}
    assert "helen" in keys
    helen = next(e for e in ents if e["key"] == "helen")
    assert helen["type"] == "person"


def test_proper_noun_extracted():
    ents = _heuristic_entities("My favorite coffee shop is Blue Bottle on Valencia")
    keys = {e["key"] for e in ents}
    assert "blue-bottle" in keys or "valencia" in keys
