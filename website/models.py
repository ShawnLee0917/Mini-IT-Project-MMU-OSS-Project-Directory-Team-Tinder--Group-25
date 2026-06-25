from . import db
from datetime import datetime, timedelta, timezone, UTC

MYT = timezone(timedelta(hours=8))

class ProjectMember(db.Model):
    __tablename__ = 'project_members'
    
    # Composite Primary Key
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True)
    
    # Core field: 'admin' or 'member'. 
    # (Note: 'owner' is the project creator, recorded directly in Project's user_id)
    role = db.Column(db.String(20), nullable=False, default='member') 
    joined_at = db.Column(db.DateTime, default=datetime.now(MYT))

    # Establish relationship for easy access to the corresponding User object via project_member.user
    user = db.relationship('User', backref=db.backref('project_memberships', lazy='dynamic', cascade='all, delete-orphan'))

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    name = db.Column(db.String(255), nullable=False, default='MMU Student')
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    faculty = db.Column(db.String(255), nullable=False, default='Faculty of Computing & Informatics')
    bio = db.Column(db.Text, default='')
    avatar_path = db.Column(db.String(255), default='')
    interests = db.Column(db.Text, default='')  # Comma-separated project interests
    rank = db.Column(db.Integer, nullable=False, default=0)
    karma = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)  # Admin privilege for content moderation
    otp = db.Column(db.String(6), nullable=True)
    last_seen = db.Column(db.DateTime, nullable=True)
    
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
    starred_projects = db.relationship('ProjectStar', backref='user', lazy=True, cascade='all, delete-orphan')
    settings = db.relationship('UserSettings', backref='user', uselist=False, cascade='all, delete-orphan')


class UserSettings(db.Model):
    __tablename__ = 'user_settings'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    
    # Privacy settings
    profile_visibility = db.Column(db.String(20), nullable=False, default='public')  # 'public', 'private', 'friends'
    email_visibility = db.Column(db.Boolean, default=False)
    show_rank = db.Column(db.Boolean, default=True)
    show_karma = db.Column(db.Boolean, default=True)
    
    # Notification settings
    notify_qna_new_answers = db.Column(db.Boolean, default=True)
    notify_project_comments = db.Column(db.Boolean, default=True)
    notify_profile_views = db.Column(db.Boolean, default=False)
    notify_project_invites = db.Column(db.Boolean, default=True)
    notify_new_suggestions = db.Column(db.Boolean, default=True)
    notify_newsletter = db.Column(db.Boolean, default=False)
    
    # Display preferences
    theme = db.Column(db.String(20), nullable=False, default='light')  # 'light', 'dark'
    
    # Other preferences
    allow_direct_messages = db.Column(db.Boolean, default=True)
    auto_accept_collaborations = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT), onupdate=datetime.now(MYT))


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
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))


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
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))
    views = db.Column(db.Integer, default=0)
    
    # Relationships
    images = db.relationship('ProjectImage', backref='project', lazy=True, cascade='all, delete-orphan')
    suggestions = db.relationship('Suggestion', backref='project', lazy=True, cascade='all, delete-orphan')
    
    # Modification: Changed secondary pointing to db.Table to point to the new ProjectMember model
    members = db.relationship('ProjectMember', backref='project', lazy='subquery', cascade='all, delete-orphan')
    # ADDED: Relationship to easily count or access stars for this project
    stars = db.relationship('ProjectStar', backref='project', lazy=True, cascade='all, delete-orphan')

class ProjectViewLog(db.Model):
    __tablename__ = 'project_view_logs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True) 
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))

class ProjectStar(db.Model):
    __tablename__ = 'project_stars'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))
    
    # Ensure a user can only star a specific project once
    __table_args__ = (db.UniqueConstraint('user_id', 'project_id', name='unique_user_project_star'),)

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
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))
    
    __table_args__ = (db.UniqueConstraint('user_id', 'project_id', name='unique_user_project'),)


class JoinRequest(db.Model):
    __tablename__ = 'join_requests'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='pending')  # 'pending', 'accepted', 'rejected'
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT), onupdate=datetime.now(MYT))
    
    # Relationships
    user = db.relationship('User', backref='join_requests')
    project = db.relationship('Project', backref=db.backref('join_requests', cascade='all, delete-orphan'))
    
    __table_args__ = (db.UniqueConstraint('user_id', 'project_id', name='unique_user_project_request'),)


class MemberHistory(db.Model):
    """Track member join and leave history for projects"""
    __tablename__ = 'member_history'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # 'joined' or 'left'
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))
    reason = db.Column(db.String(255), nullable=True)  # Optional reason for leaving
    
    # Relationships
    project = db.relationship('Project', backref=db.backref('member_histories', cascade='all, delete-orphan'))
    
    __table_args__ = (db.Index('idx_project_user', 'project_id', 'user_id'),)


class LeaveRequest(db.Model):
    """Team member leave/exit requests with reason"""
    __tablename__ = 'leave_requests'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='pending')  # 'pending', 'approved', 'rejected'
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT), onupdate=datetime.now(MYT))
    approved_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', backref='leave_requests')
    project = db.relationship('Project', backref=db.backref('leave_requests', cascade='all, delete-orphan'))
    
    __table_args__ = (db.UniqueConstraint('user_id', 'project_id', name='unique_user_leave_request'),)


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
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))


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
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT), onupdate=datetime.now(MYT))
    
    # Relationships
    author = db.relationship('User', backref='project_comments')
    project = db.relationship('Project', backref=db.backref('project_comments', cascade='all, delete-orphan'))
    images = db.relationship('ProjectCommentImage', backref='comment', lazy=True, cascade='all, delete-orphan')
    
    __table_args__ = (db.Index('idx_project_comments', 'project_id', 'created_at'),)


class ProjectCommentImage(db.Model):
    """Images attached to project comments"""
    __tablename__ = 'project_comment_images'

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('project_comments.id', ondelete='CASCADE'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)


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
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))

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
    created_at  = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))
    
    images = db.relationship('QuestionCommentImage', backref='comment', lazy=True, cascade='all, delete-orphan')


class QuestionCommentImage(db.Model):
    __tablename__ = 'question_comment_images'

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('question_comments.id', ondelete='CASCADE'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)

# ---------------------------------------------------------------------------
# Community Post Model (For the Timeline Feed) - Upgraded with Q&A features
# ---------------------------------------------------------------------------
class CommunityPost(db.Model):
    __tablename__ = 'community_posts'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='Discussion') 
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))
    
    image_path = db.Column(db.String(255), nullable=True)
    link_url = db.Column(db.String(500), nullable=True)
    attached_project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)
    
    author = db.relationship('User', backref=db.backref('community_posts', lazy=True, cascade='all, delete-orphan'))
    attached_project = db.relationship('Project')
    
    likes = db.relationship('CommunityPostLike', backref='post', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('CommunityPostComment', backref='post', lazy=True, cascade='all, delete-orphan')
    images = db.relationship('CommunityPostImage', backref='post', lazy=True, cascade='all, delete-orphan')
    favorites = db.relationship('CommunityPostFavorite', backref='post', lazy=True, cascade='all, delete-orphan')


class CommunityPostImage(db.Model):
    __tablename__ = 'community_post_images'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id', ondelete='CASCADE'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)


class CommunityPostFavorite(db.Model):
    __tablename__ = 'community_post_favorites'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id', ondelete='CASCADE'), nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT), server_default=db.func.now())
    
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_user_cpost_fav'),)


# --- Likes for Community Posts ---
class CommunityPostLike(db.Model):
    __tablename__ = 'community_post_likes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))
    
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_user_cpost_like'),)


# --- Comments for Community Posts ---
class CommunityPostComment(db.Model):
    __tablename__ = 'community_post_comments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    parent_id = db.Column(db.Integer, db.ForeignKey('community_post_comments.id', ondelete='CASCADE'), nullable=True)
    
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))
    
    author = db.relationship('User')
    images = db.relationship('CommunityPostCommentImage', backref='comment', lazy=True, cascade='all, delete-orphan')


class CommunityPostCommentImage(db.Model):
    __tablename__ = 'community_post_comment_images'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('community_post_comments.id', ondelete='CASCADE'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)

class ProjectUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)  
    status = db.Column(db.String(50), nullable=False)  
    content = db.Column(db.Text, nullable=False)       
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(MYT))
    is_approved = db.Column(db.Boolean, default=False)  

    author = db.relationship('User', backref='project_updates')
    project = db.relationship('Project', backref=db.backref('updates', lazy='dynamic'))
    images = db.relationship('ProjectUpdateImage', backref='update', lazy=True, cascade='all, delete-orphan')  
class ProjectUpdateImage(db.Model):
    __tablename__ = 'project_update_images'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    update_id = db.Column(db.Integer, db.ForeignKey('project_update.id', ondelete='CASCADE'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)


# ---------------------------------------------------------------------------
# Content Moderation Models - Admin Control System
# ---------------------------------------------------------------------------

class ContentReport(db.Model):
    """User reports for inappropriate content - Project, Question, Comment, or Post"""
    __tablename__ = 'content_reports'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Content type: 'project', 'question', 'comment', 'post', 'post_comment'
    content_type = db.Column(db.String(50), nullable=False)
    content_id = db.Column(db.Integer, nullable=False)  # ID of the reported content
    
    # Reason for report: 'spam', 'inappropriate', 'harmful', 'plagiarism', 'other'
    reason = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)  # Detailed explanation
    
    # Status: 'pending', 'approved', 'rejected', 'deleted'
    status = db.Column(db.String(20), nullable=False, default='pending')
    
    # Admin action
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    admin_comment = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT), onupdate=datetime.now(MYT))
    
    # Relationships
    reporter = db.relationship('User', foreign_keys=[reporter_id], backref='reported_contents')
    admin = db.relationship('User', foreign_keys=[admin_id], backref='moderated_reports')
    
    __table_args__ = (db.Index('idx_content_reports', 'content_type', 'content_id', 'status'),)


class AdminLog(db.Model):
    """Log of all admin moderation actions"""
    __tablename__ = 'admin_logs'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Action: 'delete_content', 'suspend_user', 'restore_content', 'approve_report', 'reject_report'
    action = db.Column(db.String(50), nullable=False)
    
    # Target type and ID
    target_type = db.Column(db.String(50), nullable=True)  # 'project', 'question', 'comment', 'post', 'user'
    target_id = db.Column(db.Integer, nullable=True)
    
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))
    
    # Relationships
    admin = db.relationship('User', backref='admin_logs')
    
    __table_args__ = (db.Index('idx_admin_logs', 'admin_id', 'created_at'),)


class SuspendedUser(db.Model):
    """Track suspended users and reasons"""
    __tablename__ = 'suspended_users'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    reason = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)  # False = unsuspended
    
    suspended_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))
    unsuspended_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='suspension')
    admin = db.relationship('User', foreign_keys=[admin_id], backref='user_suspensions')


class ContentFlagKeyword(db.Model):
    """Predefined keywords for automatic content flagging"""
    __tablename__ = 'content_flag_keywords'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    keyword = db.Column(db.String(255), nullable=False, unique=True)
    category = db.Column(db.String(50), nullable=False)  # 'spam', 'inappropriate', 'harmful'
    severity = db.Column(db.Integer, default=1)  # 1-5, higher = more severe
    is_active = db.Column(db.Boolean, default=True)
    added_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now(MYT))