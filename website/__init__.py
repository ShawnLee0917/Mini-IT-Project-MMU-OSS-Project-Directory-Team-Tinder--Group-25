from flask import Flask
from flask_sqlalchemy import SQLAlchemy
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
        _initialize_default_labels()
        _initialize_admin_system()

    return app

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