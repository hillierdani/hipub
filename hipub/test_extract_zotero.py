import pytest
from extract_zotero import (
    disambiguate_author_year_collisions,
    register_reference,
    _extract_leading_ref_number,
)

# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def registry_with_collision():
    """Two distinct papers that resolve to the same (display, year)."""
    return {
        "https://doi.org/paperA": {"display": "Smith et al.", "year": "2024", "title": "Paper A"},
        "https://doi.org/paperB": {"display": "Smith et al.", "year": "2024", "title": "Paper B"},
    }


@pytest.fixture
def registry_no_collision():
    """Distinct papers with different (display, year) pairs."""
    return {
        "https://doi.org/paperA": {"display": "Smith et al.", "year": "2024", "title": "Paper A"},
        "https://doi.org/paperB": {"display": "Jones et al.", "year": "2023", "title": "Paper B"},
    }


@pytest.fixture
def registry_three_way():
    """Three papers with identical (display, year) — e.g., all failed lookups."""
    return {
        f"https://doi.org/paper{i}": {"display": "Unknown", "year": "2026", "title": f"Paper {i}"}
        for i in range(3)
    }


# ── Collision disambiguation ──────────────────────────────────────────

class TestDisambiguateAuthorYear:
    def test_distinct_papers_same_author_year_get_suffixed(self, registry_with_collision):
        updated, collisions = disambiguate_author_year_collisions(registry_with_collision)

        marker_years = sorted(v["marker_year"] for v in updated.values())
        assert marker_years == ["2024a", "2024b"]
        # True bibliographic year must stay untouched.
        assert all(v["year"] == "2024" for v in updated.values())
        assert len(collisions) == 1

    def test_no_collision_marker_year_matches_year(self, registry_no_collision):
        updated, collisions = disambiguate_author_year_collisions(registry_no_collision)
        assert updated["https://doi.org/paperA"]["marker_year"] == "2024"
        assert updated["https://doi.org/paperB"]["marker_year"] == "2023"
        assert collisions == []

    def test_three_way_collision_gets_three_distinct_suffixes(self, registry_three_way):
        updated, collisions = disambiguate_author_year_collisions(registry_three_way)
        marker_years = sorted(v["marker_year"] for v in updated.values())
        assert marker_years == ["2026a", "2026b", "2026c"]


# ── Reference-number registration ─────────────────────────────────────

class TestRegisterReference:
    def test_duplicate_ref_num_does_not_overwrite_first_entry(self):
        ref_num_to_url, used, log = {}, set(), []
        register_reference(ref_num_to_url, used, "7", "https://example.com/first", log)
        register_reference(ref_num_to_url, used, "7", "https://example.com/second", log)

        assert ref_num_to_url["7"] == "https://example.com/first"
        assert "https://example.com/second" in ref_num_to_url.values()
        assert len(log) == 1

    def test_triple_collision_gets_unique_keys(self):
        ref_num_to_url, used, log = {}, set(), []
        register_reference(ref_num_to_url, used, "7", "https://example.com/a", log)
        register_reference(ref_num_to_url, used, "7", "https://example.com/b", log)
        register_reference(ref_num_to_url, used, "7", "https://example.com/c", log)

        assert len(ref_num_to_url) == 3
        assert len(set(ref_num_to_url.keys())) == 3  # all keys unique
        assert len(log) == 2

    def test_unique_ref_nums_pass_through_untouched(self):
        ref_num_to_url, used, log = {}, set(), []
        register_reference(ref_num_to_url, used, "1", "https://example.com/a", log)
        register_reference(ref_num_to_url, used, "2", "https://example.com/b", log)
        assert ref_num_to_url == {"1": "https://example.com/a", "2": "https://example.com/b"}
        assert log == []


# ── Leading reference number extraction ───────────────────────────────

class TestExtractLeadingRefNumber:
    def test_standard_numbered_citation(self):
        assert _extract_leading_ref_number("7. Smith J 2024") == "7"
        assert _extract_leading_ref_number("[7] Smith J 2024") == "7"
        assert _extract_leading_ref_number("7) Smith J 2024") == "7"

    def test_does_not_grab_embedded_year(self):
        assert _extract_leading_ref_number("Smith J 2024 Some Title") is None
        assert _extract_leading_ref_number("Some Title 2024 https://doi.org/10.1234/abc") is None

    def test_empty_or_no_number_returns_none(self):
        assert _extract_leading_ref_number("") is None
        assert _extract_leading_ref_number("no numbers here") is None
