#!/usr/bin/env python3
"""Command-line entry point for the complete research project."""
from pathlib import Path
from formation_tensor.project import main

if __name__ == '__main__':
    raise SystemExit(main(Path(__file__).resolve().parent))
