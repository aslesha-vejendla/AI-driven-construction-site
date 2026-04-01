import numpy as np
import pickle, os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "elis_model.pkl")

class ELISClassifier:
    def __init__(self):
        self.vectorizer = None
        self.model      = None
        self.trained    = False

    def prepare_features(self, events: list) -> np.ndarray:
        from sklearn.feature_extraction.text import TfidfVectorizer
        messages = [e.get("message", "") for e in events]
        text_features = self.vectorizer.transform(messages).toarray()
        numeric_features = np.array([
            [
                float(e.get("worker_id", 0) or 0),
                float(e.get("hours_worked", 0) or 0),
                float(e.get("quantity_done", 0) or 0),
                1.0 if e.get("severity") == "CRITICAL" else 0.0,
            ]
            for e in events
        ])
        return np.hstack([text_features, numeric_features])

    def train(self, events: list, labels: list):
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.feature_extraction.text import TfidfVectorizer

        messages = [e.get("message", "") for e in events]
        self.vectorizer = TfidfVectorizer(max_features=100)
        self.vectorizer.fit(messages)

        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        X = self.prepare_features(events)
        self.model.fit(X, labels)
        self.trained = True
        self._save()
        print(f"[ELIS] Trained on {len(events)} events.")

    def classify(self, event: dict) -> dict:
        if not self.trained:
            return {
                "class": "UNCLASSIFIED", "confidence": 0.0,
                "normal_pct": 0.0, "suspicious_pct": 0.0, "critical_pct": 0.0
            }
        X = self.prepare_features([event])
        pred  = self.model.predict(X)[0]
        proba = self.model.predict_proba(X)[0]
        label_map = {0: "NORMAL", 1: "SUSPICIOUS", 2: "CRITICAL_BREACH"}
        return {
            "class":          label_map[pred],
            "confidence":     round(float(max(proba)) * 100, 1),
            "normal_pct":     round(float(proba[0]) * 100, 1),
            "suspicious_pct": round(float(proba[1]) * 100, 1),
            "critical_pct":   round(float(proba[2]) * 100, 1),
        }

    def _save(self):
        with open(MODEL_PATH, "wb") as f:
            pickle.dump({"vectorizer": self.vectorizer, "model": self.model}, f)

    def load(self):
        if os.path.exists(MODEL_PATH):
            with open(MODEL_PATH, "rb") as f:
                data = pickle.load(f)
                self.vectorizer = data["vectorizer"]
                self.model      = data["model"]
                self.trained    = True
            print("[ELIS] Model loaded from disk.")

# Singleton
elis_classifier = ELISClassifier()
elis_classifier.load()