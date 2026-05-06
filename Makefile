.PHONY: demo clean import-local run-local test

demo:
	python3 scripts/run_sample_pipeline.py

test:
	python3 -m unittest discover -s tests

import-local:
	python3 scripts/import_raw.py raw --out parsed

run-local:
	python3 scripts/run_pipeline.py raw

clean:
	rm -rf processed final parsed
