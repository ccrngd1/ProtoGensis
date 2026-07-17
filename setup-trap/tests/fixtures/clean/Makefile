.PHONY: setup train eval test

setup:
	pip install -r requirements.txt

train:
	python -m src.train --config configs/base.yaml

eval:
	python -m src.eval --checkpoint checkpoints/latest.pt

test:
	pytest -q
