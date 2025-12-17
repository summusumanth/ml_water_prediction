import joblib
import numpy as np


class MaizeETCPredictor:
    def __init__(self):

        """Load trained ETo model."""

        self.lgbm_model = joblib.load("eto_lightgbm_model.pkl")
        print("model loaded successfully!")

    # ---------------------------------------------
    # Kc Calculation Based on DAS
    # ---------------------------------------------
    @staticmethod
    def get_maize_kc(das: float) -> float:
        """Return Kc for maize based on days after sowing (DAS)."""

        if das < 0:
            raise ValueError("DAS cannot be negative.")

        if 0 <= das < 25:
            kc_start, kc_end = 0.30, 0.40
            das_start, das_end = 0, 25
        elif 25 <= das < 55:
            kc_start, kc_end = 0.40, 0.80
            das_start, das_end = 25, 55
        elif 55 <= das < 95:
            kc_start, kc_end = 1.15, 1.20
            das_start, das_end = 55, 95
        elif 95 <= das <= 120:
            kc_start, kc_end = 0.70, 0.35
            das_start, das_end = 95, 120
        else:
            return 0.35  # after harvest

        # Linear interpolation
        kc = kc_start + (kc_end - kc_start) * ((das - das_start) / (das_end - das_start))
        return kc


    # ---------------------------------------------
    # Predict ETc (ETc = Kc × ETo)
    # ---------------------------------------------
    def predict_etc(self, weather_dict, das) -> dict:
        """
        Predict ETc using:
        - LightGBM ML ETo prediction
        - Maize Kc based on DAS
        """
        print("MODEL BOOSTER:", self.lgbm_model._Booster)

        # Convert weather dict to 2D numpy array
        input_data = np.array([list(weather_dict.values())])

        print("Input data for prediction:", input_data)

        # Predict ETo using LightGBM
        print(self.lgbm_model)
        # ensure numeric dtype
        try:
            input_arr = input_data.astype(np.float32)
        except Exception:
            input_arr = input_data

        try:
            eto_pred = self.lgbm_model.predict(input_arr)[0]
        except Exception as e:
            # Some lightgbm / sklearn version mismatches cause the
            # sklearn wrapper predict to fail (private validation helper
            # becomes None). Fall back to the underlying Booster.
            print("sklearn wrapper predict failed, falling back to Booster.predict:", e)
            try:
                eto_pred = float(self.lgbm_model._Booster.predict(input_arr)[0])
            except Exception as e2:
                print("Booster.predict also failed:", e2)
                raise

        # Compute Kc
        kc = self.get_maize_kc(das)

        # Compute ETc
        etc_value = eto_pred * kc

        return {
            "etc": float(etc_value)
        }


