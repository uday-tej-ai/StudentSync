import os
import threading
from dotenv import load_dotenv
load_dotenv()

import sqlite3
import webbrowser

from flask import Flask, request, render_template, redirect, url_for, flash
from flask_mail import Mail, Message
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)

# -----------------------------
# FLASK APP SETUP
# -----------------------------
app = Flask(__name__)

# Secret Key
app.secret_key = os.environ.get("SECRET_KEY", "SAY_MY_NAME!")

# -----------------------------
# MAIL CONFIG
# -----------------------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get("MAIL_USERNAME")

# Faster fail on Render
app.config['MAIL_TIMEOUT'] = 5

mail = Mail(app)

# -----------------------------
# FLASK LOGIN SETUP
# -----------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# -----------------------------
# FOLDER SETUP
# -----------------------------
UPLOAD_FOLDER = 'static/profile_pics'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# -----------------------------
# DATABASE
# -----------------------------
def get_db_connection():
    conn = sqlite3.connect("database.db", timeout=20)
    conn.row_factory = sqlite3.Row

    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            profile_pic TEXT DEFAULT 'default.png'
        )
    ''')

    return conn


# -----------------------------
# USER CLASS
# -----------------------------
class User(UserMixin):
    def __init__(self, id, username, email, profile_pic):
        self.id = id
        self.username = username
        self.email = email
        self.profile_pic = profile_pic


# -----------------------------
# USER LOADER
# -----------------------------
@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    conn.close()

    if user:
        return User(
            id=user["id"],
            username=user["username"],
            email=user["email"],
            profile_pic=user["profile_pic"]
        )

    return None


# -----------------------------
# EMAIL FUNCTION
# -----------------------------
def send_login_email(user_email, username):
    try:
        with app.app_context():
            msg = Message(
                subject="Login Successful - StudentSync",
                recipients=[user_email]
            )

            msg.body = f"""
Hello {username},

You have successfully logged into your StudentSync account.

Thank you for visiting StudentSync.

If this login was not made by you, please secure your account immediately.

Regards,
StudentSync Team
            """

            mail.send(msg)

    except Exception as e:
        print("Mail Error:", e)


# -----------------------------
# HOME / WELCOME
# -----------------------------
@app.route('/')
def welcome():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    return render_template("welcome.html")


# -----------------------------
# REGISTER
# -----------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check existing email
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            flash("User already exists!", "error")
            return redirect(url_for('register'))

        # Insert new user
        cursor.execute(
            "INSERT INTO users (username, email, password, profile_pic) VALUES (?, ?, ?, ?)",
            (username, email, password, 'default.png')
        )

        conn.commit()
        conn.close()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for('login'))

    return render_template("register.html")


# -----------------------------
# LOGIN
# -----------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password)
        )

        user = cursor.fetchone()
        conn.close()

        if user:
            # Create login object
            user_obj = User(
                id=user["id"],
                username=user["username"],
                email=user["email"],
                profile_pic=user["profile_pic"]
            )

            # Login immediately
            login_user(user_obj)

            # Send email in background thread
            threading.Thread(
                target=send_login_email,
                args=(user["email"], user["username"]),
                daemon=True
            ).start()

            flash("Login successful!", "success")

            return redirect(url_for('dashboard'))

        else:
            flash("Invalid credentials!", "error")

    return render_template("login.html")


# -----------------------------
# DASHBOARD
# -----------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    pic = current_user.profile_pic if current_user.profile_pic else "default.png"

    return render_template(
        "dashboard.html",
        student=current_user.username,
        profile_pic=pic
    )


# -----------------------------
# EDIT PROFILE
# -----------------------------
@app.route('/edit_profile')
@login_required
def edit_profile():
    return render_template(
        "edit_profile.html",
        student=current_user.username
    )


# -----------------------------
# PROFILE PIC UPLOAD
# -----------------------------
@app.route('/upload_profile_pic', methods=['POST'])
@login_required
def upload_profile_pic():
    file = request.files.get('profile_image')

    if file and file.filename != '':
        username = current_user.username
        filename = f"{username}_avatar.png"

        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET profile_pic = ? WHERE id = ?",
            (filename, current_user.id)
        )

        conn.commit()
        conn.close()

        flash("Profile picture updated successfully!", "success")

    return redirect(url_for('dashboard'))


# -----------------------------
# LOGOUT
# -----------------------------
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully!", "success")
    return redirect(url_for('login'))


# -----------------------------
# EXTRA PRACTICE ROUTES
# -----------------------------
@app.route('/user/<name>')
def user(name):
    return f"Hello {name}"


@app.route('/student/<name>/<course>')
def student(name, course):
    return f"{name} studies {course}"


# -----------------------------
# LOCAL SERVER ONLY
# -----------------------------
if __name__ == '__main__':
    # Only open browser on local machine, never on Render
    if os.environ.get("RENDER") is None:
        webbrowser.open("http://127.0.0.1:5000")

    app.run(debug=False)