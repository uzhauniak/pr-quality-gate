"""Mutant discovery and application; the end-to-end run is exercised in CI."""

from quality.mutate import apply_mutant, changed_lines_from_diff, find_mutants

SOURCE = '''\
from decimal import Decimal

RATE = Decimal("0.03")


def discount(kwh):
    """Docstrings are never mutated: 100."""
    if kwh >= 100 and kwh < 500:
        return RATE * 2
    return 0


def body(x):
    return {
        "unit_rate": x,
        "currency": "GBP",
    }
'''


def kinds(lines):
    return [(m.line, m.kind, m.detail) for m in find_mutants("svc.py", SOURCE, lines)]


def test_parses_added_lines_of_source_files_only():
    diff = """\
diff --git a/services/pricing/src/pricing/engine.py b/services/pricing/src/pricing/engine.py
--- a/services/pricing/src/pricing/engine.py
+++ b/services/pricing/src/pricing/engine.py
@@ -67 +67 @@ def volume_discount(annual_kwh: Decimal) -> Decimal:
-        if annual_kwh >= threshold:
+        if annual_kwh > threshold:
@@ -80,0 +81,2 @@
+    a = 1
+    b = 2
diff --git a/services/pricing/tests/unit/test_engine.py b/services/pricing/tests/unit/test_engine.py
+++ b/services/pricing/tests/unit/test_engine.py
@@ -1 +1 @@
+import x
"""
    assert changed_lines_from_diff(diff) == {"services/pricing/src/pricing/engine.py": {67, 81, 82}}


def test_deleted_only_hunks_add_nothing():
    diff = "+++ b/services/a/src/a/x.py\n@@ -5,2 +4,0 @@\n"
    assert changed_lines_from_diff(diff) == {}


def test_finds_mutants_only_on_changed_lines():
    found = kinds({8, 9})
    assert (8, "compare", "`>=` → `>`") in found
    assert (8, "compare", "`<` → `<=`") in found
    assert (8, "boolean", "`and` → `or`") in found
    assert (8, "constant", "`100` → `101`") in found
    assert (9, "arithmetic", "`*` → `/`") in found
    assert all(line in {8, 9} for line, _, _ in found)


def test_decimal_literals_and_dict_keys_on_multiline_dicts():
    assert (3, "constant", '`Decimal("0.03")` → `Decimal("1.03")`') in kinds({3})
    assert kinds({15}) == [(15, "key", 'key `"unit_rate"` renamed')]


def test_docstrings_are_not_mutated():
    assert kinds({7}) == []


def test_applied_mutant_changes_exactly_one_thing():
    mutant = next(m for m in find_mutants("svc.py", SOURCE, {8}) if m.detail == "`>=` → `>`")
    mutated = apply_mutant(SOURCE, mutant)

    assert "if kwh > 100 and kwh < 500:" in mutated
    assert "RATE = Decimal('0.03')" in mutated  # rest untouched (unparse normalises quotes)


def test_key_mutant_renames_the_key():
    mutant = find_mutants("svc.py", SOURCE, {15})[0]
    assert "'unit_rate__mutant': x" in apply_mutant(SOURCE, mutant)
