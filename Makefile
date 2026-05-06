.PHONY: demo clean import-local run-local

demo:
	python3 scripts/run_sample_pipeline.py

import-local:
	python3 scripts/import_raw.py raw --out parsed

run-local:
	python3 scripts/run_pipeline.py raw

clean:
	rm -rf processed final parsed
