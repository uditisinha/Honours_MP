from flask import Flask, render_template, url_for, request, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import supabase
from flask import jsonify
import random
import qrcode
from io import BytesIO
from flask import send_file
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import OneHotEncoder
from datetime import datetime
from models import db, User, UserResponse, Event, UserEvent, UserChats, UserMessages
from sqlalchemy.exc import IntegrityError
import os
from werkzeug.utils import secure_filename
import base64
import google.generativeai as genai
import numpy as np
from typing import List, Dict
import json
import re

GOOGLE_API_KEY='AIzaSyDmKGlt0wQREPzT8vI9WpzB5A37NuvLHlc'
# GOOGLE_API_KEY='AIzaSyDwsOjC6diV88sDez5BuUeCYheVS0aa5UI'
# GOOGLE_API_KEY='AIzaSyBJXh--ktIhO3u6d_I51aTjo8brP6VwloU'

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres.jgmvvjlfnqimbwoqqfam:poonambhogle@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
app.secret_key = "SecretestKey"

app.config['UPLOAD_FOLDER'] = 'static/images/avatars'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db.init_app(app)

supabase_url = "https://jgmvvjlfnqimbwoqqfam.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpnbXZ2amxmbnFpbWJ3b3FxZmFtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzUyOTczMTEsImV4cCI6MjA1MDg3MzMxMX0.jED2-HuAoiAdY_BSqFAr2YIaHjF9eSIzdppmSCy1x7Y"  # Ensure this key is correct
supabase_client = supabase.create_client(supabase_url, supabase_key)

# with app.app_context():
#     db.drop_all() 
#     db.create_all()
  
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/profile/')
def profile():
    if 'user' not in session:
        flash("Please log in to view your profile.", 'warning')
        return redirect(url_for('login'))
    
    user_email = session['user']
    user = User.query.filter_by(email=user_email).first() 
    
    if user:
        return render_template('profile.html', user=user)
    else:
        flash("User not found.", 'danger')
        return redirect(url_for('login'))

@app.route('/search/', methods=['GET', 'POST'])
def search():
    search_results = []
    if request.method == 'POST':
        query = request.form.get('query')
        search_results = ["Example Match 1", "Example Match 2"] 
    return render_template('search.html', results=search_results)

def get_user_chats(user_email):
    """
    Fetch all chats where the requesting user is involved either as email_1 or email_2
    """
    chats = UserChats.query.filter(
        db.or_(
            UserChats.email_1 == user_email,
            UserChats.email_2 == user_email
        )
    ).join(
        Event,
        Event.id == UserChats.event_id
    ).add_columns(
        UserChats.chat_id,
        UserChats.email_1,
        UserChats.email_2,
        Event.name.label('event_name'),
        Event.code.label('event_code')
    ).all()
    
    return chats

@app.route('/chats')
def chat_list():
    if 'user' not in session:
        flash("Please log in to view your profile.", 'warning')
        return redirect(url_for('login'))

    # Get user email from session
    user_email = session['user']

    # Redirect if not logged in
    if not user_email:
        return redirect(url_for('login'))

    # Fetch user's name and avatar
    user = User.query.filter_by(email=user_email).first()
    if not user:
        flash("User not found.", 'danger')
        return redirect(url_for('login'))

    user_name = user.name
    user_avatar = user.avatar

    # Fetch chats and additional user info
    chats = UserChats.query.filter((UserChats.email_1 == user_email) | (UserChats.email_2 == user_email)).all()

    # Fetch other user details for each chat
    chat_details = []
    for chat in chats:
        other_email = chat.email_2 if user_email == chat.email_1 else chat.email_1
        other_user = User.query.filter_by(email=other_email).first()
        chat_details.append({
            'chat_id': chat.chat_id,
            'other_user': {
                'name': other_user.name if other_user else 'Unknown User',
                'avatar': other_user.avatar if other_user and other_user.avatar else '../static/images/user.png',
            }
        })

    # Pass user details and chats to the template
    return render_template(
        'chat_list.html',
        chats=chat_details,
        user_email=user_email,
        user_name=user_name,
        user_avatar=user_avatar
    )


@app.route('/signup/', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            gender = request.form.get('gender')
            dob = request.form.get('dob')
            interests = request.form.getlist('interests[]')
            city = request.form.get('city')
            country = request.form.get('country')
            password = request.form.get('password')
            email = request.form.get('email')

            # Validate required fields
            if not all([name, gender, dob, city, country, password, email]):
                flash("All fields except Interests are required.", 'danger')
                return redirect(url_for('signup'))

            # Check if the date format is valid
            try:
                dob_parsed = datetime.strptime(dob, '%Y-%m-%d').date()
            except ValueError:
                flash("Invalid date format. Please use YYYY-MM-DD.", 'danger')
                return redirect(url_for('signup'))

            # Check if email already exists
            if User.query.filter_by(email=email).first():
                flash("Email already exists. Please log in.", 'danger')
                return redirect(url_for('login'))

            hashed_password = generate_password_hash(password)

            new_user = User(
                name=name,
                gender=gender,
                dob=dob_parsed,
                interests=interests,  # Store as list directly
                city=city,
                country=country,
                password_hash=hashed_password,
                email=email
            )

            db.session.add(new_user)
            db.session.commit()

            flash("Account created successfully! Please log in.", 'success')
            return redirect(url_for('login'))

        except Exception as e:
            db.session.rollback()
            print(f"Error during signup: {str(e)}")
            flash(f"Sign-up failed. Please try again.", 'danger')
            return redirect(url_for('signup'))

    return render_template('signup.html')

@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password. Please try again.", 'danger')
            return redirect(url_for('login'))
        
        session['user'] = user.email
        flash("Login successful!", 'success')
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/logout/')
def logout():
    session.pop('user', None)
    flash("You have been logged out.", 'info')
    return redirect(url_for('login'))

@app.route('/join-event/<int:event_id>', methods=['GET', 'POST'])
def join_event_from_list(event_id):
    if 'user' not in session:
        flash("Please log in to join events.", "warning")
        return redirect(url_for('login'))
    
    try:
        # Get the event
        event = Event.query.get(event_id)
        if not event:
            flash("Event not found.", "error")
            return redirect(url_for('public_events'))
        
        if request.method == 'POST':
            event_code = request.form.get('event_code')
            
            # Verify the event code
            if event_code != event.code:
                flash("Invalid event code. Please try again.", "error")
                return render_template('join_event_from_list.html', event=event)
            
            user_email = session['user']
            
            # Check if user is already registered for this event
            existing_registration = UserEvent.query.filter_by(
                user_email=user_email,
                event_id=event_id
            ).first()
            
            if existing_registration:
                flash("You are already registered for this event.", "info")
                return redirect(url_for('public_events'))
            
            # Register the user for the event
            new_registration = UserEvent(
                user_email=user_email,
                event_id=event_id
            )
            
            db.session.add(new_registration)
            db.session.commit()
            
            flash("Successfully joined the event!", "success")
            return redirect(url_for('public_events'))
            
        return render_template('join_event_from_list.html', event=event)
        
    except Exception as e:
        app.logger.error(f"Error in join_event: {str(e)}")
        flash("An error occurred while joining the event.", "error")
        return redirect(url_for('public_events'))

@app.route('/events/public')
def public_events():
    if 'user' not in session:
        flash("Please log in to access events.", 'warning')
        return redirect(url_for('login'))
    
    try:
        current_time = datetime.now()
        user_email = session['user']
        
        # Get user's city
        user = User.query.filter_by(email=user_email).first()
        if not user:
            flash("User not found.", "error")
            return redirect(url_for('home'))

        # Check if user is hosting any active events
        hosted_event = Event.query.filter_by(
            host=user_email
        ).filter(Event.end_time > current_time).first()
        
        # Check if user is participating in any events
        participating_event = None
        if not hosted_event:
            participating_event = db.session.query(Event).join(UserEvent).filter(
                UserEvent.user_email == user_email,
                Event.end_time > current_time
            ).first()
        
        # Get all public events in user's city
        events = Event.query.filter(
            Event.city == user.city,
            Event.is_private == False,
            Event.end_time > current_time
        ).order_by(Event.start_time.asc()).all()

        events_data = []
        for event in events:
            # Get host information
            host = User.query.filter_by(email=event.host).first()
            host_name = host.name if host else "Unknown"

            # Get participant count
            participant_count = UserEvent.query.filter_by(event_id=event.id).count()

            events_data.append({
                "event": event,
                "host_name": host_name,
                "participant_count": participant_count
            })

        return render_template(
            'public_events.html',
            events_data=events_data,
            city=user.city,
            current_time=current_time,
            hosted_event=hosted_event,
            participating_event=participating_event
        )

    except Exception as e:
        app.logger.error(f"Error in public_events: {str(e)}")
        flash("An error occurred while loading events.", "error")
        return redirect(url_for('home'))

# Route file
@app.route('/event/')
def eventPage():
    if 'user' not in session:
        flash("Please log in to access events.", 'warning')
        return redirect(url_for('login'))
    
    current_time = datetime.now()
    user_email = session['user']
    
    # Initialize variables
    active_event = None
    is_host = False
    host_name = None
    has_active_event = False
    
    try:
        # Check if user is hosting any active events
        hosted_event = Event.query.filter_by(
            host=user_email
        ).filter(Event.end_time > current_time).first()
        
        if hosted_event:
            active_event = hosted_event
            is_host = True
            host_user = User.query.filter_by(email=hosted_event.host).first()
            host_name = host_user.name if host_user else "Unknown"
        else:
            # Check if user is participating in any active events
            participating_event = db.session.query(Event).join(UserEvent).filter(
                UserEvent.user_email == user_email,
                Event.end_time > current_time
            ).first()
            if participating_event:
                active_event = participating_event
                host_user = User.query.filter_by(email=participating_event.host).first()
                host_name = host_user.name if host_user else "Unknown"
        
        has_active_event = active_event is not None
        active_event_name = active_event.name if active_event else None

        return render_template('event.html',
                            has_active_event=has_active_event,
                            active_event=active_event,
                            active_event_name=active_event_name,
                            host_name=host_name,
                            is_host=is_host)
                            
    except Exception as e:
        app.logger.error(f"Error in eventPage: {str(e)}")
        flash(f"An error occurred while loading the event page. {str(e)}", 'danger')
        return redirect(url_for('home'))

@app.route('/leave_event', methods=['POST'])
def leave_event():
    if 'user' not in session:
        flash("Please log in to leave an event.", 'warning')
        return redirect(url_for('login'))
    
    user_email = session['user']
    event_id = request.form.get('event_id')
    
    if not event_id:
        flash("Invalid request.", 'danger')
        return redirect(url_for('public_events'))
    
    try:
        # Check if user is a host
        event = Event.query.filter_by(id=event_id).first()
        if event and event.host == user_email:
            flash("Event hosts cannot leave their own event.", 'danger')
            return redirect(url_for('public_events'))
        
        # Delete the user's event association
        user_event = UserEvent.query.filter_by(
            user_email=user_email,
            event_id=event_id
        ).first()
        
        if user_event:
            db.session.delete(user_event)
            db.session.commit()
            flash("You have successfully left the event.", 'success')
        else:
            flash("You are not part of this event.", 'warning')
            
    except Exception as e:
        db.session.rollback()
        flash(f"Error leaving event: {str(e)}", 'danger')
    
    return redirect(url_for('public_events'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/edit_profile/', methods=['GET', 'POST'])
def edit_profile():
    if 'user' not in session:
        flash("Please log in to edit your profile.", 'warning')
        return redirect(url_for('login'))

    user_email = session['user']
    user = User.query.filter_by(email=user_email).first()
    
    if request.method == 'POST':
        # Handle avatar upload
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename != '' and allowed_file(file.filename):
                # Create upload directory if it doesn't exist
                if not os.path.exists(app.config['UPLOAD_FOLDER']):
                    os.makedirs(app.config['UPLOAD_FOLDER'])
                
                # Save the file with a secure filename
                filename = secure_filename(f"{user.email}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Remove old avatar file if it exists
                if user.avatar and os.path.exists(user.avatar[1:]):  # Remove leading slash
                    try:
                        os.remove(user.avatar[1:])
                    except Exception as e:
                        print(f"Error removing old avatar: {e}")
                
                # Save new avatar
                file.save(filepath)
                user.avatar = '/' + filepath  # Store path in database with leading slash

        # Get all the new values from the form
        new_email = request.form['email']
        new_name = request.form['name']
        new_bio = request.form['bio']  # Add this line
        new_gender = request.form['gender']
        new_dob = request.form['dob']
        new_interests = request.form.getlist('interests[]')
        new_city = request.form['city']
        new_country = request.form['country']

        try:
            # Update all user fields including bio
            user.email = new_email
            user.name = new_name
            user.bio = new_bio  # Add this line
            user.gender = new_gender
            user.dob = new_dob
            user.interests = new_interests
            user.city = new_city
            user.country = new_country

            db.session.commit()
            session['user'] = new_email
            flash("Profile updated successfully!", 'success')
            return redirect(url_for('profile'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating profile: {e}", 'danger')
            return redirect(url_for('edit_profile'))

    return render_template('edit_profile.html', user=user)

def check_user_active_events(user_email):
    """
    Check if user has any active events and clean up expired events.
    Returns tuple (is_active, active_event_name) where is_active is True if user 
    has an active event (including as host), and active_event_name is the name of that event.
    """
    current_time = datetime.now()
    
    # Check events where user is a participant
    user_events = db.session.query(Event, UserEvent).join(UserEvent).filter(
        UserEvent.user_email == user_email
    ).all()
    
    # Check events where user is a host
    hosted_events = Event.query.filter_by(host=user_email).all()
    
    # Clean up expired events and check for active ones
    expired_user_events = []
    expired_hosted_events = []
    active_event = None
    
    # Check participant events
    for event, user_event in user_events:
        if event.end_time > current_time:
            active_event = event
        else:
            expired_user_events.append(user_event)
    
    # Check hosted events
    for event in hosted_events:
        if event.end_time > current_time:
            active_event = event
        else:
            expired_hosted_events.append(event)
    flash(expired_hosted_events)
    try:
        # Delete expired event associations for participants
        if expired_user_events:
            for user_event in expired_user_events:
                db.session.delete(user_event)
        
        # Delete expired events hosted by the user
        if expired_hosted_events:
            for event in expired_hosted_events:
                # First delete all associated user_event entries
                UserEvent.query.filter_by(event_id=event.id).delete()
                # Then delete the event itself
                db.session.delete(event)
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error cleaning up expired events: {str(e)}")
    
    return (active_event is not None, active_event.name if active_event else None)

@app.route('/host/', methods=['GET', 'POST'])
def host_event():
    if 'user' not in session:
        flash("Please log in to host an event.", 'warning')
        return redirect(url_for('login'))

    # Check if user has active events
    has_active_event, active_event_name = check_user_active_events(session['user'])
    if has_active_event:
        flash(f"You are already part of an active event: {active_event_name}. "
              "Please wait until it ends before hosting another event.", 'warning')
        return redirect(url_for('home'))

    if request.method == 'POST':
        try:
            # Retrieve form data
            name = request.form.get('name')
            start_time_str = request.form.get('start_time')
            end_time_str = request.form.get('end_time')
            address = request.form.get('address')
            city = request.form.get('city')
            is_private = request.form.get('is_private') == 'true'  # Convert to boolean
            description = request.form.get('description')

            # Validate required fields
            if not all([name, start_time_str, end_time_str, address, city]):
                flash("All fields are required.", 'danger')
                return redirect(url_for('host_event'))

            # Parse datetime strings
            start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')

            # Validate end time is after start time
            if end_time <= start_time:
                flash("End time must be after start time.", 'danger')
                return redirect(url_for('host_event'))

            # Generate unique 4-digit code
            while True:
                code = f"{random.randint(1000, 9999)}"
                if not Event.query.filter_by(code=code).first():
                    break

            # Create QR code directory if it doesn't exist
            qr_dir = os.path.join(app.static_folder, 'qr_codes')
            os.makedirs(qr_dir, exist_ok=True)

            # Generate and save QR code
            qr = qrcode.make(code)
            img_byte_arr = BytesIO()
            qr.save(img_byte_arr, format='PNG')
            img_str = base64.b64encode(img_byte_arr.getvalue()).decode()

            # Create new event with all fields
            event = Event(
                name=name,
                code=code,
                start_time=start_time,
                end_time=end_time,
                address=address,
                city=city,
                is_private=is_private,
                description=description,
                host=session['user'],
                qr=img_str
            )

            db.session.add(event)
            db.session.commit()

            flash(f"Event '{name}' created successfully! Code: {code}", 'success')
            return redirect(url_for('public_events'))  # Redirect to event page

        except ValueError as e:
            flash("Invalid date/time format. Please use the datetime picker.", 'danger')
            return redirect(url_for('host_event'))
        except Exception as e:
            db.session.rollback()
            print(f"Error creating event: {str(e)}")
            flash("Failed to create event. Please try again.", 'danger')
            return redirect(url_for('host_event'))

    return render_template('host_event.html')


def get_user_active_event(user_email):
    """
    Get user's active event details.
    Returns (event_id, is_expired) tuple. Returns (None, False) if no event found.
    """
    current_time = datetime.now()
    
    # Check events where user is a participant
    user_event = db.session.query(Event, UserEvent).join(UserEvent).filter(
        UserEvent.user_email == user_email
    ).first()
    
    # Check events where user is a host
    hosted_event = Event.query.filter_by(host=user_email).first()
    
    active_event = None
    is_expired = False
    
    # Check participant event
    if user_event:
        event, _ = user_event
        if event.end_time <= current_time:
            is_expired = True
        else:
            active_event = event
            
    # Check hosted event
    if hosted_event:
        if hosted_event.end_time <= current_time:
            is_expired = True
        elif not active_event:  # Only use hosted event if no participant event found
            active_event = hosted_event
            
    return (active_event.id if active_event else None, is_expired)

@app.route('/join/', methods=['GET', 'POST'])
def join_event():
    if 'user' not in session:
        flash("Please log in to join an event.", 'warning')
        return redirect(url_for('login'))

    # Check if user has active events
    has_active_event, active_event_name = check_user_active_events(session['user'])
    if has_active_event:
        flash(f"You are already part of an active event: {active_event_name}. "
              "Please wait until it ends before joining another event.", 'warning')
        return redirect(url_for('home'))

    event_users = []
    if request.method == 'POST':
        code = request.form.get('code')
        event = Event.query.filter_by(code=code).first()

        if event:
            # Check if the event has already ended
            if event.end_time <= datetime.now():
                flash("This event has already ended.", 'warning')
                return redirect(url_for('join_event'))

            # Add the logged-in user to the event
            user_event = UserEvent(user_email=session['user'], event_id=event.id)
            try:
                db.session.add(user_event)
                db.session.commit()
                flash("Successfully joined the event!", 'success')
            except Exception as e:
                db.session.rollback()
                flash(f"Failed to join the event: {str(e)}", 'danger')

            # Fetch all users in the event
            event_users = User.query.join(UserEvent, User.email == UserEvent.user_email)\
                                    .filter(UserEvent.event_id == event.id).all()
        else:
            flash("Invalid event code. Please try again.", 'danger')

    return render_template('join_event.html', event_users=event_users)

@app.route('/questionnaire/', methods=['GET', 'POST'])
def questionnaire():
    if 'user' not in session:
        flash("Please log in to complete the questionnaire.", 'warning')
        return redirect(url_for('login'))
    
    user_email = session['user']
    existing_response = UserResponse.query.filter_by(user_email=user_email).first()
    
    if request.method == 'POST':
        try:
            # Get responses from form
            responses = {
                'q1_fictional_character': request.form.get('q1_fictional_character'),
                'q2_friendship_value': request.form.get('q2_friendship_value'),
                'q3_group_role': request.form.get('q3_group_role'),
                'q4_adventurous_activity': request.form.get('q4_adventurous_activity'),
                'q5_ultimate_day': request.form.get('q5_ultimate_day'),
                'q6_comfort_zone': request.form.get('q6_comfort_zone'),
                'q7_conversation_type': request.form.get('q7_conversation_type')
            }
            
            # Check if all questions are answered
            if not all(responses.values()):
                flash("Please answer all questions.", 'warning')
                return redirect(url_for('questionnaire'))
            
            if existing_response:
                # Update existing response
                for key, value in responses.items():
                    setattr(existing_response, key, value)
            else:
                # Create new response
                new_response = UserResponse(user_email=user_email, **responses)
                db.session.add(new_response)
            
            db.session.commit()
            flash("Thank you for completing the questionnaire!", 'success')
            return redirect(url_for('profile'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error saving responses: {str(e)}", 'danger')
            return redirect(url_for('questionnaire'))
    
    return render_template('questionnaire.html', existing_response=existing_response)

@app.route('/api/messages/<int:chat_id>', methods=['GET'])
def get_messages(chat_id):
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    # Get the chat details to verify the user is part of this chat
    chat = UserChats.query.filter_by(chat_id=chat_id).first()
    if not chat or (session['user'] not in [chat.email_1, chat.email_2]):
        return jsonify({'error': 'Unauthorized access'}), 403
        
    # Get all messages for this chat
    messages = UserMessages.query.filter_by(chat_id=chat_id)\
        .order_by(UserMessages.time_sent).all()
        
    messages_list = []
    for msg in messages:
        messages_list.append({
            'id': msg.message_id,
            'sender': msg.sender,
            'body': msg.body,
            'time': msg.time_sent.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    return jsonify(messages_list)

@app.route('/api/messages/<int:chat_id>/send', methods=['POST'])
def send_message(chat_id):
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    try:
        data = request.get_json()
        print("Received data:", data)
        
        if not data or 'message' not in data:
            return jsonify({'error': 'No message provided'}), 400
            
        chat = UserChats.query.filter_by(chat_id=chat_id).first()
        print("Found chat:", chat)
        
        sender = session['user']
        recipient = chat.email_2 if sender == chat.email_1 else chat.email_1
        current_time = datetime.now()
        
        print(f"Creating message: chat_id={chat_id}, sender={sender}, recipient={recipient}")
        
        new_message = UserMessages(
            chat_id=chat_id,
            sender=sender,
            recipient=recipient,
            body=data['message'],
            time_sent=current_time
        )
        
        db.session.add(new_message)
        db.session.commit()
        
        response_data = {
            'sender': sender,
            'body': data['message'],
            'time': current_time.strftime('%Y-%m-%d %H:%M:%S')
        }
        print("Sending response:", response_data)
        
        return jsonify(response_data)
        
    except Exception as e:
        db.session.rollback()
        print(f"Exception in send_message: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/chat/<int:chat_id>')
def chat_page(chat_id):
    # Get the chat details
    chat = UserChats.query.get(chat_id)
    
    if not chat:
        return "Chat not found", 404
    
    # Determine the other user's email
    user_email = session["user"]  # Assuming user's email is stored in session
    other_email = chat.email_1 if chat.email_2 == user_email else chat.email_2
    
    # Get the other user's details
    other_user = User.query.filter_by(email=other_email).first()
    
    if not other_user:
        return "User not found", 404
    
    return render_template('chat.html', other_user=other_user)


@app.route('/create_chat/<int:event_id>/<string:matched_email>', methods=['POST'])
def create_chat(event_id, matched_email):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user_email = session['user']
    
    try:
        # Verify both users are part of the event
        user1_in_event = UserEvent.query.filter_by(
            user_email=user_email,
            event_id=event_id
        ).first()
        user2_in_event = UserEvent.query.filter_by(
            user_email=matched_email,
            event_id=event_id
        ).first()
        print(user1_in_event)
        user1_in_event = UserEvent.query.filter_by(user_email=user_email, event_id=event_id).first()
        user2_in_event = UserEvent.query.filter_by(user_email=matched_email, event_id=event_id).first()

        app.logger.info(f"User 1: {user1_in_event}, User 2: {user2_in_event}")

        if not (user1_in_event and user2_in_event):
            return jsonify({'error': 'Invalid users for this event'}), 400
            
        # Check if chat already exists
        existing_chat = UserChats.query.filter(
            UserChats.event_id == event_id,
            ((UserChats.email_1 == user_email) & (UserChats.email_2 == matched_email)) |
            ((UserChats.email_1 == matched_email) & (UserChats.email_2 == user_email))
        ).first()
        
        if existing_chat:
            return jsonify({'chat_id': existing_chat.chat_id}), 200
            
        # Fix the chat_id generation
        max_chat_id = db.session.query(db.func.max(UserChats.chat_id)).scalar()
        new_chat_id = (max_chat_id or 0) + 1  # Properly handle the None case
        
        # Create new chat
        new_chat = UserChats(
            event_id=event_id,
            email_1=user_email,
            email_2=matched_email,
            chat_id=new_chat_id
        )
        db.session.add(new_chat)
        db.session.commit()
        
        return jsonify({'chat_id': new_chat.chat_id}), 201
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Failed to create chat'}), 500
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error creating chat: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.context_processor
def utility_processor():
    def get_active_event_id():
        if 'user' in session:
            event_id, is_expired = get_user_active_event(session['user'])
            return event_id
        return None
    return dict(get_active_event_id=get_active_event_id)

def calculate_personality_similarity(user1_responses: Dict, user2_responses: Dict) -> tuple[float, str]:
    """
    Calculate personality similarity between two users and provide explanation
    Returns a tuple of (similarity_score, explanation)
    """
    genai.configure(api_key=GOOGLE_API_KEY)
    
    generation_config = {
        "temperature": 0,
        "top_p": 0.8,
        "top_k": 50,
        "max_output_tokens": 8192,
    }
    
    try:
        model = genai.GenerativeModel(
            model_name="gemini-pro",
            generation_config=generation_config
        )
        print("API configured successfully!")
    except Exception as e:
        print(f"Error: {e}")
    
    def clean_responses(responses: Dict) -> Dict:
        return {
            k: v for k, v in responses.items() 
            if k.startswith('q') and not k.startswith('_')
        }
    
    user1_clean = clean_responses(user1_responses)
    user2_clean = clean_responses(user2_responses)
    
    weights = {
        'q1_fictional_character': 0.15,
        'q2_friendship_value': 0.20,
        'q3_group_role': 0.15,
        'q4_adventurous_activity': 0.10,
        'q5_ultimate_day': 0.15,
        'q6_comfort_zone': 0.10,
        'q7_conversation_type': 0.15
    }
    
    try:
        prompt = f"""
        Compare these two sets of responses and analyze their compatibility:

        User 1:
        {json.dumps(user1_clean, indent=2)}

        User 2: 
        {json.dumps(user2_clean, indent=2)}

        Analyze the semantic similarity of responses considering:
        1. Direct matches in word choice/meaning
        2. Thematic alignment
        3. Compatible personality traits
        4. Similar values and preferences
        5. Complementary characteristics

        Return a JSON object with:
        1. Numeric scores for each question (0-1)
        2. A brief, personalized explanation (1 line) addressing both users directly about why they would or wouldn't be a good match

        Format:
        {{
            "scores": {{
                "q1_fictional_character": 0.85,
                "q2_friendship_value": 0.72,
                "q3_group_role": 0.93,
                "q4_adventurous_activity": 0.65,
                "q5_ultimate_day": 0.78,
                "q6_comfort_zone": 0.88,
                "q7_conversation_type": 0.70
            }},
            "explanation": "You two would be a great match because... [brief 2-3 line personalized explanation addressing both users]"
        }}
        """
        
        response = model.generate_content(prompt)
        
        json_match = re.search(r'\{[\s\S]*\}', response.text)
        if not json_match:
            raise ValueError("No JSON found in response")
        
        result = json.loads(json_match.group())
        scores = result['scores']
        explanation = result['explanation']
        
        weighted_score = sum(
            scores.get(q, 0) * weight
            for q, weight in weights.items()
        ) / sum(weights.values())

        return max(0.0, min(1.0, weighted_score)), explanation
        
    except Exception as e:
        print(f"Error calculating personality similarity: {str(e)}")
        return 0.5, "Unable to generate explanation due to error"
from typing import List, Dict
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime

def calculate_profile_similarity(current_user: User, other_users: List[User]) -> List[Dict]:
    """
    Calculate profile similarity scores between current user and other users
    with increased focus on shared interests and location.
    """
    if not other_users:
        return []
    
    similarity_scores = []
    
    for other_user in other_users:
        # Calculate interest similarity
        current_interests = set(current_user.interests)
        other_interests = set(other_user.interests)
        
        shared_interests = current_interests & other_interests
        total_interests = current_interests | other_interests
        
        # Calculate scores for different components
        interest_score = len(shared_interests) / len(total_interests) if total_interests else 0
        location_score = 0.0
        if other_user.city == current_user.city:
            location_score = 1.0
        elif other_user.country == current_user.country:
            location_score = 0.5
            
        # Age similarity (less weight)
        age_current = (datetime.now().date() - current_user.dob).days / 365.25
        age_other = (datetime.now().date() - other_user.dob).days / 365.25
        age_diff = abs(age_current - age_other)
        age_score = max(0, 1 - (age_diff / 10))  # Normalize age difference to 0-1 scale
        
        # Calculate final score with weights
        final_score = (
            interest_score * 0.7 +  # 70% weight to interests
            location_score * 0.2 +  # 20% weight to location
            age_score * 0.1        # 10% weight to age
        )
        
        # Build explanation
        location_match = ""
        if other_user.city == current_user.city:
            location_match = " and are in the same city"
        elif other_user.country == current_user.country:
            location_match = " and are in the same country"
        
        interest_percentage = (len(shared_interests) / len(total_interests) * 100) if total_interests else 0
        explanation = (f"You share {len(shared_interests)} interests: {', '.join(shared_interests)} "
                      f"({interest_percentage:.1f}% overlap){location_match}")
        
        # Debug information
        print(f"\nMatching details for {other_user.email}:")
        print(f"Shared interests: {shared_interests}")
        print(f"Interest score: {interest_score:.2f}")
        print(f"Location score: {location_score:.2f}")
        print(f"Age score: {age_score:.2f}")
        print(f"Final score: {final_score:.2f}")
        
        similarity_scores.append({
            "user": other_user,
            "score": float(final_score),
            "profile_explanation": explanation,
            "shared_interests": list(shared_interests)
        })
    
    return sorted(similarity_scores, key=lambda x: x["score"], reverse=True)


def get_combined_rankings(event_id: int, user_email: str) -> List[Dict]:
    """
    Get combined rankings with explanations for matches
    """
    event_users = User.query.join(UserEvent)\
        .filter(UserEvent.event_id == event_id)\
        .filter(User.email != user_email)\
        .all()
    
    current_user = User.query.filter_by(email=user_email).first()
    if not current_user:
        return []
    
    profile_scores = calculate_profile_similarity(current_user, event_users)
    personality_scores = []
    current_user_responses = UserResponse.query.filter_by(user_email=user_email).first()
    
    if current_user_responses:
        for other_user in event_users:
            other_user_responses = UserResponse.query.filter_by(user_email=other_user.email).first()
            if other_user_responses:
                personality_score, explanation = calculate_personality_similarity(
                    current_user_responses.__dict__,
                    other_user_responses.__dict__
                )
                personality_scores.append({
                    'user': other_user,
                    'score': personality_score,
                    'explanation': explanation
                })
    
    combined_scores = []
    for user in event_users:
        profile_score = next((s['score'] for s in profile_scores if s['user'].email == user.email), 0)
        personality_match = next((s for s in personality_scores if s['user'].email == user.email), 
                               {'score': 0, 'explanation': 'No personality data available. Please answer the personality questionnaire.'})
        
        combined_score = (profile_score * 0.4 + personality_match['score'] * 0.6)
        
        # Print detailed matching information to console
        print(f"\nMatch Analysis for {user.email}:")
        print(f"Profile Score: {profile_score:.2f}")
        print(f"Personality Score: {personality_match['score']:.2f}")
        print(f"Combined Score: {combined_score:.2f}")
        print(f"Explanation: {personality_match['explanation']}")
        print("-" * 80)
        
        combined_scores.append({
            'user': user,
            'score': combined_score,
            'profile_score': profile_score,
            'personality_score': personality_match['score'],
            'explanation': personality_match['explanation']
        })
    
    return sorted(combined_scores, key=lambda x: x['score'], reverse=True)

@app.route('/ranked_matches/<int:event_id>/', methods=['GET'])
def ranked_matches(event_id):
    if 'user' not in session:
        flash("Please log in to view matches.", 'warning')
        return redirect(url_for('login'))
    
    user_email = session['user']
    
    try:
        current_time = datetime.now()
        event = Event.query.get_or_404(event_id)
        
        # Check if event has expired
        if event.end_time <= current_time:
            # Clean up expired event data
            UserEvent.query.filter_by(event_id=event_id).delete()
            Event.query.filter_by(id=event_id).delete()
            db.session.commit()
            
            flash("This event has ended. The matches are no longer available.", 'info')
            return redirect(url_for('home'))
            
        is_participant = UserEvent.query.filter_by(
            user_email=user_email,
            event_id=event_id
        ).first() is not None
        is_host = event.host == user_email
        
        if not (is_participant or is_host):
            flash("You don't have access to these matches.", 'warning')
            return redirect(url_for('home'))
        
        user_responses = UserResponse.query.filter_by(user_email=user_email).first()
        if not user_responses:
            flash("Complete the personality questionnaire to get better matches!", 'warning')
        
        matches = get_combined_rankings(event_id, user_email)
        if not matches:
            flash("No matches available at this time.", 'info')
            return render_template('ranked_matches.html', matches=[])
        
        return render_template('ranked_matches.html', matches=matches)
        
    except Exception as e:
        app.logger.error(f"Error in rank_matches: {str(e)}")
        flash("An error occurred while retrieving matches. Please try again.", 'danger')
        return redirect(url_for('home'))
        
if __name__ == "__main__":
    # Create tables
    with app.app_context():
        db.create_all()
 
    app.run(debug=True)