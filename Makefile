.PHONY: demo clean import-local run-local test verify-web-mobile

demo:
	python3 scripts/run_sample_pipeline.py

test:
	python3 -m unittest discover -s tests

verify-web-mobile:
	python3 scripts/verify_annual_report_mobile.py

import-local:
	python3 scripts/import_raw.py raw --out parsed

run-local:
	python3 scripts/run_pipeline.py raw

clean:
	rm -rf processed final parsed
