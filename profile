from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
import uuid

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = 'mmu-ossd-secret-key-2026'

DB_PATH      = os.path.join(os.path.dirname(__file__), 'mmu_ossd.db')
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXT  = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT    UNIQUE NOT NULL,
                password_hash TEXT,
                name          TEXT    NOT NULL DEFAULT 'MMU Student',
                faculty       TEXT    NOT NULL DEFAULT 'Faculty of Computing & Informatics',
                bio           TEXT    DEFAULT '',
                avatar_path   TEXT    DEFAULT '',
                rank          INTEGER NOT NULL DEFAULT 0,
                karma         INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS skills (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                skill    TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS badges (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                badge    TEXT    NOT NULL
            );
        """)

        # Migrate existing DB — add new columns if they don't exist yet
        for col, definition in [
            ('bio',           'TEXT DEFAULT ""'),
            ('avatar_path',   'TEXT DEFAULT ""'),
            ('password_hash', 'TEXT'),
        ]:
            try:
                conn.execute(f'ALTER TABLE users ADD COLUMN {col} {definition}')
            except Exception:
                pass  # Column already exists

        # Seed demo user
        demo_pw = generate_password_hash('mmu1234')
        conn.execute("""
            INSERT OR IGNORE INTO users (email, name, faculty, rank, karma, password_hash)
            VALUES ('student@mmu.edu.my', 'MMU Student',
                    'Faculty of Computing & Informatics', 12, 450, ?)
        """, (demo_pw,))
        conn.execute("""
            UPDATE users SET password_hash = ?
            WHERE email = 'student@mmu.edu.my' AND password_hash IS NULL
        """, (demo_pw,))

        seed_user = conn.execute(
            "SELECT id FROM users WHERE email = 'student@mmu.edu.my'"
        ).fetchone()
        if seed_user:
            uid = seed_user['id']
            for s in ['Python', 'Flask', 'Tailwind CSS', 'SQLite']:
                conn.execute(
                    "INSERT OR IGNORE INTO skills (user_id, skill) "
                    "SELECT ?, ? WHERE NOT EXISTS "
                    "(SELECT 1 FROM skills WHERE user_id=? AND skill=?)",
                    (uid, s, uid, s)
                )
        conn.commit()


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return app.send_static_file('login.html')

@app.route('/login')
def login_page():
    return app.send_static_file('login.html')

@app.route('/register')
def register_page():
    return app.send_static_file('register.html')

@app.route('/profile')
def profile_page():
    return app.send_static_file('Profile.html')

@app.route('/home')
def home_page():
    return app.send_static_file('Navigation.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ---------------------------------------------------------------------------
# Auth API
# ---------------------------------------------------------------------------

@app.route('/api/register', methods=['POST'])
def api_register():
    data     = request.get_json(silent=True) or {}
    email    = data.get('email', '').strip().lower()
    name     = data.get('name', '').strip()
    password = data.get('password', '')

    if not email or not password or not name:
        return jsonify({'error': 'All fields are required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    pw_hash = generate_password_hash(password)
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
                (email, name, pw_hash)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Email already registered'}), 409

    return jsonify({'success': True, 'message': 'Account created!'})


@app.route('/api/login', methods=['POST'])
def api_login():
    data     = request.get_json(silent=True) or {}
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

    if not user or not user['password_hash'] or \
       not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid email or password'}), 401

    session['user_email'] = user['email']
    session['user_name']  = user['name']
    return jsonify({'success': True, 'email': user['email'], 'name': user['name']})


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success': True})


@app.route('/api/me', methods=['GET'])
def api_me():
    if 'user_email' not in session:
        return jsonify({'loggedIn': False}), 401
    return jsonify({
        'loggedIn': True,
        'email':    session['user_email'],
        'name':     session['user_name'],
    })


# ---------------------------------------------------------------------------
# Profile API  (all require login)
# ---------------------------------------------------------------------------

def require_login():
    if 'user_email' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    return None


@app.route('/api/profile', methods=['GET'])
def get_profile():
    err = require_login()
    if err:
        return err

    email = session['user_email']
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        skills = conn.execute(
            "SELECT skill FROM skills WHERE user_id = ?", (user['id'],)
        ).fetchall()
        badges = conn.execute(
            "SELECT badge FROM badges WHERE user_id = ?", (user['id'],)
        ).fetchall()

    avatar_url = f"/uploads/{user['avatar_path']}" if user['avatar_path'] else ''
    return jsonify({
        'email':      user['email'],
        'name':       user['name'],
        'faculty':    user['faculty'],
        'bio':        user['bio'] or '',
        'avatar_url': avatar_url,
        'rank':       user['rank'],
        'karma':      user['karma'],
        'skills':     [r['skill'] for r in skills],
        'badges':     [r['badge'] for r in badges],
    })


@app.route('/api/profile', methods=['PUT'])
def update_profile():
    err = require_login()
    if err:
        return err

    data    = request.get_json(silent=True) or {}
    email   = session['user_email']
    name    = data.get('name')
    faculty = data.get('faculty')
    bio     = data.get('bio', '')
    skills  = data.get('skills', [])

    with get_db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        uid = user['id']

        if name:
            conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, uid))
            session['user_name'] = name
        if faculty:
            conn.execute("UPDATE users SET faculty = ? WHERE id = ?", (faculty, uid))
        conn.execute("UPDATE users SET bio = ? WHERE id = ?", (bio, uid))

        if skills is not None:
            conn.execute("DELETE FROM skills WHERE user_id = ?", (uid,))
            for skill in skills:
                if skill.strip():
                    conn.execute(
                        "INSERT INTO skills (user_id, skill) VALUES (?, ?)",
                        (uid, skill.strip())
                    )
        conn.commit()

    return jsonify({'success': True, 'message': 'Profile updated'})


@app.route('/api/profile/avatar', methods=['POST'])
def upload_avatar():
    err = require_login()
    if err:
        return err

    if 'avatar' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'Allowed types: PNG, JPG, GIF, WEBP'}), 400

    ext      = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOAD_FOLDER, filename))

    email = session['user_email']
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET avatar_path = ? WHERE email = ?", (filename, email)
        )
        conn.commit()

    return jsonify({'success': True, 'avatar_url': f'/uploads/{filename}'})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    print("Database initialised:", DB_PATH)
    print("Demo login → student@mmu.edu.my / mmu1234")
    print("Server → http://127.0.0.1:5000")
    app.run(debug=True)
