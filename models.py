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
    avatar = db.Column(db.String(256), nullable=True) 
    bio = db.Column(db.Text, nullable=True)  # Short biography or description

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
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True), nullable=False)
    host = db.Column(db.String(120), nullable=False)
    qr = db.Column(db.Text, nullable=True)
    
class UserEvent(db.Model):
    __tablename__ = 'user_event'
    user_email = db.Column(db.String(120), db.ForeignKey('user.email'), primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), primary_key=True)

class UserChats(db.Model):
    __tablename__ = 'UserChats'
    event_id = db.Column(db.Integer)
    chat_id = db.Column(db.Integer, primary_key=True)
    email_1 = db.Column(db.String(120), db.ForeignKey('user.email'))
    email_2 = db.Column(db.String(120), db.ForeignKey('user.email'))
    
class UserMessages(db.Model):
    __tablename__ = 'UserMessages'
    message_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('UserChats.chat_id'), nullable=False)
    sender = db.Column(db.String(120), db.ForeignKey('user.email'), nullable=False)
    recipient = db.Column(db.String(120), db.ForeignKey('user.email'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    time_sent = db.Column(db.DateTime, default=db.func.now(), nullable=False)