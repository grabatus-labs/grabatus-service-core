"""Contract-compatibility tests.

Two complementary checks:

1. ``test_json_schema.py`` — pin the generated JSON Schema for the
   public contract via a snapshot. Any deviation fails the suite,
   forcing the author to either regenerate the snapshot deliberately
   (``scripts/update_schema_snapshots.py``) or revert the change.

2. ``test_fixtures.py`` — every JSON fixture under ``fixtures/v1.0/``
   either round-trips cleanly (``valid/``) or raises a ``ValidationError``
   (``invalid/``), with the offending field named.

Together they catch breaking contract changes during code review before
they reach a downstream service.
"""
