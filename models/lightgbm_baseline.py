import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
warnings.filterwarnings("ignore")

def create_features(values: np.ndarray, window_sizes=[5, 10, 20]) -> pd.DataFrame:
    """
    Zaman serisi veriden LightGBM icin ozellikler uretir.
    Lag features ve rolling statistics kullanir.
    """
    df = pd.DataFrame({"value": values})
    
    # Lag features
    for lag in [1, 2, 3, 5, 10]:
        df[f"lag_{lag}"] = df["value"].shift(lag)
    
    # Rolling statistics
    for window in window_sizes:
        df[f"rolling_mean_{window}"] = df["value"].rolling(window).mean()
        df[f"rolling_std_{window}"] = df["value"].rolling(window).std()
        df[f"rolling_max_{window}"] = df["value"].rolling(window).max()
        df[f"rolling_min_{window}"] = df["value"].rolling(window).min()
    
    # Trend feature
    df["diff_1"] = df["value"].diff(1)
    df["diff_2"] = df["value"].diff(2)
    
    return df.dropna()


class LightGBMForecaster:
    """
    LightGBM tabanli zaman serisi tahmin modeli.
    TimesFM ile karsilastirma icin baseline olarak kullanilir.
    """
    
    def __init__(self, horizon=5):
        self.horizon = horizon
        self.models = []
        self.is_trained = False
    
    def train(self, values: np.ndarray):
        """Modeli verilen zaman serisi uzerinde egitir."""
        print(f"LightGBM egitiliyor... ({len(values)} veri noktasi)")
        
        features_df = create_features(values)
        feature_cols = [c for c in features_df.columns if c != "value"]
        X = features_df[feature_cols].values
        y = features_df["value"].values
        
        self.models = []
        for h in range(1, self.horizon + 1):
            y_shifted = np.roll(y, -h)
            y_shifted = y_shifted[:-h]
            X_trimmed = X[:-h]
            
            model = lgb.LGBMRegressor(
                n_estimators=100,
                learning_rate=0.05,
                max_depth=6,
                num_leaves=31,
                verbose=-1
            )
            model.fit(X_trimmed, y_shifted)
            self.models.append(model)
        
        self.is_trained = True
        print(f"LightGBM egitimi tamamlandi! ({self.horizon} adim icin {len(self.models)} model)")
    
    def predict(self, values: np.ndarray) -> list:
        """Egitilmis model ile tahmin yapar."""
        if not self.is_trained:
            raise RuntimeError("Model egitilmedi. Once train() cagirin.")
        
        features_df = create_features(values)
        feature_cols = [c for c in features_df.columns if c != "value"]
        X_last = features_df[feature_cols].values[-1].reshape(1, -1)
        
        forecast = []
        for model in self.models:
            pred = model.predict(X_last)[0]
            forecast.append(float(pred))
        
        return forecast
    
    def evaluate(self, values: np.ndarray, test_ratio=0.2) -> dict:
        """Modeli test verisi uzerinde degerlendirir."""
        split = int(len(values) * (1 - test_ratio))
        train_data = values[:split]
        test_data = values[split:]
        
        self.train(train_data)
        
        predictions = []
        actuals = []
        
        for i in range(len(test_data) - self.horizon):
            context = np.concatenate([train_data, test_data[:i]])
            pred = self.predict(context)
            predictions.append(pred[0])
            actuals.append(test_data[i])
        
        mae = mean_absolute_error(actuals, predictions)
        rmse = np.sqrt(mean_squared_error(actuals, predictions))
        
        return {
            "mae": mae,
            "rmse": rmse,
            "predictions": predictions,
            "actuals": actuals
        }


if __name__ == "__main__":
    print("LightGBM Baseline Test")
    print("-" * 40)
    
    # Test verisi olustur - sinusoidal pattern
    t = np.linspace(0, 4 * np.pi, 200)
    test_values = (50 + 30 * np.sin(t) + np.random.normal(0, 2, 200)).astype(np.float32)
    
    forecaster = LightGBMForecaster(horizon=5)
    results = forecaster.evaluate(test_values)
    
    print(f"MAE:  {results['mae']:.4f}")
    print(f"RMSE: {results['rmse']:.4f}")
    
    # Tahmin ornegi
    forecast = forecaster.predict(test_values)
    print(f"Ornek tahmin (5 adim): {[round(f, 2) for f in forecast]}")
    print("Test basarili!")
