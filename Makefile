.PHONY: verify reproduce test serve figures paper package
verify:
	python3 -B run.py verify
reproduce:
	python3 -B run.py reproduce
test:
	python3 -B run.py test
serve:
	python3 -B run.py serve --port 7878
figures:
	python3 -B run.py figures
paper:
	python3 -B run.py paper
package:
	python3 -B experiments/package_release.py
