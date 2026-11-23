"""Recompute the protocol-fixed six-pair electoral response tensor."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from formation_tensor.election import run_experiment


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--quiet',action='store_true')
    args=parser.parse_args()
    result=run_experiment(ROOT,args.output,progress=None if args.quiet else lambda line:print(line,flush=True))
    print(json.dumps({k:result[k] for k in ('status','coordinates','unique_native_tables','valid_coordinates',
        'masked_coordinates','valid_interior_four_corners','mixed_seat_histogram','mixed_threshold_histogram')},ensure_ascii=False))


if __name__=='__main__':
    main()
