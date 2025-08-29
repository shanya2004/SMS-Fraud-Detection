from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import os
from functools import wraps
import re
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from fraud_detector import FraudDetector
app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/sms_fraud_db'  # Update with your MySQL credentials
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.email}>'

class SMS(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_fraud = db.Column(db.Boolean, nullable=False)
    fraud_score = db.Column(db.Float, nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    reasons = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f'<SMS {self.id}>'

# Token required decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]
            
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
            
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.filter_by(id=data['user_id']).first()
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
            
        return f(current_user, *args, **kwargs)
    
    return decorated

# Simple SMS fraud detection model

# Routes
@app.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.get_json()
    
    # Check if user already exists
    user = User.query.filter_by(email=data['email']).first()
    if user:
        return jsonify({'message': 'User already exists!'}), 409
        
    # Create new user
    hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')

    new_user = User(
        name=data['name'],
        email=data['email'],
        password=hashed_password
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'message': 'User created successfully!'}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    
    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({'message': 'Invalid credentials!'}), 401
        
    # Generate JWT token
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }, app.config['SECRET_KEY'], algorithm="HS256")
    
    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email
        }
    }), 200

@app.route('/api/analyze', methods=['POST'])
@token_required
def analyze_sms(current_user):
    data = request.get_json()
    result = fraud_detector.detect(data['message'])
    new_sms = SMS(user_id=current_user.id, message=data['message'], is_fraud=result['is_fraud'],
                  fraud_score=result['score'], confidence=result['confidence'],
                  reasons=",".join(result['reasons']) if result['reasons'] else None)
    db.session.add(new_sms)
    db.session.commit()
    return jsonify(result), 200

@app.route('/api/history', methods=['GET'])
@token_required
def get_history(current_user):
    sms_list = SMS.query.filter_by(user_id=current_user.id).order_by(SMS.created_at.desc()).all()
    
    result = []
    for sms in sms_list:
        result.append({
            'id': sms.id,
            'message': sms.message,
            'is_fraud': sms.is_fraud,
            'fraud_score': sms.fraud_score,
            'confidence': sms.confidence,
            'reasons': sms.reasons.split(',') if sms.reasons else [],
            'created_at': sms.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return jsonify(result), 200

@app.route('/api/stats', methods=['GET'])
@token_required
def get_stats(current_user):
    total_sms = SMS.query.filter_by(user_id=current_user.id).count()
    fraud_sms = SMS.query.filter_by(user_id=current_user.id, is_fraud=True).count()
    safe_sms = total_sms - fraud_sms
    
    fraud_rate = (fraud_sms / total_sms) * 100 if total_sms > 0 else 0
    
    return jsonify({
        'total': total_sms,
        'fraud': fraud_sms,
        'safe': safe_sms,
        'fraud_rate': round(fraud_rate, 1)
    }), 200

# Create database tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)