# Formation Tensor Lab

Code, data and manuscript for **Majorities Without Governments: Exact Response Tensors and Constrained Coalition Formation in Sweden**.

The study combines exact electoral calculations, parliamentary voting records and a finite-state model of government formation. Its results are conditional on the specified transfers and bargaining rules; they are not forecasts of the next government.

## Authors

| Author | Affiliation | Contact | ORCID |
|---|---|---|---|
| Mehmet Yalçın | Independent researcher, Sweden | Correspondence: [myalcin81@gmail.com](mailto:myalcin81@gmail.com) | [0009-0005-3021-8750](https://orcid.org/0009-0005-3021-8750) |
| Osman Karslı | Independent researcher | [theosmanuall@gmail.com](mailto:theosmanuall@gmail.com) | [0009-0003-9493-3417](https://orcid.org/0009-0003-9493-3417) |

## Read the paper

- [Article with appendices](paper/main.pdf) · [LaTeX source](paper/main.tex)
- [Appendices separately](paper/supplement.pdf) · [Evidence map](paper/claims.csv)

## Run locally

Install **Python 3.9+**, **Rust 1.85+** (edition 2024) and **Node.js 18+**. The numerical experiments use the Python and Rust standard libraries. Node.js checks the dashboard's JavaScript syntax.

Clone the repository, then run:

```sh
git clone https://github.com/portwebdesign/formation-tensor-lab.git
cd formation-tensor-lab
python3 -B run.py verify
python3 -B run.py test
python3 -B run.py reproduce
python3 -B run.py serve --port 7878
```

Open [http://127.0.0.1:7878/](http://127.0.0.1:7878/) to use the dashboard. Stop the server with `Ctrl+C`.

| Command | Purpose |
|---|---|
| `verify` | Check the recorded file checksums. |
| `test` | Run the Python and Rust tests and the JavaScript syntax check. |
| `reproduce` | Recompute five experiments in a temporary directory and compare their 30 JSON/CSV outputs with the recorded results. |
| `serve` | Start the local research dashboard. |

All inputs for these five experiments are included; no downloads or account credentials are needed. Reproduction preserves the working results. Integers and CSV files are compared exactly; floating-point values use absolute tolerance `1e-10` or relative tolerance `1e-12`.

## Build figures and PDFs

The PDFs and figures are included. To rebuild them, install [Tectonic](https://tectonic-typesetting.github.io/) and run:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-figures.txt
.venv/bin/python -B run.py figures
python3 -B run.py paper
```

The released figures were generated with Python 3.12. Tectonic may download its TeX bundle on the first build. Outputs are `paper/main.pdf` and `paper/supplement.pdf`.

To create a portable ZIP, including the dashboard's repository download:

```sh
python3 -B experiments/package_release.py
```

This also refreshes the release checksums after intentional changes to the source or documents.

## Files

| Directory | Contents |
|---|---|
| `formation_tensor/`, `native/` | Python analysis and exact Rust allocation engine |
| `data/` | Election tables, official parliamentary archives, dated formation sources and recorded earlier studies |
| `experiments/` | Numerical experiments, figures and packaging |
| `results/` | Recorded numerical outputs and verification logs |
| `paper/` | Manuscript, appendices, bibliography and figures |
| `web/` | Local dashboard |
| `tests/` | Arithmetic, model and data-integrity tests |

Earlier studies in `data/programme/` are recorded evidence with their own scope and provenance. They are separate from the five experiments rerun by `reproduce`.

Source attribution and access information accompany the data. No software licence has been granted; third-party materials retain their respective rights.
