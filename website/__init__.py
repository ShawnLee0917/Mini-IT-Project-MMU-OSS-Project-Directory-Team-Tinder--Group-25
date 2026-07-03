from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
import os

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.secret_key = 'mmu-ossd-secret-key-2026'
    
    INSTANCE_PATH = os.path.join(os.path.dirname(__file__), 'instance')
    os.makedirs(INSTANCE_PATH, exist_ok=True) 
    DB_PATH = os.path.join(INSTANCE_PATH, 'mmu_ossd.db')

    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    db.init_app(app)
    

    from . views import views
    from . models import (User, Skill, Badge, Comment, Project, ProjectImage, Suggestion, ProjectComment, CommentLabel, Question, QuestionLike, QuestionFavorite, QuestionComment, QuestionImage, QuestionCommentImage, JoinRequest)

    app.register_blueprint(views, url_prefix='/')

    with app.app_context():
        db.create_all()
        _ensure_legacy_schema_columns()
        _initialize_default_labels()
        _initialize_admin_system()

    return app

def _ensure_legacy_schema_columns():
    """Add missing columns for older SQLite databases created before recent model upgrades."""
    try:
        inspector = inspect(db.engine)
        if 'project_comments' not in inspector.get_table_names():
            return

        columns = {col['name'] for col in inspector.get_columns('project_comments')}
        with db.engine.begin() as conn:
            if 'is_deleted' not in columns:
                conn.execute(text("ALTER TABLE project_comments ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
            if 'deleted_by_id' not in columns:
                conn.execute(text("ALTER TABLE project_comments ADD COLUMN deleted_by_id INTEGER"))
            if 'deleted_by_role' not in columns:
                conn.execute(text("ALTER TABLE project_comments ADD COLUMN deleted_by_role VARCHAR(20)"))
            if 'deleted_at' not in columns:
                conn.execute(text("ALTER TABLE project_comments ADD COLUMN deleted_at DATETIME"))

                # ─── user_settings missing columns ───
        if 'user_settings' in inspector.get_table_names():
            us_columns = {col['name'] for col in inspector.get_columns('user_settings')}
            with db.engine.begin() as conn:
                if 'notify_badges' not in us_columns:
                    conn.execute(text("ALTER TABLE user_settings ADD COLUMN notify_badges BOOLEAN DEFAULT 1"))

    except Exception as e:
        print(f"[SCHEMA] Warning during legacy column migration: {str(e)}")


def _initialize_default_labels():
    """Initialize default comment labels if they don't exist"""
    from .models import CommentLabel
    
    default_labels = [
        {'name': 'reject', 'color': 'red', 'description': 'Rejected suggestion or issue'},
        {'name': 'todo', 'color': 'yellow', 'description': 'Task to be done'},
        {'name': 'complete', 'color': 'green', 'description': 'Completed task'},
        {'name': 'in-progress', 'color': 'blue', 'description': 'Currently being worked on'},
        {'name': 'approved', 'color': 'emerald', 'description': 'Approved suggestion'},
        {'name': 'critical', 'color': 'rose', 'description': 'Critical issue'},
        {'name': 'bug', 'color': 'orange', 'description': 'Bug report'},
        {'name': 'feature-request', 'color': 'indigo', 'description': 'Feature request'},
        {'name': 'documentation', 'color': 'slate', 'description': 'Documentation task'},
        {'name': 'review-needed', 'color': 'purple', 'description': 'Needs review'},
    ]
    
    for label_data in default_labels:
        existing = CommentLabel.query.filter_by(name=label_data['name']).first()
        if not existing:
            label = CommentLabel(**label_data)
            db.session.add(label)
    
    db.session.commit()


def _initialize_admin_system():
    """Auto-initialize admin system on app startup"""
    from .models import User, ContentFlagKeyword
    
    try:
        # ─── Hardcoded admin emails ───
        ADMIN_EMAILS = [
            'kohkonghao@mmu.edu.my',
            'koh.kong.hao@student.mmu.edu.my',
            'Lee.Kai.Shuen@student.mmu.edu.my',
            'lee.kai.shuen@student.mmu.edu.my',
        ]
        
        for email in ADMIN_EMAILS:
            user = User.query.filter_by(email=email).first()
            if user and not user.is_admin:
                user.is_admin = True
                db.session.commit()
                print(f"[AUTO SETUP] Admin granted: {email}")
        
        # Initialize default flagged keywords if not present
        default_keywords = [
            {'keyword': 'click-here', 'category': 'spam', 'severity': 2},
            {'keyword': 'buy-now', 'category': 'spam', 'severity': 3},
            {'keyword': 'free-money', 'category': 'spam', 'severity': 4},
            {'keyword': 'earn-cash', 'category': 'spam', 'severity': 3},
            {'keyword': 'inappropriate', 'category': 'inappropriate', 'severity': 3},
            {'keyword': 'harmful-content', 'category': 'harmful', 'severity': 5},
        ]
        
        keywords_added = 0
        for kw_data in default_keywords:
            existing = ContentFlagKeyword.query.filter_by(keyword=kw_data['keyword']).first()
            if not existing:
                kw = ContentFlagKeyword(**kw_data)
                db.session.add(kw)
                keywords_added += 1
        
        if keywords_added > 0:
            db.session.commit()
            print(f"[AUTO SETUP] Added {keywords_added} default keywords")
        
    except Exception as e:
        print(f"[AUTO SETUP] Warning during initialization: {str(e)}")
        db.session.rollback()