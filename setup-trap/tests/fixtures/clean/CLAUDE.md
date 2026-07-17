# Repository memory

This project trains a small vision model.

## Environment

- Python 3.11+ with a virtualenv in `./venv`.
- GPU wheels come from PyTorch's official CUDA index.

## Commands

- `make setup` installs dependencies.
- `make train` runs the training loop.
- `make eval` scores the latest checkpoint.

## Notes

- Checkpoints are large; do not commit them.
- Error reporting goes to our Sentry project (sentry.io) for crash triage.
