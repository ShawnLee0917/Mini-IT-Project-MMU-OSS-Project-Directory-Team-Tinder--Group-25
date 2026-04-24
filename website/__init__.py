import os
from flask import Flask
from .models import db, User, Skill, Badge, Comment, Project, ProjectImage, Suggestion

DB_NAME = "mmu_ossd.db"

def create_app():
    app = Flask(__name__)
    
    app.config['SECRET_KEY'] = 'MiniITProjectG025'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    UPLOAD_FOLDER = os.path.join(app.root_path, 'static/uploads')
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    from .views import views
    app.register_blueprint(views, url_prefix='/')

    with app.app_context():
        db.create_all()
        print(f"Database {DB_NAME} initialized successfully!")

    return app