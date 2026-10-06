.PHONY: run test
run:
	./run.sh
test:
	.venv/bin/python -m pytest tests -q
