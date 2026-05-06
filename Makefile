.PHONY: demo clean

demo:
	python3 scripts/run_sample_pipeline.py

clean:
	rm -rf processed final
