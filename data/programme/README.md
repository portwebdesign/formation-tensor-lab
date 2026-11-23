# Recorded studies from the wider research programme

This directory preserves numerical evidence from four earlier `isvec-secim` studies: exact vote-cost certificates, longitudinal SVD and geometric stability, fitted response-tensor models, and historical polling calibration.

`recorded-evidence.json` gives the results, study scopes, original execution commands and SHA-256 inventories. `upstream/` contains 25 result, protocol and provenance files. Scientific results are retained; some metadata records omit development notes. `source_records` gives each original source hash, the hash of the included copy, and its byte-identity status.

These studies were not rerun when they were imported. They are outside the five experiments recomputed by `python3 -B run.py reproduce`. The current parliamentary experiment uses the same period independently; that does not reproduce the earlier SVD or fitted models.

Historical upstream manifests include references to code and inputs absent from this repository. They record provenance and do not define a standalone execution environment. Their original hashes describe the original files; the local `files` map in `recorded-evidence.json` verifies the included copies.

The original execution commands require an intact copy of `isvec-secim`. Several regenerate evidence in place, so preserve the original results and use a separate copy for replication.
