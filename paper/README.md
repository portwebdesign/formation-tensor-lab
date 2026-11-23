# Majorities Without Governments

Mehmet Yalçın and Osman Karslı

Exact electoral sensitivity, cabinet compatibility and sequential government formation in Sweden. The source cutoff is 22 November 2026.

## Article files

- `main.tex`: article, appendices and references.
- `supplement.tex`: separate rendering of the same appendices.
- `appendix-body.tex`: computational domains, proofs and exact agenda counts.
- `completion-appendix.tex`: sensitivity to alternative party-action rules.
- `programme-appendix.tex`: supplementary findings from four related studies.
- `references.bib`: academic and official-source bibliography.
- `claims.csv`: numerical claims and their evidence files.
- `figures/`: figures generated from the recorded results.

## Reproduce the calculations

From the repository root, with Python 3 and a Rust compiler supporting edition 2024:

```sh
python3 -B run.py verify
python3 -B run.py test
python3 -B run.py reproduce
```

`verify` checks file hashes. `reproduce` recomputes five experiments in a temporary directory and compares the results with the included JSON/CSV outputs. It leaves the recorded results unchanged. Integer and CSV comparisons are exact; floating-point comparisons use absolute tolerance `1e-10` or relative tolerance `1e-12`.

## Build the PDFs

Install the dependencies in `requirements-figures.txt` and Tectonic, then run from the repository root:

```sh
python3 -B run.py figures
python3 -B run.py paper
```

The PDFs are written to `paper/main.pdf` and `paper/supplement.pdf`. With the figures already present, direct compilation from `paper/` also works:

```sh
tectonic main.tex
tectonic supplement.tex
```

A first Tectonic run may need to download its TeX package bundle. The numerical source data are included in the repository.

## Scope

The exact transfer grid and finite-state bargaining results describe the stated inputs and action rules. Agenda counts are finite enumerations, not probabilities of future cabinets. The party-action rule sensitivity was specified after inspection of the baseline results. Historical replays are retrospective. Related CP/Tucker, SVD and calibration results retain their own evaluation designs and are supplied separately from the five reproduced experiments.
