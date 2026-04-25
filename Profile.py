from flask import Flask, request, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = 'mmu-ossd-secret-key-2026'

DB_PATH      = os.path.join(os.path.dirname(__file__), 'mmu_ossd.db')
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXT  = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# SQLAlchemy Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


# ---------------------------------------------------------------------------
# Database Models
# ---------------------------------------------------------------------------

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    name = db.Column(db.String(255), nullable=False, default='MMU Student')
    faculty = db.Column(db.String(255), nullable=False, default='Faculty of Computing & Informatics')
    bio = db.Column(db.Text, default='')
    avatar_path = db.Column(db.String(255), default='')
    rank = db.Column(db.Integer, nullable=False, default=0)
    karma = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    skills = db.relationship('Skill', backref='user', lazy=True, cascade='all, delete-orphan')
    badges = db.relationship('Badge', backref='user', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='user', lazy=True, cascade='all, delete-orphan')
    projects = db.relationship('Project', backref='user', lazy=True, cascade='all, delete-orphan')
    suggestions = db.relationship('Suggestion', backref='user', lazy=True, cascade='all, delete-orphan')
    questions = db.relationship('Question', backref='author', lazy=True, cascade='all, delete-orphan')
    question_likes = db.relationship('QuestionLike', backref='user', lazy=True, cascade='all, delete-orphan')
    question_favorites = db.relationship('QuestionFavorite', backref='user', lazy=True, cascade='all, delete-orphan')
    question_comments = db.relationship('QuestionComment', backref='user', lazy=True, cascade='all, delete-orphan')


class Skill(db.Model):
    __tablename__ = 'skills'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    skill = db.Column(db.String(255), nullable=False)


class Badge(db.Model):
    __tablename__ = 'badges'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    badge = db.Column(db.String(255), nullable=False)


class Comment(db.Model):
    __tablename__ = 'comments'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Project(db.Model):
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default='')
    status = db.Column(db.String(50), nullable=False, default='Active')
    contributors = db.Column(db.String(50), default='1')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    suggestions = db.relationship('Suggestion', backref='project', lazy=True, cascade='all, delete-orphan')


class Suggestion(db.Model):
    __tablename__ = 'suggestions'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    match_score = db.Column(db.Integer, default=100)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'project_id', name='unique_user_project'),)


# ---------------------------------------------------------------------------
# Q&A Models
# ---------------------------------------------------------------------------

class Question(db.Model):
    __tablename__ = 'questions'

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title      = db.Column(db.String(300), nullable=False)
    body       = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(255), default='')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    likes     = db.relationship('QuestionLike',    backref='question', lazy=True, cascade='all, delete-orphan')
    favorites = db.relationship('QuestionFavorite', backref='question', lazy=True, cascade='all, delete-orphan')
    q_comments = db.relationship('QuestionComment', backref='question', lazy=True, cascade='all, delete-orphan')


class QuestionLike(db.Model):
    __tablename__ = 'question_likes'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'question_id', name='unique_user_question_like'),)


class QuestionFavorite(db.Model):
    __tablename__ = 'question_favorites'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'question_id', name='unique_user_question_fav'),)


class QuestionComment(db.Model):
    __tablename__ = 'question_comments'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    parent_id   = db.Column(db.Integer, db.ForeignKey('question_comments.id', ondelete='CASCADE'), nullable=True)
    body        = db.Column(db.Text, nullable=False)
    created_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def init_db():
    """Initialize database with tables and seed data"""
    with app.app_context():
        db.create_all()

        # Migrate: add new columns for existing databases
        with db.engine.connect() as conn:
            for sql in [
                "ALTER TABLE questions ADD COLUMN image_path VARCHAR(255) DEFAULT ''",
                "ALTER TABLE question_comments ADD COLUMN parent_id INTEGER REFERENCES question_comments(id)",
            ]:
                try:
                    conn.execute(db.text(sql))
                    conn.commit()
                except Exception:
                    pass  # Column already exists
        
        # Seed demo user
        demo_user = User.query.filter_by(email='student@mmu.edu.my').first()
        if not demo_user:
            demo_user = User(
                email='student@mmu.edu.my',
                name='MMU Student',
                faculty='Faculty of Computing & Informatics',
                rank=12,
                karma=450,
                password_hash=generate_password_hash('mmu1234')
            )
            db.session.add(demo_user)
            db.session.flush()
            
            # Add skills
            for skill_name in ['Python', 'Flask', 'Tailwind CSS', 'SQLite']:
                skill = Skill(user_id=demo_user.id, skill=skill_name)
                db.session.add(skill)
            
            # Add projects
            projects_data = [
                ('MMU Open Source Directory', 'Platform for student projects', '5'),
                ('Smart Parking System', 'IoT-based parking solution', '3'),
            ]
            for proj_name, proj_desc, contrib in projects_data:
                project = Project(
                    user_id=demo_user.id,
                    name=proj_name,
                    description=proj_desc,
                    status='Active',
                    contributors=contrib
                )
                db.session.add(project)
            
            db.session.commit()
        
        # Create sample other users
        other_users_data = [
            ('alice@mmu.edu.my', 'Alice Chen', 'Faculty of Engineering'),
            ('bob@mmu.edu.my', 'Bob Kumar', 'Faculty of Computing & Informatics'),
        ]
        
        for email, name, faculty in other_users_data:
            existing_user = User.query.filter_by(email=email).first()
            if not existing_user:
                user = User(
                    email=email,
                    name=name,
                    faculty=faculty,
                    password_hash=generate_password_hash('test1234')
                )
                db.session.add(user)
                db.session.flush()
                
                # Add skills
                if email == 'alice@mmu.edu.my':
                    skills = ['Python', 'JavaScript', 'React']
                    projects = [
                        ('E-Commerce Platform', 'Full-stack shopping system with React', '4'),
                        ('AI Chatbot', 'Python-based conversational AI', '2'),
                    ]
                else:  # bob
                    skills = ['Flask', 'SQLite', 'Docker']
                    projects = [
                        ('Task Manager API', 'REST API with Flask and SQLite', '2'),
                    ]
                
                for skill_name in skills:
                    skill = Skill(user_id=user.id, skill=skill_name)
                    db.session.add(skill)
                
                for proj_name, proj_desc, contrib in projects:
                    project = Project(
                        user_id=user.id,
                        name=proj_name,
                        description=proj_desc,
                        status='Active',
                        contributors=contrib
                    )
                    db.session.add(project)
        
        db.session.commit()



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

@app.route('/qna')
def qna_page():
    return app.send_static_file('QnA.html')

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
    
    try:
        user = User(email=email, name=name, password_hash=pw_hash)
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Email already registered'}), 409

    return jsonify({'success': True, 'message': 'Account created!'})


@app.route('/api/login', methods=['POST'])
def api_login():
    data     = request.get_json(silent=True) or {}
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    user = User.query.filter_by(email=email).first()

    if not user or not user.password_hash or \
       not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid email or password'}), 401

    session['user_email'] = user.email
    session['user_name']  = user.name
    return jsonify({'success': True, 'email': user.email, 'name': user.name})


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
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    skills = Skill.query.filter_by(user_id=user.id).all()
    badges = Badge.query.filter_by(user_id=user.id).all()

    avatar_url = f"/uploads/{user.avatar_path}" if user.avatar_path else ''
    return jsonify({
        'email':      user.email,
        'name':       user.name,
        'faculty':    user.faculty,
        'bio':        user.bio or '',
        'avatar_url': avatar_url,
        'rank':       user.rank,
        'karma':      user.karma,
        'skills':     [s.skill for s in skills],
        'badges':     [b.badge for b in badges],
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

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if name:
        user.name = name
        session['user_name'] = name
    if faculty:
        user.faculty = faculty
    user.bio = bio

    if skills is not None:
        Skill.query.filter_by(user_id=user.id).delete()
        for skill in skills:
            if skill.strip():
                skill_obj = Skill(user_id=user.id, skill=skill.strip())
                db.session.add(skill_obj)
    
    db.session.commit()

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
    user = User.query.filter_by(email=email).first()
    user.avatar_path = filename
    db.session.commit()

    return jsonify({'success': True, 'avatar_url': f'/uploads/{filename}'})


# ---------------------------------------------------------------------------
# Comments API
# ---------------------------------------------------------------------------

@app.route('/api/comments', methods=['GET'])
def get_comments():
    comments = db.session.query(Comment, User.name).join(User).order_by(
        Comment.created_at.desc()
    ).limit(50).all()
    
    result = []
    for comment, user_name in comments:
        result.append({
            'id': comment.id,
            'user_id': comment.user_id,
            'user_name': user_name,
            'comment': comment.comment,
            'created_at': comment.created_at.isoformat(),
        })
    
    return jsonify(result)


@app.route('/api/comments', methods=['POST'])
def post_comment():
    err = require_login()
    if err:
        return err
    
    data = request.get_json(silent=True) or {}
    comment_text = data.get('comment', '').strip()
    
    if not comment_text:
        return jsonify({'error': 'Comment cannot be empty'}), 400
    
    if len(comment_text) > 500:
        return jsonify({'error': 'Comment too long (max 500 characters)'}), 400
    
    email = session['user_email']
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    comment = Comment(user_id=user.id, comment=comment_text)
    db.session.add(comment)
    db.session.commit()
    
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
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    projects = Project.query.filter_by(user_id=user.id).order_by(
        Project.created_at.desc()
    ).all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'description': p.description,
        'status': p.status,
        'contributors': p.contributors,
        'created_at': p.created_at.isoformat(),
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
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    project = Project(
        user_id=user.id,
        name=name,
        description=description,
        status='Active',
        contributors='1'
    )
    db.session.add(project)
    db.session.commit()
    
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
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Get user's skills
    my_skills = Skill.query.filter_by(user_id=user.id).all()
    my_skill_list = [s.skill.lower() for s in my_skills]
    
    # Get all projects from OTHER users that match skills
    already_suggested = db.session.query(Suggestion.project_id).filter_by(user_id=user.id).all()
    already_suggested_ids = [s[0] for s in already_suggested]
    
    suggestions = db.session.query(
        Project,
        User.name,
        db.func.count(Skill.id).label('skill_matches')
    ).join(User, Project.user_id == User.id).outerjoin(
        Skill, Skill.user_id == User.id
    ).filter(
        Project.user_id != user.id,
        ~Project.id.in_(already_suggested_ids)
    ).group_by(Project.id).order_by(
        db.desc('skill_matches'),
        db.desc(Project.created_at)
    ).limit(5).all()
    
    result = []
    for project, owner_name, skill_matches in suggestions:
        result.append({
            'id': project.id,
            'project_id': project.id,
            'owner_name': owner_name,
            'name': project.name,
            'description': project.description,
            'status': project.status,
            'contributors': project.contributors,
            'match_score': min(100, 50 + (skill_matches or 0) * 10),
        })
    
    return jsonify(result)


@app.route('/api/suggestions/<int:project_id>', methods=['POST'])
def accept_suggestion(project_id):
    err = require_login()
    if err:
        return err
    
    email = session['user_email']
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Check if project exists
    project = Project.query.get(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    # Create suggestion record
    try:
        suggestion = Suggestion(user_id=user.id, project_id=project_id, match_score=100)
        db.session.add(suggestion)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Already suggested'}), 409
    
    return jsonify({'success': True, 'message': 'Project suggested to you!'})


# ---------------------------------------------------------------------------
# Q&A API
# ---------------------------------------------------------------------------

@app.route('/api/questions', methods=['GET'])
def get_questions():
    """Return all questions, newest first, with like/fav/comment counts and current user's status."""
    # We allow unauthenticated reads; current user detected if logged in
    current_user_id = None
    if 'user_email' in session:
        u = User.query.filter_by(email=session['user_email']).first()
        if u:
            current_user_id = u.id

    questions = db.session.query(Question, User.name).join(
        User, Question.user_id == User.id
    ).order_by(Question.created_at.desc()).limit(100).all()

    result = []
    for q, author_name in questions:
        like_count = QuestionLike.query.filter_by(question_id=q.id).count()
        fav_count  = QuestionFavorite.query.filter_by(question_id=q.id).count()
        cmt_count  = QuestionComment.query.filter_by(question_id=q.id).count()

        user_liked = False
        user_faved = False
        if current_user_id:
            user_liked = QuestionLike.query.filter_by(
                user_id=current_user_id, question_id=q.id).first() is not None
            user_faved = QuestionFavorite.query.filter_by(
                user_id=current_user_id, question_id=q.id).first() is not None

        result.append({
            'id':           q.id,
            'user_id':      q.user_id,
            'author_name':  author_name,
            'title':        q.title,
            'body':         q.body,
            'image_url':    f'/uploads/{q.image_path}' if q.image_path else '',
            'created_at':   q.created_at.isoformat(),
            'like_count':   like_count,
            'fav_count':    fav_count,
            'comment_count': cmt_count,
            'user_liked':   user_liked,
            'user_faved':   user_faved,
            'is_owner':     (current_user_id == q.user_id),
        })

    return jsonify(result)


@app.route('/api/questions', methods=['POST'])
def post_question():
    err = require_login()
    if err:
        return err

    # Support multipart (with image) and plain JSON
    if request.content_type and 'multipart' in request.content_type:
        title = request.form.get('title', '').strip()
        body  = request.form.get('body', '').strip()
    else:
        data  = request.get_json(silent=True) or {}
        title = data.get('title', '').strip()
        body  = data.get('body', '').strip()

    if not title:
        return jsonify({'error': 'Title is required'}), 400
    if not body:
        return jsonify({'error': 'Question body is required'}), 400
    if len(title) > 300:
        return jsonify({'error': 'Title too long (max 300 chars)'}), 400
    if len(body) > 5000:
        return jsonify({'error': 'Body too long (max 5000 chars)'}), 400

    user = User.query.filter_by(email=session['user_email']).first()
    q = Question(user_id=user.id, title=title, body=body)

    # Handle optional image
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"q_{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            q.image_path = filename

    db.session.add(q)
    db.session.commit()
    return jsonify({'success': True, 'id': q.id})


@app.route('/api/questions/<int:question_id>', methods=['DELETE'])
def delete_question(question_id):
    err = require_login()
    if err:
        return err

    user = User.query.filter_by(email=session['user_email']).first()
    q = Question.query.get(question_id)

    if not q:
        return jsonify({'error': 'Question not found'}), 404
    if q.user_id != user.id:
        return jsonify({'error': 'Not authorised'}), 403

    db.session.delete(q)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/questions/<int:question_id>/like', methods=['POST'])
def toggle_like(question_id):
    err = require_login()
    if err:
        return err

    user = User.query.filter_by(email=session['user_email']).first()
    existing = QuestionLike.query.filter_by(
        user_id=user.id, question_id=question_id).first()

    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(QuestionLike(user_id=user.id, question_id=question_id))
        liked = True

    db.session.commit()
    count = QuestionLike.query.filter_by(question_id=question_id).count()
    return jsonify({'liked': liked, 'like_count': count})


@app.route('/api/questions/<int:question_id>/favorite', methods=['POST'])
def toggle_favorite(question_id):
    err = require_login()
    if err:
        return err

    user = User.query.filter_by(email=session['user_email']).first()
    existing = QuestionFavorite.query.filter_by(
        user_id=user.id, question_id=question_id).first()

    if existing:
        db.session.delete(existing)
        faved = False
    else:
        db.session.add(QuestionFavorite(user_id=user.id, question_id=question_id))
        faved = True

    db.session.commit()
    count = QuestionFavorite.query.filter_by(question_id=question_id).count()
    return jsonify({'faved': faved, 'fav_count': count})


@app.route('/api/questions/<int:question_id>/comments', methods=['GET'])
def get_question_comments(question_id):
    rows = db.session.query(QuestionComment, User.name).join(
        User, QuestionComment.user_id == User.id
    ).filter(QuestionComment.question_id == question_id
    ).order_by(QuestionComment.created_at.asc()).all()

    current_user_id = None
    if 'user_email' in session:
        u = User.query.filter_by(email=session['user_email']).first()
        if u:
            current_user_id = u.id

    result = [{
        'id':          c.id,
        'author_name': name,
        'body':        c.body,
        'parent_id':   c.parent_id,
        'created_at':  c.created_at.isoformat(),
        'is_owner':    (current_user_id == c.user_id),
    } for c, name in rows]

    return jsonify(result)


@app.route('/api/questions/<int:question_id>/comments', methods=['POST'])
def post_question_comment(question_id):
    err = require_login()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    body = data.get('body', '').strip()

    if not body:
        return jsonify({'error': 'Comment cannot be empty'}), 400
    if len(body) > 1000:
        return jsonify({'error': 'Comment too long (max 1000 chars)'}), 400

    q = Question.query.get(question_id)
    if not q:
        return jsonify({'error': 'Question not found'}), 404

    parent_id = data.get('parent_id', None)
    if parent_id:
        parent = QuestionComment.query.get(parent_id)
        if not parent or parent.question_id != question_id:
            parent_id = None

    user = User.query.filter_by(email=session['user_email']).first()
    c = QuestionComment(user_id=user.id, question_id=question_id, body=body, parent_id=parent_id)
    db.session.add(c)
    db.session.commit()
    return jsonify({'success': True, 'id': c.id})


# ---------------------------------------------------------------------------
# Delete comment
# ---------------------------------------------------------------------------

@app.route('/api/questions/<int:question_id>/comments/<int:comment_id>', methods=['DELETE'])
def delete_question_comment(question_id, comment_id):
    err = require_login()
    if err:
        return err

    user = User.query.filter_by(email=session['user_email']).first()
    c = QuestionComment.query.get(comment_id)
    if not c or c.question_id != question_id:
        return jsonify({'error': 'Comment not found'}), 404
    if c.user_id != user.id:
        return jsonify({'error': 'Not authorised'}), 403

    db.session.delete(c)
    db.session.commit()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Liked / Favorited question lists
# ---------------------------------------------------------------------------

def _build_question_result(q, author_name, current_user_id):
    like_count = QuestionLike.query.filter_by(question_id=q.id).count()
    fav_count  = QuestionFavorite.query.filter_by(question_id=q.id).count()
    cmt_count  = QuestionComment.query.filter_by(question_id=q.id).count()
    user_liked = QuestionLike.query.filter_by(user_id=current_user_id, question_id=q.id).first() is not None
    user_faved = QuestionFavorite.query.filter_by(user_id=current_user_id, question_id=q.id).first() is not None
    return {
        'id': q.id, 'user_id': q.user_id, 'author_name': author_name,
        'title': q.title, 'body': q.body,
        'image_url': f'/uploads/{q.image_path}' if q.image_path else '',
        'created_at': q.created_at.isoformat(),
        'like_count': like_count, 'fav_count': fav_count, 'comment_count': cmt_count,
        'user_liked': user_liked, 'user_faved': user_faved,
        'is_owner': (current_user_id == q.user_id),
    }


@app.route('/api/questions/liked', methods=['GET'])
def get_liked_questions():
    err = require_login()
    if err:
        return err
    user = User.query.filter_by(email=session['user_email']).first()
    rows = db.session.query(Question, User.name).join(
        User, Question.user_id == User.id
    ).join(QuestionLike, QuestionLike.question_id == Question.id
    ).filter(QuestionLike.user_id == user.id
    ).order_by(Question.created_at.desc()).all()
    return jsonify([_build_question_result(q, n, user.id) for q, n in rows])


@app.route('/api/questions/favorited', methods=['GET'])
def get_favorited_questions():
    err = require_login()
    if err:
        return err
    user = User.query.filter_by(email=session['user_email']).first()
    rows = db.session.query(Question, User.name).join(
        User, Question.user_id == User.id
    ).join(QuestionFavorite, QuestionFavorite.question_id == Question.id
    ).filter(QuestionFavorite.user_id == user.id
    ).order_by(Question.created_at.desc()).all()
    return jsonify([_build_question_result(q, n, user.id) for q, n in rows])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    print("Database initialised:", DB_PATH)
    print("Demo login -> student@mmu.edu.my / mmu1234")
    print("Server -> http://127.0.0.1:5000")
    app.run(debug=True)