import os
import threading
import webbrowser
import random
from datetime import datetime

from pymongo import MongoClient
from bson.objectid import ObjectId

from dotenv import load_dotenv
load_dotenv()

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
app.secret_key = os.environ.get("SECRET_KEY", "SAY_MY_NAME!")

# -----------------------------
# MONGODB ATLAS SETUP
# -----------------------------
MONGO_URI = os.environ.get("MONGO_URI")

mongo_client = MongoClient(MONGO_URI)

db = mongo_client["student_portal"]
users_collection = db["users"]

try:
    print("Connected Databases:", mongo_client.list_database_names())
except Exception as e:
    print("MongoDB Connection Error:", e)

# -----------------------------
# MAIL CONFIG
# -----------------------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.environ.get("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get("MAIL_USERNAME")
app.config['MAIL_TIMEOUT'] = 15

mail = Mail(app)

# -----------------------------
# LOGIN MANAGER
# -----------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please login first."
login_manager.login_message_category = "error"

# -----------------------------
# UPLOAD FOLDER
# -----------------------------
UPLOAD_FOLDER = "static/profile_pics"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# -----------------------------
# USER CLASS
# -----------------------------
class User(UserMixin):
    def __init__(self, id, username, email, profile_pic):
        self.id = str(id)
        self.username = username
        self.email = email
        self.profile_pic = profile_pic


# -----------------------------
# USER LOADER
# -----------------------------
@login_manager.user_loader
def load_user(user_id):
    try:
        user = users_collection.find_one(
            {"_id": ObjectId(user_id)}
        )

        if user:
            return User(
                id=user["_id"],
                username=user["username"],
                email=user["email"],
                profile_pic=user.get("profile_pic", "default.png")
            )

    except Exception as e:
        print("User Loader Error:", e)

    return None


# -----------------------------
# DYNAMIC LOGIN EMAIL
# -----------------------------
def send_login_email(user_email, username):
    try:
        with app.app_context():

            subjects = [
                "Login Successful - StudentSync",
                "Welcome Back to StudentSync!",
                "Your StudentSync Account Accessed",
                "New Login Alert - StudentSync",
                f"Hey {username}, You’re Back!"
            ]

            greetings = [
                f"Hello {username},",
                f"Welcome back {username},",
                f"Hey {username},",
                f"Hi {username},",
                f"Greetings {username},"
            ]

            messages = [
                "You have successfully logged into your StudentSync account.",
                "Your learning dashboard is now active and ready.",
                "A successful login was detected on your StudentSync profile.",
                "You’re all set — your StudentSync portal is ready for you.",
                "Your account was accessed successfully."
            ]

            motivational_lines = [
                "Keep learning, keep growing.",
                "Your future is built one step at a time.",
                "Stay consistent. Success follows.",
                "Every login is progress.",
                "Build. Learn. Achieve."
            ]

            greeting = random.choice(greetings)
            main_message = random.choice(messages)
            motivation = random.choice(motivational_lines)
            subject = random.choice(subjects)

            login_time = datetime.now().strftime("%d-%m-%Y | %I:%M %p")

            msg = Message(
                subject=subject,
                recipients=[user_email]
            )

            msg.body = f"""
{greeting}

{main_message}

Login Time: {login_time}

{motivation}

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
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        # Validation
        if not username or not email or not password:
            flash("All fields are required!", "error")
            return redirect(url_for("register"))

        # Check existing user
        existing_user = users_collection.find_one({
            "$or": [
                {"username": username},
                {"email": email}
            ]
        })

        if existing_user:
            flash("Username or email already exists!", "error")
            return redirect(url_for("register"))

        # Insert user
        users_collection.insert_one({
            "username": username,
            "email": email,
            "password": password,
            "profile_pic": "default.png",
            "created_at": datetime.utcnow()
        })

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# -----------------------------
# LOGIN
# -----------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Please enter both username and password!", "error")
            return redirect(url_for("login"))

        # Find user
        user = users_collection.find_one({
            "username": username,
            "password": password
        })

        if user:
            user_obj = User(
                id=user["_id"],
                username=user["username"],
                email=user["email"],
                profile_pic=user.get("profile_pic", "default.png")
            )

            login_user(user_obj)

            # Dynamic mail
            threading.Thread(
                target=send_login_email,
                args=(user["email"], user["username"]),
                daemon=True
            ).start()

            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password!", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


# -----------------------------
# DASHBOARD
# -----------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    profile_pic = current_user.profile_pic or "default.png"

    return render_template(
        "dashboard.html",
        student=current_user.username,
        profile_pic=profile_pic
    )


# -----------------------------
# EDIT PROFILE
# -----------------------------
@app.route('/edit_profile')
@login_required
def edit_profile():
    return render_template(
        "edit_profile.html",
        student=current_user.username,
        profile_pic=current_user.profile_pic
    )


# -----------------------------
# PROFILE PIC UPLOAD
# -----------------------------
@app.route('/upload_profile_pic', methods=['POST'])
@login_required
def upload_profile_pic():
    file = request.files.get("profile_image")

    if not file or file.filename == "":
        flash("Please select an image first!", "error")
        return redirect(url_for("dashboard"))

    filename = f"{current_user.username}_avatar.png"
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    try:
        file.save(filepath)

        users_collection.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$set": {"profile_pic": filename}}
        )

        flash("Profile picture updated successfully!", "success")

    except Exception as e:
        print("Upload Error:", e)
        flash("Profile picture upload failed!", "error")

    return redirect(url_for("dashboard"))


# -----------------------------
# LOGOUT
# -----------------------------
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully!", "success")
    return redirect(url_for("login"))


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
# MAIN
# -----------------------------
if __name__ == "__main__":

    # Open browser locally only
    if os.environ.get("RENDER") is None:
        webbrowser.open("http://127.0.0.1:5000")

    app.run(debug=False)