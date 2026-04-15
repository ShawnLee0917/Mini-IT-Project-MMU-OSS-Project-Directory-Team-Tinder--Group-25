from flask import Flask, render_template, request, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
import os

app = Flask(__name__, template_folder='.')
# Uses an environment variable for production, falls back to 'secret123' locally
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'secret123')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

db = SQLAlchemy(app)

# ======================
# TOKEN SETUP
# ======================
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

def generate_token(email):
    return s.dumps(email, salt='email-confirm')

def confirm_token(token, expiration=3600):
    try:
        email = s.loads(token, salt='email-confirm', max_age=expiration)
        return email
    except Exception:  
        return False

# ======================
# EMAIL VALIDATION
# ======================
def is_valid_mmu_email(email):
    """Check if email is a valid MMU student or staff email"""
    return email.endswith('@student.mmu.edu.my') or email.endswith('@mmu.edu.my')

# ======================
# DATABASE
# ======================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    is_verified = db.Column(db.Boolean, default=False)

# ======================
# HOME
# ======================
@app.route('/')
def home():
    if 'user_id' in session:
        return 'Welcome! You are logged in. <br><br> <a href="/logout">Logout</a>'
    return redirect('/login')

# ======================
# REGISTER
# ======================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not email or not password:
            return "Email and password are required!"
        
        # MMU EMAIL VALIDATION
        if not is_valid_mmu_email(email):
            return "Only @student.mmu.edu.my or @mmu.edu.my emails are allowed!"
        
        password = generate_password_hash(password)

        # CHECK IF USER EXISTS
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return "Email already registered!"

        # SAVE USER
        user = User(email=email, password=password)
        db.session.add(user)
        db.session.commit()

        # GENERATE VERIFICATION LINK
        token = generate_token(email)
        verification_link = url_for('verify_email', token=token, _external=True)

        print("\n=== EMAIL VERIFICATION LINK ===")
        print(verification_link)
        print("================================\n")

        return "Registered! Check terminal for verification link."

    return render_template('register1.html')

# ======================
# VERIFY EMAIL
# ======================
@app.route('/verify/<token>')
def verify_email(token):
    email = confirm_token(token)

    if not email:
        return "Invalid or expired link!"

    user = User.query.filter_by(email=email).first()

    if user:
        user.is_verified = True
        db.session.commit()
        return 'Email verified! You can now <a href="/login">login</a>.'

    return "User not found!"

# ======================
# LOGIN
# ======================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not email or not password:
            return "Email and password are required!"

        # MMU EMAIL VALIDATION
        if not is_valid_mmu_email(email):
            return "Only @student.mmu.edu.my or @mmu.edu.my emails are allowed!"

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):

            # CHECK VERIFIED
            if not user.is_verified:
                return "Please verify your email first!"

            session['user_id'] = user.id
            return redirect('/')

        return "Login failed! Please check your credentials."

    return render_template('login1.html')

# ======================
# LOGOUT
# ======================
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect('/login')

# ======================
# RUN
# ======================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True)