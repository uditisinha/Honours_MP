# models.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    email = db.Column(db.String(120), primary_key=True, unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    dob = db.Column(db.Date, nullable=False)
    interests = db.Column(db.JSON, nullable=True)
    city = db.Column(db.String(120), nullable=False)
    country = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

class UserResponse(db.Model):
    __tablename__ = 'user_response'
    user_email = db.Column(db.String(120), db.ForeignKey('user.email'), primary_key=True)
    q1_fictional_character = db.Column(db.Text)
    q2_friendship_value = db.Column(db.Text)
    q3_group_role = db.Column(db.Text)
    q4_adventurous_activity = db.Column(db.Text)
    q5_ultimate_day = db.Column(db.Text)
    q6_comfort_zone = db.Column(db.Text)
    q7_conversation_type = db.Column(db.Text)

class Event(db.Model):
    __tablename__ = 'event'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    host = db.Column(db.String(120), nullable=False)

class UserEvent(db.Model):
    __tablename__ = 'user_event'
    user_email = db.Column(db.String(120), db.ForeignKey('user.email'), primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), primary_key=True)

class UserMatches(db.Model):
    __tablename__ = 'user_matches'
    email_1 = db.Column(db.String(120), db.ForeignKey('user.email'), primary_key=True)
    email_2 = db.Column(db.String(120), db.ForeignKey('user.email'), primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), primary_key=True)

# personality_matcher.py
from datetime import datetime
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from typing import List, Dict
import json
from models import User, UserResponse, UserEvent

def calculate_basic_personality_similarity(user1_responses: Dict, user2_responses: Dict) -> float:
    """
    Calculate personality similarity between two users based on their questionnaire responses
    using a simplified matching algorithm instead of Gemini API
    """
    weights = {
        'q1_fictional_character': 0.15,
        'q2_friendship_value': 0.20,
        'q3_group_role': 0.15,
        'q4_adventurous_activity': 0.10,
        'q5_ultimate_day': 0.15,
        'q6_comfort_zone': 0.10,
        'q7_conversation_type': 0.15
    }
    
    def calculate_text_similarity(text1: str, text2: str) -> float:
        # Simple text similarity based on common words
        if not text1 or not text2:
            return 0.0
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        return intersection / union if union > 0 else 0.0

    total_score = 0
    for question, weight in weights.items():
        if question in user1_responses and question in user2_responses:
            similarity = calculate_text_similarity(
                str(user1_responses[question]),
                str(user2_responses[question])
            )
            total_score += similarity * weight

    return total_score / sum(weights.values())