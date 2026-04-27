"""Atheris-based fuzz harnesses for malformed-input safety.

Atheris is a coverage-guided fuzzer for Python. The harnesses in this
package wrap library entry points (Pub/Sub raw decoder, contract
validator) and feed them arbitrary bytes. The invariant is that the
target either succeeds or raises a typed library error — never an
unexpected exception that would crash a worker.

Atheris is Linux-only. On macOS and Windows the harnesses are still
importable (the atheris module is loaded lazily inside ``main``) but
cannot be executed. CI runs the harnesses for a fixed budget on
Linux runners; see ``.github/workflows/ci.yml``.
"""
