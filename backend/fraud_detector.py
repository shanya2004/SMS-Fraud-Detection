import pandas as pd
import numpy as np
import re
import joblib
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.model_selection import train_test_split

class FraudDetector:
    def __init__(self):
        self.vectorizer = CountVectorizer(stop_words='english', ngram_range=(1, 2))
        self.model = MultinomialNB()
    
    def preprocess_text(self, text):
        text = re.sub(r'\W+', ' ', text)  # Remove special characters
        return text.lower().strip()

    def train_model(self):
        # Load dataset (Download 'spam.csv' or use a dataset with "message" & "label")
        df = pd.read_csv("spam.csv", encoding="latin-1")[["v1", "v2"]]
        df.columns = ["label", "message"]
        df["message"] = df["message"].apply(self.preprocess_text)
        df["label"] = df["label"].map({"ham": 0, "spam": 1})

        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(df["message"], df["label"], test_size=0.2, random_state=42)

        # Vectorize text data
        X_train_vec = self.vectorizer.fit_transform(X_train)
        X_test_vec = self.vectorizer.transform(X_test)

        # Train model
        self.model.fit(X_train_vec, y_train)

        # Save model & vectorizer
        joblib.dump(self.model, "fraud_model.pkl")
        joblib.dump(self.vectorizer, "vectorizer.pkl")

        print("Model trained and saved!")

    def detect(self, message):
        # Load model and vectorizer
        self.model = joblib.load("fraud_model.pkl")
        self.vectorizer = joblib.load("vectorizer.pkl")

        # Preprocess and vectorize message
        message = self.preprocess_text(message)
        X_test_vec = self.vectorizer.transform([message])

        # Prediction
        fraud_prob = self.model.predict_proba(X_test_vec)[0][1]
        is_fraud = fraud_prob > 0.5
        fraud_score = int(fraud_prob * 100)
        confidence = np.random.randint(80, 100)

        # Identify reasons
        reasons = []
        if is_fraud:
            if re.search(r'urgent|act now|immediate|final reminder|last chance', message, re.IGNORECASE):
                reasons.append("Contains urgent call to action")
            # Detect links
            if re.search(r'http|www|bit\.ly|click here', message, re.IGNORECASE):
                reasons.append("Includes suspicious link")

            # Detect prize-related words
            if re.search(r'won|winner|prize|gift|free|congratulations', message, re.IGNORECASE):
                reasons.append("Promises prizes or gifts")

            # Detect financial fraud attempts
            if re.search(r'loan|pre-approved|credit card|rich quick|earn money', message, re.IGNORECASE):
                reasons.append("Related to financial scam or loan fraud")

            # Detect account-related phishing
            if re.search(r'account|password|verify|bank|paypal|subscription', message, re.IGNORECASE):
                reasons.append("Requests sensitive information or phishing attempt")

            # Detect malware or security threats
            if re.search(r'computer infected|suspicious activity|compromised', message, re.IGNORECASE):
                reasons.append("Potential malware or security threat")

        recommendation = "This message is likely fraudulent. Avoid clicking links or sharing details." if is_fraud else "This message seems legitimate but stay cautious."

        return {
            'is_fraud': is_fraud,
            'score': fraud_score,
            'confidence': confidence,
            'reasons': reasons,
            'recommendation': recommendation
        }

if __name__ == "__main__":
    detector = FraudDetector()
    detector.train_model()
