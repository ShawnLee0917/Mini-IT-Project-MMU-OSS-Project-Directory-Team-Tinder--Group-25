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

            CREATE TABLE IF NOT EXISTS comments (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                comment    TEXT    NOT NULL,
                created_at TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS projects (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name        TEXT    NOT NULL,
                description TEXT    DEFAULT '',
                status      TEXT    NOT NULL DEFAULT 'Active',
                contributors TEXT DEFAULT '1',
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS suggestions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                project_id          INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                match_score         INTEGER DEFAULT 100,
                created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user_id, project_id)
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
            # Add sample projects
            conn.execute(
                "INSERT OR IGNORE INTO projects (user_id, name, description, status, contributors) "
                "VALUES (?, ?, ?, ?, ?)",
                (uid, 'MMU Open Source Directory', 'Platform for student projects', 'Active', '5')
            )
            conn.execute(
                "INSERT OR IGNORE INTO projects (user_id, name, description, status, contributors) "
                "VALUES (?, ?, ?, ?, ?)",
                (uid, 'Smart Parking System', 'IoT-based parking solution', 'Active', '3')
            )
        
        # Create sample other users and projects
        other_users = [
            ('alice@mmu.edu.my', 'Alice Chen', 'Faculty of Engineering'),
            ('bob@mmu.edu.my', 'Bob Kumar', 'Faculty of Computing & Informatics'),
        ]
        
        for email, name, faculty in other_users:
            conn.execute(
                "INSERT OR IGNORE INTO users (email, name, faculty, password_hash) "
                "VALUES (?, ?, ?, ?)",
                (email, name, faculty, generate_password_hash('test1234'))
            )
        
        # Add skills and projects for other users
        alice = conn.execute("SELECT id FROM users WHERE email = 'alice@mmu.edu.my'").fetchone()
        if alice:
            for s in ['Python', 'JavaScript', 'React']:
                conn.execute(
                    "INSERT OR IGNORE INTO skills (user_id, skill) VALUES (?, ?)",
                    (alice['id'], s)
                )
            conn.execute(
                "INSERT OR IGNORE INTO projects (user_id, name, description, status, contributors) "
                "VALUES (?, ?, ?, ?, ?)",
                (alice['id'], 'E-Commerce Platform', 'Full-stack shopping system with React', 'Active', '4')
            )
            conn.execute(
                "INSERT OR IGNORE INTO projects (user_id, name, description, status, contributors) "
                "VALUES (?, ?, ?, ?, ?)",
                (alice['id'], 'AI Chatbot', 'Python-based conversational AI', 'Active', '2')
            )
        
        bob = conn.execute("SELECT id FROM users WHERE email = 'bob@mmu.edu.my'").fetchone()
        if bob:
            for s in ['Flask', 'SQLite', 'Docker']:
                conn.execute(
                    "INSERT OR IGNORE INTO skills (user_id, skill) VALUES (?, ?)",
                    (bob['id'], s)
                )
            conn.execute(
                "INSERT OR IGNORE INTO projects (user_id, name, description, status, contributors) "
                "VALUES (?, ?, ?, ?, ?)",
                (bob['id'], 'Task Manager API', 'REST API with Flask and SQLite', 'Active', '2')
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
# Comments API
# ---------------------------------------------------------------------------

@app.route('/api/comments', methods=['GET'])
def get_comments():
    with get_db() as conn:
        comments = conn.execute("""
            SELECT c.id, c.user_id, u.name as user_name, c.comment, c.created_at
            FROM comments c
            JOIN users u ON c.user_id = u.id
            ORDER BY c.created_at DESC
            LIMIT 50
        """).fetchall()
    
    return jsonify([{
        'id': c['id'],
        'user_id': c['user_id'],
        'user_name': c['user_name'],
        'comment': c['comment'],
        'created_at': c['created_at'],
    } for c in comments])


@app.route('/api/comments', methods=['POST'])
def post_comment():
    err = require_login()
    if err:
        return err
    
    data = request.get_json(silent=True) or {}
    comment = data.get('comment', '').strip()
    
    if not comment:
        return jsonify({'error': 'Comment cannot be empty'}), 400
    
    if len(comment) > 500:
        return jsonify({'error': 'Comment too long (max 500 characters)'}), 400
    
    email = session['user_email']
    with get_db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        conn.execute(
            "INSERT INTO comments (user_id, comment) VALUES (?, ?)",
            (user['id'], comment)
        )
        conn.commit()
    
    return jsonify({'success': True, 'message': 'Comment posted'})


# ---------------------------------------------------------------------------
# Projects API
# ---------------------------------------------------------------------------

@app.route('/api/projects', methods=['GET'])
def get_projects():
    err = require_login()
    if err:
        return err
    
    email = session['user_email']
    with get_db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        projects = conn.execute(
            "SELECT id, name, description, status, contributors, created_at "
            "FROM projects WHERE user_id = ? ORDER BY created_at DESC",
            (user['id'],)
        ).fetchall()
    
    return jsonify([{
        'id': p['id'],
        'name': p['name'],
        'description': p['description'],
        'status': p['status'],
        'contributors': p['contributors'],
        'created_at': p['created_at'],
    } for p in projects])


@app.route('/api/projects', methods=['POST'])
def create_project():
    err = require_login()
    if err:
        return err
    
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    
    if not name:
        return jsonify({'error': 'Project name is required'}), 400
    
    email = session['user_email']
    with get_db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        conn.execute(
            "INSERT INTO projects (user_id, name, description, status, contributors) "
            "VALUES (?, ?, ?, ?, ?)",
            (user['id'], name, description, 'Active', '1')
        )
        conn.commit()
    
    return jsonify({'success': True, 'message': 'Project created'})


# ---------------------------------------------------------------------------
# Suggestions API
# ---------------------------------------------------------------------------

@app.route('/api/suggestions', methods=['GET'])
def get_suggestions():
    err = require_login()
    if err:
        return err
    
    email = session['user_email']
    with get_db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user's skills
        my_skills = conn.execute(
            "SELECT skill FROM skills WHERE user_id = ?", (user['id'],)
        ).fetchall()
        my_skill_list = [s['skill'].lower() for s in my_skills]
        
        # Get all projects from OTHER users that match skills
        suggestions = conn.execute("""
            SELECT DISTINCT p.id, p.user_id, u.name as owner_name, p.name, p.description, 
                   p.status, p.contributors, COUNT(sk.skill) as skill_matches
            FROM projects p
            JOIN users u ON p.user_id = u.id
            LEFT JOIN skills sk ON sk.user_id = u.id
            WHERE p.user_id != ? 
              AND p.id NOT IN (SELECT project_id FROM suggestions WHERE user_id = ?)
              AND (sk.skill IN ({}) OR 1=1)
            GROUP BY p.id
            ORDER BY skill_matches DESC, p.created_at DESC
            LIMIT 5
        """.format(','.join(['?']*len(my_skill_list)) if my_skill_list else '1'), 
        tuple([user['id'], user['id']] + my_skill_list)).fetchall()
    
    result = []
    for s in suggestions:
        result.append({
            'id': s['id'],
            'project_id': s['id'],
            'owner_name': s['owner_name'],
            'name': s['name'],
            'description': s['description'],
            'status': s['status'],
            'contributors': s['contributors'],
            'match_score': min(100, 50 + (s['skill_matches'] or 0) * 10),
        })
    
    return jsonify(result)


@app.route('/api/suggestions/<int:project_id>', methods=['POST'])
def accept_suggestion(project_id):
    err = require_login()
    if err:
        return err
    
    email = session['user_email']
    with get_db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if project exists
        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Create suggestion record
        try:
            conn.execute(
                "INSERT INTO suggestions (user_id, project_id, match_score) VALUES (?, ?, ?)",
                (user['id'], project_id, 100)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Already suggested'}), 409
    
    return jsonify({'success': True, 'message': 'Project suggested to you!'})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    print("Database initialised:", DB_PATH)
    print("Demo login → student@mmu.edu.my / mmu1234")
    print("Server → http://127.0.0.1:5000")
    app.run(debug=True)
