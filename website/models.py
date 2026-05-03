from . import db
from datetime import datetime

project_members = db.Table('project_members',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    db.Column('project_id', db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True)
)

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    name = db.Column(db.String(255), nullable=False, default='MMU Student')
    faculty = db.Column(db.String(255), nullable=False, default='Faculty of Computing & Informatics')
    bio = db.Column(db.Text, default='')
    avatar_path = db.Column(db.String(255), default='')
    interests = db.Column(db.Text, default='')  # Comma-separated project interests
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
    project_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default='')
    status = db.Column(db.String(50), nullable=False, default='Active')
    repo_url = db.Column(db.String(255), default='')
    languages = db.Column(db.String(255), default='')
    roles_needed = db.Column(db.String(255), default='')
    contributors = db.Column(db.String(50), default='1')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    images = db.relationship('ProjectImage', backref='project', lazy=True, cascade='all, delete-orphan')
    suggestions = db.relationship('Suggestion', backref='project', lazy=True, cascade='all, delete-orphan')
    
    members = db.relationship('User', secondary=project_members, lazy='subquery',
        backref=db.backref('joined_projects', lazy=True))

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


# ---------------------------------------------------------------------------
# Project Comment Models
# ---------------------------------------------------------------------------

class CommentLabel(db.Model):
    """Predefined labels for issue and suggestion comments"""
    __tablename__ = 'comment_labels'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    color = db.Column(db.String(20), default='gray')  # Color code like 'red', 'green', 'blue', etc.
    description = db.Column(db.String(255), default='')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class ProjectComment(db.Model):
    """Comments on projects with different types and labels"""
    __tablename__ = 'project_comments'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    
    # Comment type: 'normal', 'issue', 'suggestion'
    comment_type = db.Column(db.String(50), nullable=False, default='normal')
    
    # Label for issue/suggestion comments
    label = db.Column(db.String(50), nullable=True)  # e.g., 'reject', 'todo', 'complete', 'in-progress', 'approved'
    
    # Role-based: 'user', 'team-member', 'owner'
    user_role = db.Column(db.String(20), nullable=False, default='user')
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    author = db.relationship('User', backref='project_comments')
    project = db.relationship('Project', backref='project_comments')
    
    __table_args__ = (db.Index('idx_project_comments', 'project_id', 'created_at'),)


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

    likes      = db.relationship('QuestionLike',    backref='question', lazy=True, cascade='all, delete-orphan')
    favorites  = db.relationship('QuestionFavorite', backref='question', lazy=True, cascade='all, delete-orphan')
    q_comments = db.relationship('QuestionComment', backref='question', lazy=True, cascade='all, delete-orphan')
    images     = db.relationship('QuestionImage', backref='question', lazy=True, cascade='all, delete-orphan')


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


class QuestionImage(db.Model):
    __tablename__ = 'question_images'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    image_path  = db.Column(db.String(255), nullable=False)


class QuestionComment(db.Model):
    __tablename__ = 'question_comments'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    parent_id   = db.Column(db.Integer, db.ForeignKey('question_comments.id', ondelete='CASCADE'), nullable=True)
    body        = db.Column(db.Text, nullable=False)
    created_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    images = db.relationship('QuestionCommentImage', backref='comment', lazy=True, cascade='all, delete-orphan')


class QuestionCommentImage(db.Model):
    __tablename__ = 'question_comment_images'

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('question_comments.id', ondelete='CASCADE'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
