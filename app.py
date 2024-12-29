from flask import Flask, render_template, url_for, request, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import supabase
import random
import qrcode
from io import BytesIO
from flask import send_file

app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres.jgmvvjlfnqimbwoqqfam:poonambhogle@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
app.secret_key = "SecretestKey"

# Initialize Database
db = SQLAlchemy(app)
supabase_url = "https://jgmvvjlfnqimbwoqqfam.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpnbXZ2amxmbnFpbWJ3b3FxZmFtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzUyOTczMTEsImV4cCI6MjA1MDg3MzMxMX0.jED2-HuAoiAdY_BSqFAr2YIaHjF9eSIzdppmSCy1x7Y"  # Ensure this key is correct
supabase_client = supabase.create_client(supabase_url, supabase_key)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=True)

# User Model
class User(db.Model):
    email = db.Column(db.String(120), unique=True, nullable=False, primary_key=True)
    password_hash = db.Column(db.String(200), nullable=False)

class UserEvent(db.Model):
    user_email = db.Column(db.String(120), db.ForeignKey('user.email'), primary_key=True)
    event_code = db.Column(db.String(10), db.ForeignKey('event.code'), primary_key=True)

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
        email = request.form.get('email')
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        
        if User.query.filter_by(email=email).first():
            flash("Email already registered. Please log in.", 'danger')
            return redirect(url_for('login'))
        
        try:
            new_user = User(email=email, password_hash=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            flash("Account created successfully! Please log in.", 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Sign-up failed: {e}", 'danger')
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

@app.route('/host/', methods=['GET', 'POST'])
def host_event():
    if request.method == 'POST':
        name = request.form.get('name')  # Event name (optional)
        code = f"{random.randint(1000, 9999)}"  # Generate 4-digit code
        event = Event(code=code, name=name)

        try:
            db.session.add(event)
            db.session.commit()

            # Generate QR code
            qr = qrcode.make(code)
            buffer = BytesIO()
            qr.save(buffer)
            buffer.seek(0)

            flash(f"Event created successfully! Code: {code}", 'success')
            return send_file(buffer, mimetype="image/png", as_attachment=True, download_name="event_qr.png")
        except Exception as e:
            flash(f"Failed to create event: {e}", 'danger')

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
