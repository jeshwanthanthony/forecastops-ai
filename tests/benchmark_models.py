"""Local synthetic chronological comparison; not an EC2 capacity benchmark."""
import time
import tracemalloc

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from forecasting import _training_frame, recursive_forecast, seasonal_naive_forecast


def main():
    for days in (28, 90, 180, 365):
        for pattern in ("weekly", "trend", "noisy"):
            rng = np.random.default_rng(7)
            dates = pd.date_range("2025-01-01", periods=days)
            weekly = np.array([.8,.85,.9,1,1.2,1.4,1.1])[dates.dayofweek]
            trend = np.linspace(1, 1.4, days) if pattern == "trend" else 1
            noise = .3 if pattern == "noisy" else .06
            frame = pd.DataFrame({"date": dates, "sales": 1000 * weekly * trend * rng.normal(1, noise, days)})
            train, test = frame.iloc[:-7], frame.iloc[-7:]
            x, y = _training_frame(train)
            models = {"naive": None, "ridge": make_pipeline(StandardScaler(), Ridge(alpha=10)), "hist": HistGradientBoostingRegressor(max_iter=40, max_leaf_nodes=7, random_state=42), "forest": RandomForestRegressor(n_estimators=150, min_samples_leaf=2, random_state=42, n_jobs=1)}
            for name, model in models.items():
                tracemalloc.start(); start=time.perf_counter()
                if model is None:
                    fit=0; predicted=seasonal_naive_forecast(train,7).baseline_sales
                else:
                    model.fit(x,y); fit=time.perf_counter()-start
                    predicted=recursive_forecast(model,train,7).forecast_sales
                elapsed=time.perf_counter()-start; peak=tracemalloc.get_traced_memory()[1]/1048576; tracemalloc.stop()
                mae=mean_absolute_error(test.sales,predicted); total=test.sales.abs().sum()
                print(f"{days:3} {pattern:6} {name:6} MAE={mae:7.1f} WAPE={mae*7/total:.3f} fit={fit:.3f}s total={elapsed:.3f}s traced_MiB={peak:.2f}", flush=True)


if __name__ == "__main__":
    main()
