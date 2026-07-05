"""Parser tests against the shareable ``ExporterEval`` fixture notebook.

``ExporterEval`` is a small, synthetic (dummy-content) OneNote notebook built to
exercise these parser fixes, so it can be committed as public test data:

  * ``DupTitles`` — distinct pages that share a title must all survive (no
    title-based collapse).
  * ``Hierarchy`` — page display order and subpage levels (1-3) come straight
    from the ``.one`` binary.
"""

from pathlib import Path

import pytest

from onenote_export.parser.one_store import OneStoreParser

EVAL = Path(__file__).parent / "test_data" / "ExporterEval"
_HAS_EVAL = EVAL.exists() and any(EVAL.glob("*.one"))

pytestmark = pytest.mark.skipif(
    not _HAS_EVAL, reason="ExporterEval fixture not available"
)


def _parse(name: str):
    return OneStoreParser(EVAL / name).parse()


class TestDupTitles:
    def test_all_same_titled_pages_retained(self):
        sec = _parse("DupTitles.one")
        titles = [p.title for p in sec.pages]
        assert len(sec.pages) == 4
        assert titles.count("Note") == 3  # three distinct pages titled "Note"
        assert "Unique" in titles


class TestHierarchy:
    EXPECTED = [
        ("Zeta", 1),
        ("Zeta-Sub-1", 2),
        ("Zeta-Sub-2", 2),
        ("Zeta-Sub-2a", 3),  # level-3 subpage
        ("Alpha", 1),
        ("Alpha-Sub-1", 2),
        ("Mike", 1),  # leaf; last despite "M" — order is display order, not alphabetical
    ]

    def test_order_and_levels(self):
        sec = _parse("Hierarchy.one")
        assert [(p.title, p.level) for p in sec.pages] == self.EXPECTED
