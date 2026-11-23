from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from formation_tensor.parliament import run_experiment
if __name__=='__main__':
    result=run_experiment(ROOT,progress=print)
    print(result['overall']['budget_profile'])
