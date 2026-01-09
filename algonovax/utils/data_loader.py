import pandas as pd
from .logger import log
import os

def load_csv_data(path):
    path = os.path.expanduser(path)
    if os.path.exists(path):
        df = pd.read_csv(path)
        log(f"Loaded data from {path}")
    else:
        log(f"CSV missing: {path}. Using dummy data")
        df = pd.DataFrame({
            "close": [40000, 40100, 40250, 40300, 40450, 40500,
                      40400, 40300, 40200, 40100, 40050, 39950]
        })
    return df
