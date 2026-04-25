# grabatus-service-core

Hexagonal core library for Grabatus computational services. Encapsulates the platform-to-service communication protocol so that new services (forecasting, optimization, Bayesian inference) only implement their own compute logic — every other concern (Pub/Sub, Storage I/O, JWT webhook, contract validation, observability, security) is inherited from this library.

## Status

v0.1.0 — work in progress.

## Documentation

Full Sphinx documentation lives in `docs/`. Build with `uv run sphinx-build -W docs/ docs/_build/html`.

## Development

```bash
uv sync --all-extras
uv run pre-commit install
uv run pytest
```

## License

Proprietary. © Grabatus.
