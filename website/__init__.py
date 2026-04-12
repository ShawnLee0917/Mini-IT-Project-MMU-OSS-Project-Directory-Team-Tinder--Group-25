from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import path

db = SQLAlchemy()
DB_NAME = "mmu_ossd.db"

def create_app():

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'MiniITProjectG025'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'

    db.init_app(app)

    from .views import views
    app.register_blueprint(views, url_prefix='/')

    from .models import Project
    with app.app_context():
        db.create_all()

    return app