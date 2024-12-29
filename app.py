from flask import Flask, render_template, url_for, request, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import supabase
import random
import qrcode
from io import BytesIO
from datetime import datetime
from flask import send_file


app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres.jgmvvjlfnqimbwoqqfam:poonambhogle@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
app.secret_key = "SecretestKey"

db = SQLAlchemy(app)
supabase_url = "https://jgmvvjlfnqimbwoqqfam.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpnbXZ2amxmbnFpbWJ3b3FxZmFtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzUyOTczMTEsImV4cCI6MjA1MDg3MzMxMX0.jED2-HuAoiAdY_BSqFAr2YIaHjF9eSIzdppmSCy1x7Y"  # Ensure this key is correct
supabase_client = supabase.create_client(supabase_url, supabase_key)

class User(db.Model):
    __tablename__ = 'user'
    name = db.Column(db.String(120), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    dob = db.Column(db.Date, nullable=False)
    interests = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(120), nullable=False)
    country = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)  # Added missing field
    email = db.Column(db.String(120), primary_key=True, unique=True, nullable=False) 

class Event(db.Model):
    __tablename__ = 'event'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    host = db.Column(db.String(120), nullable=False)

# UserEvent Model (Many-to-Many relationship between User and Event)
class UserEvent(db.Model):
    __tablename__ = 'user_event'
    user_email = db.Column(db.String(120), db.ForeignKey('user.email'), primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), primary_key=True)

# UserMatches Model (User matching table with self-referencing foreign keys)
class UserMatches(db.Model):
    __tablename__ = 'user_matches'
    email_1 = db.Column(db.String(120), db.ForeignKey('user.email'), primary_key=True)
    email_2 = db.Column(db.String(120), db.ForeignKey('user.email'), primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), primary_key=True)

with app.app_context():
    db.drop_all()  # Only if you need to reset the tables
    db.create_all()
# Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/profile/')
def profile():
    if 'user' not in session:
        flash("Please log in to view your profile.", 'warning')
        return redirect(url_for('login'))
    
    # Fetch user data from the database based on the logged-in user's email
    user_email = session['user']
    user = User.query.filter_by(email=user_email).first()  # Query the user by email
    
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
        # Example logic: Find matches based on the query
        search_results = ["Example Match 1", "Example Match 2"]  # Replace with actual logic
    return render_template('search.html', results=search_results)

@app.route('/matches/')
def matches():
    matched_people = ["Alice", "Bob", "Charlie"]
    return render_template('matches.html', matches=matched_people)

@app.route('/signup/', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            gender = request.form.get('gender')
            dob = request.form.get('dob')
            interests = request.form.get('interests')
            city = request.form.get('city')
            country = request.form.get('country')
            password = request.form.get('password')
            email = request.form.get('email')  # Add email field to your form

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
                interests=interests,
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
            db.session.rollback()  # Rollback on error
            print(f"Error during signup: {str(e)}")  # Log the error
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
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard/')
def dashboard():
    if 'user' not in session:
        flash("Please log in to access the dashboard.", 'warning')
        return redirect(url_for('login'))
    return render_template('dashboard.html', user=session['user'])

@app.route('/logout/')
def logout():
    session.pop('user', None)
    flash("You have been logged out.", 'info')
    return redirect(url_for('login'))

@app.route('/edit_profile/', methods=['GET', 'POST'])
def edit_profile():
    if 'user' not in session:
        flash("Please log in to edit your profile.", 'warning')
        return redirect(url_for('login'))

    # Get the user by email from session
    user_email = session['user']
    user = User.query.filter_by(email=user_email).first()
    
    if request.method == 'POST':
        # Get the new values from the form
        new_email = request.form['email']

        # Ensure the new email is unique
        if new_email != user.email and User.query.filter_by(email=new_email).first():
            flash("Email is already in use. Please choose a different one.", 'danger')
        else:
            # Update the user's email and password
            user.email = new_email

            try:
                db.session.commit()
                session['user'] = new_email  # Update the session with the new email
                flash("Profile updated successfully!", 'success')
                return redirect(url_for('profile'))
            except Exception as e:
                flash(f"Error updating profile: {e}", 'danger')

    return render_template('edit_profile.html', user=user)

# Update the Event route in app.py
@app.route('/host/', methods=['GET', 'POST'])
def host_event():
    if 'user' not in session:
        flash("Please log in to host an event.", 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            name = request.form.get('name')
            start_time_str = request.form.get('start_time')
            end_time_str = request.form.get('end_time')
            
            # Validate required fields
            if not all([name, start_time_str, end_time_str]):
                flash("All fields are required.", 'danger')
                return redirect(url_for('host'))

            # Parse datetime strings
            start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')

            # Validate end time is after start time
            if end_time <= start_time:
                flash("End time must be after start time.", 'danger')
                return redirect(url_for('host'))

            # Generate unique 4-digit code
            while True:
                code = f"{random.randint(1000, 9999)}"
                if not Event.query.filter_by(code=code).first():
                    break

            # Create new event
            event = Event(
                name=name,
                code=code,
                start_time=start_time,
                end_time=end_time,
                host=session['user']  # Use logged-in user's email as host
            )

            db.session.add(event)
            db.session.commit()

            # Generate QR code
            qr = qrcode.make(code)
            buffer = BytesIO()
            qr.save(buffer)
            buffer.seek(0)

            flash(f"Event '{name}' created successfully! Code: {code}", 'success')
            return send_file(buffer, mimetype="image/png", as_attachment=True, download_name="event_qr.png")

        except ValueError as e:
            flash("Invalid date/time format. Please use the datetime picker.", 'danger')
            return redirect(url_for('host'))
        except Exception as e:
            db.session.rollback()
            print(f"Error creating event: {str(e)}")
            flash("Failed to create event. Please try again.", 'danger')
            return redirect(url_for('host'))

    return render_template('host_event.html')

@app.route('/join/', methods=['GET', 'POST'])
def join_event():
    if 'user' not in session:
        flash("Please log in to join an event.", 'warning')
        return redirect(url_for('login'))

    event_users = []
    if request.method == 'POST':
        code = request.form.get('code')
        event = Event.query.filter_by(code=code).first()

        if event:
            # Check if the user is already part of the event
            existing_user_event = UserEvent.query.filter_by(user_email=session['user'], event_code=code).first()
            if not existing_user_event:
                # Add the logged-in user to the event
                user_event = UserEvent(user_email=session['user'], event_code=code)
                try:
                    db.session.add(user_event)
                    db.session.commit()
                    flash("Successfully joined the event!", 'success')
                except Exception as e:
                    flash(f"Failed to join the event: {e}", 'danger')
            else:
                flash("You are already part of this event.", 'info')

            # Fetch all users in the event
            event_users = User.query.join(UserEvent, User.email == UserEvent.user_email)\
                                    .filter(UserEvent.event_code == code).all()
        else:
            flash("Invalid event code. Please try again.", 'danger')

    return render_template('join_event.html', event_users=event_users)



if __name__ == "__main__":
    # Create tables
    with app.app_context():
        db.create_all()
    app.run(debug=True)
