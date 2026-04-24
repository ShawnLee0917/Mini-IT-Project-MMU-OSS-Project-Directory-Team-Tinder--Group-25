# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

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
    
    project_name = db.Column(db.String(150), nullable=False)
    repo_url = db.Column(db.String(300), nullable=False)
    languages = db.Column(db.String(150))
    roles_needed = db.Column(db.String(100))
    description = db.Column(db.Text, default='')
    
    status = db.Column(db.String(50), nullable=False, default='Active')
    contributors = db.Column(db.String(50), default='1')
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    images = db.relationship('ProjectImage', backref='project', lazy=True, cascade="all, delete-orphan")
    suggestions = db.relationship('Suggestion', backref='project', lazy=True, cascade='all, delete-orphan')
class ProjectImage(db.Model):
    __tablename__ = 'project_images' 
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)


class Suggestion(db.Model):
    __tablename__ = 'suggestions'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    match_score = db.Column(db.Integer, default=100)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'project_id', name='unique_user_project'),)