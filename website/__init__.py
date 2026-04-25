from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.secret_key = 'mmu-ossd-secret-key-2026'
    
    DB_PATH = os.path.join(os.path.dirname(__file__), 'mmu_ossd.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    db.init_app(app)

    from .views import views
    from .models import User, Skill, Badge, Comment, Project, ProjectImage, Suggestion

    app.register_blueprint(views, url_prefix='/')

    with app.app_context():
        db.create_all()

    return app