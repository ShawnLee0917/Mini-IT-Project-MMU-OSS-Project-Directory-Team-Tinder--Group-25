from werkzeug import datastructures
import os
import random
import smtplib
import sys
import logging
import json
from email.mime.text import MIMEText
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash, jsonify, session
from .models import Question, QuestionComment, QuestionFavorite, QuestionLike, db, User, Skill, Badge, Comment, Project, ProjectImage, Suggestion, ProjectComment, CommentLabel, QuestionCommentImage, QuestionImage, JoinRequest, LeaveRequest, MemberHistory, ProjectCommentImage, UserSettings, ProjectMember, CommunityPostComment, CommunityPost, CommunityPostLike, CommunityPostImage, CommunityPostFavorite, CommunityPostCommentImage, ProjectViewLog, ProjectUpdate, ContentReport, AdminLog, SuspendedUser, ContentFlagKeyword, ProjectStar
from datetime import datetime, timezone, timedelta

views = Blueprint('views', __name__)

# =====================================================================
# ─── BANNED KEYWORDS AUTOMATIC FILTERING SYSTEM ───
# =====================================================================
BANNED_KEYWORDS = [
    'scam', 'spam', 'casino', 'gamble', 'betting',
    'buy followers', 'homework help', 'advertisement', 'hack'
]

def contains_banned_keywords(text_to_check):
    """
    Helper function to check if the text contains any blacklisted words.
    Returns the banned word if found, otherwise returns None.
    """
    if not text_to_check:
        return None
    
    # Convert text to lowercase to prevent bypassing with 'ScaM' or 'SCAM'
    lower_text = str(text_to_check).lower()
    for word in BANNED_KEYWORDS:
        if word.lower() in lower_text:
            return word
    return None

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def require_login():
    if 'user_email' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    return None

def get_current_user():
    email = session.get('user_email', 'student@mmu.edu.my')
    user = User.query.filter_by(email=email).first()
    return user

def parse_interests(interests_str):
    """Parse interests from JSON or comma-separated format"""
    if not interests_str:
        return {'dev_interests': [], 'lang_interests': []}
    
    try:
        # Try parsing as JSON first
        return json.loads(interests_str)
    except:
        # Fallback to comma-separated format (legacy)
        all_interests = [i.strip() for i in interests_str.split(',') if i.strip()]
        return {'dev_interests': all_interests, 'lang_interests': []}


# =====================================================================
# Content Moderation & Admin Functions
# =====================================================================

@views.route('/api/admin/delete-content', methods=['POST'])
def api_admin_delete_content():
    """Admin panel: seamlessly handles soft-deletion for projects or hard-deletion for text elements."""
    error_resp = require_admin()
    if error_resp:
        return error_resp

    data = request.get_json(silent=True) or {}
    content_type = data.get('type')  # 'project', 'comment', 'post', 'post_comment'
    content_id = data.get('id')
    report_id = data.get('report_id')

    if not content_type or not content_id:
        return jsonify({'error': 'Missing type or ID.'}), 400

    try:
        target = None
        details_msg = ""

        if content_type == 'project':
            target = Project.query.get(content_id)
            if target:
                # 🌟 SOFT DELETE IMPLEMENTATION: Change status to Suspended instead of db.session.delete
                target.status = 'Suspended'
                details_msg = f"Soft Deleted/Suspended Project: {target.project_name or content_id}"

        elif content_type == 'comment':
            target = ProjectComment.query.get(content_id)
            if not target:
                target = Comment.query.get(content_id)
            if target:
                details_msg = f"Deleted Comment ID {content_id}"
                db.session.delete(target)

        elif content_type == 'post':
            target = CommunityPost.query.get(content_id)
            if target:
                details_msg = f"Deleted Post ID {content_id}"
                db.session.delete(target)

        elif content_type == 'post_comment':
            target = CommunityPostComment.query.get(content_id)
            if target:
                details_msg = f"Deleted Post Comment ID {content_id}"
                db.session.delete(target)

        else:
            return jsonify({'error': 'Invalid content type.'}), 400

        if target:
            if report_id:
                report = ContentReport.query.get(report_id)
                if report:
                    # 🌟 FIX: Change status to 'approved' so project_page history lookups can match it perfectly!
                    report.status = 'approved'
                    report.admin_id = get_current_user().id

            log = AdminLog()
            log.admin_id = get_current_user().id
            log.action = 'delete_content'
            log.target_type = content_type
            log.target_id = int(content_id)
            log.details = f"[Admin Action] {details_msg}"
            db.session.add(log)

            db.session.commit()
            return jsonify({'success': True, 'message': f'{content_type.capitalize()} updated successfully.'})
        else:
            return jsonify({'error': 'Content not found.'}), 404

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Database operational failure: {str(e)}'}), 500
    
def check_admin_permission():
    """Verify if current user is admin"""
    if 'user_email' not in session:
        return False, None
    user = get_current_user()
    if not user or not user.is_admin:
        return False, None
    return True, user


def detect_inappropriate_content(text):
    """Scan text for inappropriate keywords - returns list of flagged keywords"""
    if not text:
        return []
    
    flagged_keywords = ContentFlagKeyword.query.filter_by(is_active=True).all()
    flagged = []
    
    text_lower = text.lower()
    for keyword_obj in flagged_keywords:
        if keyword_obj.keyword.lower() in text_lower:
            flagged.append({
                'keyword': keyword_obj.keyword,
                'category': keyword_obj.category,
                'severity': keyword_obj.severity
            })
    
    return flagged


def auto_report_content(content_type, content_id, reason='auto_flagged'):
    """Automatically create a content report for flagged content"""
    # Check if report already exists
    existing = ContentReport.query.filter_by(
        content_type=content_type,
        content_id=content_id,
        status='pending'
    ).first()
    
    if not existing:
        report = ContentReport()
        report.reporter_id = 1  # System as reporter
        report.content_type = content_type
        report.content_id = content_id
        report.reason = reason
        report.status = 'pending'
        db.session.add(report)
        db.session.commit()
        return True
    return False


def _enrich_pending_reports(reports):
    """Build display metadata for pending content reports."""
    items = []
    type_labels = {
        'project': 'Project',
        'comment': 'Comment',
        'question': 'Question',
        'post': 'Community Post',
        'post_comment': 'Post Comment',
    }

    for report in reports:
        item = {
            'id': report.id,
            'content_type': report.content_type,
            'content_id': report.content_id,
            'reason': report.reason,
            'description': report.description or '',
            'reporter_name': report.reporter.name if report.reporter else 'System',
            'created_at': report.created_at,
            'type_label': type_labels.get(report.content_type, report.content_type.title()),
            'target_label': f'{type_labels.get(report.content_type, report.content_type)} #{report.content_id}',
            'target_link': '#',
            'target_preview': '',
        }

        if report.content_type == 'project':
            project = Project.query.get(report.content_id)
            if project:
                item['target_label'] = project.project_name
                item['target_link'] = f'/project/{report.content_id}'
                item['target_preview'] = (project.description or '')[:120]
            else:
                item['target_preview'] = 'Content may have been removed already.'

        elif report.content_type == 'comment':
            comment = ProjectComment.query.get(report.content_id)
            if comment:
                item['target_label'] = f'Comment on {comment.project.project_name if comment.project else "Project"}'
                item['target_link'] = f'/project/{comment.project_id}'
                item['target_preview'] = (comment.content or '')[:120]
            else:
                item['target_preview'] = 'Comment may have been removed already.'

        elif report.content_type == 'question':
            question = Question.query.get(report.content_id)
            if question:
                item['target_label'] = question.title
                item['target_link'] = f'/qna/{report.content_id}'
                item['target_preview'] = (question.body or '')[:120]

        elif report.content_type == 'post':
            post = CommunityPost.query.get(report.content_id)
            if post:
                item['target_label'] = f'Community Post #{post.id}'
                item['target_link'] = '/trending'
                item['target_preview'] = (post.content or '')[:120]

        elif report.content_type == 'post_comment':
            post_comment = CommunityPostComment.query.get(report.content_id)
            if post_comment:
                item['target_label'] = f'Comment on Post #{post_comment.post_id}'
                item['target_link'] = '/trending'
                item['target_preview'] = (post_comment.content or '')[:120]

        items.append(item)
    return items

    # =====================================================================
# ─── ADMIN BADGE MANAGEMENT APIs ───
# =====================================================================

@views.route('/api/admin/users/badges', methods=['GET'])
def admin_get_user_badges():
    """Admin endpoint to view all users and their badges"""
    is_admin, _ = check_admin_permission()
    if not is_admin: 
        return jsonify({'error': 'Admin permission required'}), 403
        
    users = User.query.all()
    user_data = []
    for u in users:
        user_data.append({
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'badges': [{'id': b.id, 'name': b.badge} for b in u.badges]
        })
    return jsonify(user_data)

@views.route('/api/admin/users/<int:user_id>/badge', methods=['POST'])
def admin_award_badge(user_id):
    """Admin endpoint to award a badge to a specific user"""
    is_admin, admin_user = check_admin_permission()
    if not is_admin:
        return jsonify({'error': 'Admin permission required'}), 403
    
    data = request.get_json(silent=True) or {}
    badge_name = data.get('badge_name', '').strip()
    
    if not badge_name:
        return jsonify({'error': 'Badge name is required'}), 400
        
    # Check if user exists
    user = User.query.get_or_404(user_id)
        
    # Check if they already have this exact badge
    existing = Badge.query.filter_by(user_id=user_id, badge=badge_name).first()
    if existing:
        return jsonify({'error': f'{user.name} already has the {badge_name} badge.'}), 409
        
    new_badge = Badge(user_id=user_id, badge=badge_name)
    
    # Log the action
    log = AdminLog(
        admin_id=admin_user.id, 
        action='award_badge', 
        target_type='user', 
        target_id=user_id, 
        details=f"Awarded badge '{badge_name}' to {user.name}"
    )
    db.session.add(log)
    db.session.add(new_badge)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Badge awarded successfully!', 'badge_id': new_badge.id})

@views.route('/api/admin/badges/<int:badge_id>', methods=['DELETE'])
def admin_delete_badge(badge_id):
    """Admin endpoint to remove a badge from a user"""
    is_admin, admin_user = check_admin_permission()
    if not is_admin:
        return jsonify({'error': 'Admin permission required'}), 403
        
    badge = Badge.query.get_or_404(badge_id)
    
    # Log the action
    log = AdminLog(
        admin_id=admin_user.id, 
        action='remove_badge', 
        target_type='user', 
        target_id=badge.user_id, 
        details=f"Removed badge '{badge.badge}' from User #{badge.user_id}"
    )
    
    db.session.add(log)
    db.session.delete(badge)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Badge removed successfully'})


# =============================================================
# BADGE HELPER FUNCTIONS
# =============================================================

# Map language names (lowercase) → badge name
LANG_BADGE_MAP = {
    'python':        'Python Expert',
    'javascript':    'JavaScript Expert',
    'js':            'JavaScript Expert',
    'html':          'HTML Expert',
    'css':           'CSS Expert',
    'react':         'React Expert',
    'php':           'PHP Expert',
    'go':            'Go Expert',
    'golang':        'Go Expert',
    'c++':           'C++ Expert',
    'cpp':           'C++ Expert',
    'dart':          'Dart Expert',
    'rust':          'Rust Expert',
    'typescript':    'TypeScript Expert',
    'ts':            'TypeScript Expert',
}

def _award_badge(user_id, badge_name):
    """Award a badge if the user doesn't already have it. Caller must commit."""
    exists = Badge.query.filter_by(user_id=user_id, badge=badge_name).first()
    if not exists:
        db.session.add(Badge(user_id=user_id, badge=badge_name))

def _revoke_badge(user_id, badge_name):
    """Remove a badge if the user has it. Caller must commit."""
    badge = Badge.query.filter_by(user_id=user_id, badge=badge_name).first()
    if badge:
        db.session.delete(badge)

def _get_lang_badges_for_project(languages_str):
    """Return a set of badge names earned from a project's language string."""
    if not languages_str:
        return set()
    badges = set()
    for lang in languages_str.split(','):
        badge = LANG_BADGE_MAP.get(lang.strip().lower())
        if badge:
            badges.add(badge)
    return badges

def sync_lang_badges(user_id):
    """
    Recalculate which language badges the user should have based on ALL
    their current projects, then award/revoke accordingly.
    Called after listing, deleting, or editing a project.
    """
    all_projects = Project.query.filter_by(user_id=user_id).all()

    # Collect every badge still earned across remaining projects
    earned = set()
    for p in all_projects:
        earned |= _get_lang_badges_for_project(p.languages)

    # All possible language badges
    all_lang_badges = set(b for b in LANG_BADGE_MAP.values() if b)

    # Award any newly earned ones
    for badge_name in earned:
        _award_badge(user_id, badge_name)

    # Revoke any that are no longer earned
    for badge_name in all_lang_badges - earned:
        _revoke_badge(user_id, badge_name)

def sync_trending_badges(user_id):
    """
    Recalculate Hottest Project / Trending Project badges for a user
    based on whether any of their projects currently appear in the top 10.
    Called after deleting a project.
    """
    from datetime import datetime, timezone, timedelta

    all_projects = Project.query.filter(Project.status != 'Archived').all()
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    all_time_scores = {}
    trending_scores = {}

    for p in all_projects:
        comment_count = ProjectComment.query.filter_by(project_id=p.id).count()
        attached_posts = CommunityPost.query.filter_by(attached_project_id=p.id).all()
        post_ids = [post.id for post in attached_posts]

        post_like_count = CommunityPostLike.query.filter(
            CommunityPostLike.post_id.in_(post_ids)).count() if post_ids else 0
        post_save_count = CommunityPostFavorite.query.filter(
            CommunityPostFavorite.post_id.in_(post_ids)).count() if post_ids else 0
        views = p.views or 0

        total_score = (views * 1) + (post_like_count * 5) + (comment_count * 10) + (post_save_count * 20)
        all_time_scores[p.id] = (p.user_id, total_score)

        recent_comments = ProjectComment.query.filter(
            ProjectComment.project_id == p.id,
            ProjectComment.created_at >= seven_days_ago).count()
        recent_views = ProjectViewLog.query.filter(
            ProjectViewLog.project_id == p.id,
            ProjectViewLog.created_at >= seven_days_ago).count()
        recent_likes = CommunityPostLike.query.filter(
            CommunityPostLike.post_id.in_(post_ids),
            CommunityPostLike.created_at >= seven_days_ago).count() if post_ids else 0
        recent_saves = CommunityPostFavorite.query.filter(
            CommunityPostFavorite.post_id.in_(post_ids),
            CommunityPostFavorite.created_at >= seven_days_ago).count() if post_ids else 0

        t_score = (recent_views * 1) + (recent_likes * 5) + (recent_comments * 10) + (recent_saves * 20)
        if t_score > 0:
            trending_scores[p.id] = (p.user_id, t_score)

    top_all_time_owners = {v[0] for _, v in sorted(
        all_time_scores.items(), key=lambda x: x[1][1], reverse=True)[:3]}
    top_trending_owners = {v[0] for _, v in sorted(
        trending_scores.items(), key=lambda x: x[1][1], reverse=True)[:3]}

    if user_id in top_all_time_owners:
        _award_badge(user_id, 'Hottest Project')
    else:
        _revoke_badge(user_id, 'Hottest Project')

    if user_id in top_trending_owners:
        _award_badge(user_id, 'Trending Project')
    else:
        _revoke_badge(user_id, 'Trending Project')


@views.route('/api/admin/reports', methods=['GET'])
def api_get_reports():
    """Get all content reports (paginated)"""
    is_admin, _ = check_admin_permission()
    if not is_admin:
        return jsonify({'error': 'Admin permission required'}), 403
    
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'pending')  # pending, approved, rejected, deleted
    
    query = ContentReport.query
    if status != 'all':
        query = query.filter_by(status=status)
    
    reports = query.order_by(ContentReport.created_at.desc()).paginate(
        page=page, per_page=20
    )
    
    reports_data = []
    for report in reports.items:
        reports_data.append({
            'id': report.id,
            'reporter_name': report.reporter.name if report.reporter else 'System',
            'content_type': report.content_type,
            'content_id': report.content_id,
            'reason': report.reason,
            'description': report.description,
            'status': report.status,
            'created_at': report.created_at.isoformat(),
            'updated_at': report.updated_at.isoformat(),
        })
    
    return jsonify({
        'reports': reports_data,
        'total': reports.total,
        'pages': reports.pages,
        'current_page': page
    })


@views.route('/api/report-content', methods=['POST'])
def api_report_content():
    """User reports inappropriate content"""
    err = require_login()
    if err:
        return err
    
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    
    content_type = data.get('content_type')  # 'project', 'question', 'comment', 'post', 'post_comment'
    raw_id = data.get('content_id')
    content_id = int(raw_id) if raw_id is not None else None
    reason = data.get('reason')  # 'spam', 'inappropriate', 'harmful', 'plagiarism', 'other'
    description = data.get('description', '')
    
    if not all([content_type, content_id, reason]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check if user already reported this
    existing = ContentReport.query.filter_by(
        reporter_id=user.id,
        content_type=content_type,
        content_id=content_id,
        status='pending'
    ).first()
    
    if existing:
        return jsonify({'error': 'You have already reported this content'}), 409
    
    report = ContentReport()
    report.reporter_id = user.id
    report.content_type = content_type
    report.content_id = content_id
    report.reason = reason
    report.description = description
    report.status = 'pending'  # 👈 【核心修复】：显式指定状态为 pending，确保后台能查到
    
    db.session.add(report)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Report submitted. Thank you for helping keep our community safe!',
        'report_id': report.id
    })


@views.route('/api/admin/approve-report/<int:report_id>', methods=['POST'])
def api_approve_report(report_id):
    """Admin approves a report and deletes the content"""
    is_admin, admin_user = check_admin_permission()
    if not is_admin:
        return jsonify({'error': 'Admin permission required'}), 403
    
    report = ContentReport.query.get_or_404(report_id)
    admin_comment = (request.get_json(silent=True) or {}).get('comment', '')
    
    try:
        # Delete the reported content based on type
        if report.content_type == 'project':
            content = Project.query.get(report.content_id)
            if content:
                db.session.delete(content)
                
        elif report.content_type == 'question':
            content = Question.query.get(report.content_id)
            if content:
                db.session.delete(content)
                
        elif report.content_type == 'comment':
            content = ProjectComment.query.get(report.content_id)
            if content:
                db.session.delete(content)
                
        elif report.content_type == 'post':
            content = CommunityPost.query.get(report.content_id)
            if content:
                db.session.delete(content)
                
        elif report.content_type == 'post_comment':
            content = CommunityPostComment.query.get(report.content_id)
            if content:
                db.session.delete(content)
        
        # Update report status
        report.status = 'deleted'
        report.admin_id = admin_user.id
        report.admin_comment = admin_comment
        
        # Log admin action
        log = AdminLog()
        log.admin_id = admin_user.id
        log.action = 'delete_content'
        log.target_type = report.content_type
        log.target_id = report.content_id
        log.details = f"Reason: {report.reason}. {admin_comment}"
        db.session.add(log)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Content deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error deleting content: {str(e)}'}), 500


@views.route('/api/admin/reject-report/<int:report_id>', methods=['POST'])
def api_reject_report(report_id):
    """Admin rejects a report (content is not deleted)"""
    is_admin, admin_user = check_admin_permission()
    if not is_admin:
        return jsonify({'error': 'Admin permission required'}), 403
    
    report = ContentReport.query.get_or_404(report_id)
    admin_comment = (request.get_json(silent=True) or {}).get('comment', '')
    
    report.status = 'rejected'
    report.admin_id = admin_user.id
    report.admin_comment = admin_comment
    
    log = AdminLog()
    log.admin_id = admin_user.id
    log.action = 'reject_report'
    log.target_type = report.content_type
    log.target_id = report.content_id
    log.details = f"Rejected report: {report.reason}. {admin_comment}"
    db.session.add(log)
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Report rejected'})


@views.route('/api/admin/suspend-user/<int:user_id>', methods=['POST'])
def api_suspend_user(user_id):
    """Admin suspends a user"""
    is_admin, admin_user = check_admin_permission()
    if not is_admin:
        return jsonify({'error': 'Admin permission required'}), 403
    
    user = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}
    reason = data.get('reason', 'Violation of community guidelines')
    
    # Check if already suspended
    existing = SuspendedUser.query.filter_by(user_id=user_id, is_active=True).first()
    if existing:
        return jsonify({'error': 'User is already suspended'}), 409
    
    suspension = SuspendedUser()
    suspension.user_id = user_id
    suspension.admin_id = admin_user.id
    suspension.reason = reason
    
    log = AdminLog()
    log.admin_id = admin_user.id
    log.action = 'suspend_user'
    log.target_type = 'user'
    log.target_id = user_id
    log.details = reason
    db.session.add(log)
    
    db.session.add(suspension)
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'User {user.email} has been suspended'})


@views.route('/api/admin/unsuspend-user/<int:user_id>', methods=['POST'])
def api_unsuspend_user(user_id):
    """Admin unsuspends a user"""
    is_admin, admin_user = check_admin_permission()
    if not is_admin:
        return jsonify({'error': 'Admin permission required'}), 403
    
    suspension = SuspendedUser.query.filter_by(user_id=user_id, is_active=True).first()
    if not suspension:
        return jsonify({'error': 'User is not suspended'}), 404
    
    suspension.is_active = False
    suspension.unsuspended_at = datetime.utcnow()
    
    log = AdminLog()
    log.admin_id = admin_user.id
    log.action = 'unsuspend_user'
    log.target_type = 'user'
    log.target_id = user_id
    log.details = 'User unsuspended'
    db.session.add(log)
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'User unsuspended'})


@views.route('/api/admin/keywords', methods=['GET'])
def api_get_keywords():
    """Get all content flag keywords"""
    is_admin, _ = check_admin_permission()
    if not is_admin:
        return jsonify({'error': 'Admin permission required'}), 403
    
    keywords = ContentFlagKeyword.query.all()
    keywords_data = [{
        'id': k.id,
        'keyword': k.keyword,
        'category': k.category,
        'severity': k.severity,
        'is_active': k.is_active
    } for k in keywords]
    
    return jsonify({'keywords': keywords_data})


@views.route('/api/admin/add-keyword', methods=['POST'])
def api_add_keyword():
    """Admin adds a flagging keyword"""
    is_admin, admin_user = check_admin_permission()
    if not is_admin:
        return jsonify({'error': 'Admin permission required'}), 403
    
    data = request.get_json(silent=True) or {}
    keyword = data.get('keyword', '').strip()
    category = data.get('category')  # 'spam', 'inappropriate', 'harmful'
    severity = data.get('severity', 1)
    
    if not keyword or not category:
        return jsonify({'error': 'Missing required fields'}), 400
    
    existing = ContentFlagKeyword.query.filter_by(keyword=keyword).first()
    if existing:
        return jsonify({'error': 'Keyword already exists'}), 409
    
    keyword_obj = ContentFlagKeyword()
    keyword_obj.keyword = keyword
    keyword_obj.category = category
    keyword_obj.severity = severity
    keyword_obj.added_by = admin_user.id
    
    db.session.add(keyword_obj)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Keyword added'})


@views.route('/api/admin/delete-keyword/<int:keyword_id>', methods=['DELETE'])
def api_delete_keyword(keyword_id):
    """Admin deletes a flagging keyword"""
    is_admin, admin_user = check_admin_permission()
    if not is_admin:
        return jsonify({'error': 'Admin permission required'}), 403
    
    keyword = ContentFlagKeyword.query.get_or_404(keyword_id)
    keyword.is_active = False
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Keyword disabled'})


@views.route('/api/admin/logs', methods=['GET'])
def api_get_admin_logs():
    """Get admin action logs (paginated)"""
    is_admin, _ = check_admin_permission()
    if not is_admin:
        return jsonify({'error': 'Admin permission required'}), 403
    
    page = request.args.get('page', 1, type=int)
    action_type = request.args.get('action', None)
    
    query = AdminLog.query
    if action_type:
        query = query.filter_by(action=action_type)
    
    logs = query.order_by(AdminLog.created_at.desc()).paginate(
        page=page, per_page=50
    )
    
    logs_data = []
    for log in logs.items:
        logs_data.append({
            'id': log.id,
            'admin_name': log.admin.name if log.admin else 'System',
            'action': log.action,
            'target_type': log.target_type,
            'target_id': log.target_id,
            'details': log.details,
            'created_at': log.created_at.isoformat()
        })
    
    return jsonify({
        'logs': logs_data,
        'total': logs.total,
        'pages': logs.pages,
        'current_page': page
    })


@views.route('/api/admin/dismiss-report', methods=['POST'])
def api_admin_dismiss_report():
    """管理面板：忽略/驳回举报记录"""
    
    # 1. 权限检查：确保函数名和你的验证逻辑一致
    is_admin, user = check_admin_permission()
    if not is_admin:
        return jsonify({'error': 'Unauthorized access.'}), 403

    # 2. 解析前端传来的 JSON
    data = request.get_json(silent=True) or {}
    report_id = data.get('report_id')

    if not report_id:
        return jsonify({'error': 'Missing report ID.'}), 400

    try:
        # 3. 查找举报记录（改用兼容性最强的 filter_by 方式）
        # 请确保 ContentReport 名字与你的 models.py 中完全一致
        report = ContentReport.query.filter_by(id=int(report_id)).first()
        
        if not report:
            return jsonify({'error': f'Report #{report_id} not found in database.'}), 404

        # 4. 更新状态
        report.status = 'resolved' 
        
        # 5. 安全地记录审计日志（将其完全隔离，防止因没有表或少字段导致整个接口崩溃）
        try:
            log = AdminLog()
            # 动态获取当前管理员 ID，如果没有就安全赋一个默认值 1
            log.admin_id = user.id if (user and hasattr(user, 'id')) else 1
            log.action = 'dismiss_report'
            log.target_type = 'report'
            log.target_id = int(report_id)
            log.details = f"[Admin Action] Dismissed report #{report_id}"
            db.session.add(log)
        except Exception as log_err:
            # 如果是 AdminLog 报错，打印出来但不要 raise，让主逻辑继续走
            print(f"安全跳过日志错误 (AdminLog Save Failed): {str(log_err)}")

        # 6. 提交到数据库
        db.session.commit()
        return jsonify({'success': True, 'message': 'Report dismissed successfully.'}), 200

    except Exception as e:
        db.session.rollback()
        # 核心调试：如果还报错，这行会在你运行 Flask 的 VS Code 终端里打印出真正的 Python 报错死因
        print(f"\n💥 [CRITICAL ERROR] Dismiss API crashed due to: {str(e)}\n")
        return jsonify({'error': f'Database failure: {str(e)}'}), 500
    
# --- ADDED: Auto-Email Sending Function ---
# Reference: Python smtplib - https://docs.python.org/3/library/smtplib.html
def send_otp_email(receiver_email, otp_code):
    # =====================================================================
    # ⚠️ IMPORTANT: Replace with your real Gmail and 16-digit Google App Password ⚠️
    # =====================================================================
    sender_email = "kohkonghao4@gmail.com" 
    sender_password = "wlas kitq zrpa qpbb"

    message = f"\n{'='*70}\n[DEVELOPMENT MODE] OTP CODE FOR: {receiver_email}\n{'='*70}\nOTP CODE: {otp_code}\nVerification URL: http://127.0.0.1:5000/verify\nDirect OTP URL: http://127.0.0.1:5000/test_otp/{receiver_email}\n{'='*70}\n"
    
    print(message, flush=True)
    sys.stdout.write(message)
    sys.stdout.flush()
    sys.stderr.write(message)
    sys.stderr.flush()
    
    logging.info(message)
    current_app.logger.info(message)

    if sender_email == "your_email@gmail.com" or sender_password == "your_16_digit_app_password":
        print("\n WARNING: Email credentials not set! Using development mode. Check the terminal for the OTP.")
        return True  # Allow registration for testing

    msg = MIMEText(f"Welcome to MMU OSSD!\n\nYour 6-digit verification code is: {otp_code}\n\nThis code will expire in 15 minutes.")
    msg['Subject'] = 'MMU OSSD Verification Code'
    msg['From'] = sender_email
    msg['To'] = receiver_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        print(f" OTP email automatically sent to {receiver_email}")
        return True
    except Exception as e:
        print(f" Email Automation Error: {e}")
        return False

@views.route('/')
@views.route('/home')
def home():
    if 'user_email' not in session:
        return redirect(url_for('views.login'))
    return render_template("Navigation.html")

@views.route('/login')
def login():
    return render_template("login.html")

@views.route('/register')
def register():
    return render_template("register.html")

# --- ADDED: Verify Page Route ---
@views.route('/verify')
def verify_page():
    return render_template("otp.html")

# --- ADDED: New Endpoint for verifying the OTP ---
# Reference: Flask session management - https://flask.palletsprojects.com/en/stable/quickstart/#sessions
@views.route('/api/verify_otp', methods=['POST'])
def api_verify_otp():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    otp = data.get('otp', '').strip()

    user = User.query.filter_by(email=email).first()

    if user and user.otp == otp:
        user.is_verified = True
        user.otp = None  # Clear OTP after successful use
        db.session.commit()
        return jsonify({'success': True, 'message': 'Account verified!'})
        
    return jsonify({'error': 'Invalid code. Please check and try again.'}), 401

@views.route('/api/resend_otp', methods=['POST'])
def api_resend_otp():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found.'}), 404
    if user.is_verified:
        return jsonify({'error': 'Account already verified.'}), 400
    
    otp_code = str(random.randint(100000, 999999))
    user.otp = otp_code
    db.session.commit()
    
    send_otp_email(email, otp_code)
    print(f"[RESEND OTP] {email} → {otp_code}")
    return jsonify({'success': True, 'message': 'OTP resent.'})

# --- ADDED: Simple test route to display OTP ---
@views.route('/test_otp/<email>')
def test_otp(email):
    user = User.query.filter_by(email=email).first()
    if not user:
        return f"User {email} not found"
    
    if user.is_verified:
        return f"User {email} is already verified"
    
    if not user.otp:
        return f"No OTP available for {email}"
    
    return f"""
    <h1>OTP for {email}</h1>
    <h2 style="color: red; font-size: 48px;">{user.otp}</h2>
    <p>Use this code at: <a href="/verify">http://127.0.0.1:5000/verify</a></p>
    """

# ── Forgot / Reset Password Pages ──────────────────────────────────────────
@views.route('/forgot-password')
def forgot_password():
    return render_template('forgot_password.html')

@views.route('/reset-password')
def reset_password():
    return render_template('reset_password.html')

# ── API: Request password reset OTP ─────────────────────────────────────────
# Reference: Python smtplib - https://docs.python.org/3/library/smtplib.html
@views.route('/api/forgot-password', methods=['POST'])
def api_forgot_password():
    data  = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': 'Email is required'}), 400
    if not (email.endswith('@mmu.edu.my') or email.endswith('@student.mmu.edu.my')):
        return jsonify({'error': 'Only MMU email addresses are allowed'}), 400

    user = User.query.filter_by(email=email).first()
    # Always return success even if email not found (security best practice)
    if user and user.is_verified:
        otp_code  = f'{random.randint(0, 999999):06d}'
        user.otp  = otp_code
        db.session.commit()
        send_otp_email(email, otp_code)

    return jsonify({'success': True, 'message': 'If that email is registered, a reset code has been sent.'})

# ── API: Verify reset OTP (without changing password yet) ───────────────────
@views.route('/api/verify-reset-otp', methods=['POST'])
def api_verify_reset_otp():
    data  = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    otp   = data.get('otp', '').strip()

    user = User.query.filter_by(email=email).first()
    if not user or not user.otp or user.otp != otp:
        return jsonify({'error': 'Invalid or expired reset code. Please request a new one.'}), 401

    return jsonify({'success': True, 'message': 'Code verified'})

# ── API: Set new password after OTP verified ─────────────────────────────────
@views.route('/api/reset-password', methods=['POST'])
def api_reset_password():
    from werkzeug.security import generate_password_hash
    data         = request.get_json(silent=True) or {}
    email        = data.get('email', '').strip().lower()
    otp          = data.get('otp', '').strip()
    new_password = data.get('new_password', '')

    if not email or not otp or not new_password:
        return jsonify({'error': 'All fields are required'}), 400
    if len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.otp or user.otp != otp:
        return jsonify({'error': 'Invalid or expired reset code. Please start over.'}), 401

    user.password_hash = generate_password_hash(new_password)
    user.otp           = None   # Invalidate the OTP after use
    db.session.commit()

    return jsonify({'success': True, 'message': 'Password reset successfully!'})

# ── API: Dev helper — retrieve reset OTP (same as get_otp) ──────────────────
@views.route('/api/get_reset_otp', methods=['POST'])
def api_get_reset_otp():
    data  = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    user  = User.query.filter_by(email=email).first()
    if not user or not user.otp:
        return jsonify({'error': 'No reset code found for this email. Please request one first.'}), 404
    return jsonify({'otp': user.otp})

@views.route('/search')
def search():
    all_projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template("Search.html", projects=all_projects)

@views.route('/suggestions')
def suggestions():
    if 'user_email' not in session:
        return redirect(url_for('views.login'))
    return render_template("AI_Suggestions.html")

@views.route('/my_projects')
def my_projects():
    current_user = get_current_user()
    
    if not current_user or 'user_email' not in session:
        flash("Please login to view your projects.", "error")
        return redirect(url_for('views.login'))

    own_projects = Project.query.filter(
        Project.user_id == current_user.id,
        Project.status != 'Suspended'
    ).order_by(Project.created_at.desc()).all()
    
    memberships = current_user.project_memberships.all()
    joined_projects = [
        membership.project for membership in memberships 
        if membership.project.status != 'Suspended'
    ]
    
    # Update current user's last_seen timestamp
    current_user.last_seen = datetime.now(timezone.utc)
    db.session.commit()

    return render_template("My_Projects.html", own_projects=own_projects, joined_projects=joined_projects)

@views.route('/profile')
def profile():
    return render_template("Profile.html")

@views.route('/user/<int:user_id>')
def view_user_profile(user_id):
    """View another user's profile"""
    user = User.query.get_or_404(user_id)
    current_user = get_current_user()
    
    # Check privacy settings
    settings = user.settings
    is_private = settings and settings.profile_visibility == 'private'
    
    # Check if current user is authorized to view this profile
    show_private_message = False
    if is_private:
        # Only allow viewing if it's the user's own profile
        if not current_user or current_user.id != user.id:
            show_private_message = True
    
    return render_template("User_Profile.html", profile_user=user, current_user=current_user, show_private_message=show_private_message)

@views.route('/qna/delete/<int:question_id>')
def qna_delete_page(question_id):
    """Display delete confirmation page for a question"""
    q = Question.query.get_or_404(question_id)
    user = get_current_user()
    
    # Check if user is the owner
    if not user or q.user_id != user.id:
        flash("You don't have permission to delete this question.", "error")
        return redirect(url_for('views.qna_page'))
    
    return render_template("QnA_Delete.html", question=q)


@views.route('/qna')
def qna_page():
    return render_template('QnA.html')

@views.route('/project/<int:project_id>')
def project_page(project_id):
    """Renders the standard student project page or historical moderation notices if soft-deleted."""
    project = Project.query.get_or_404(project_id)
    current_user = get_current_user()
    
    # 🌟 HISTORICAL LOCK: If the project is soft-deleted/suspended, intercept and display moderation reason
    if project.status == 'Suspended':
        # Admin can still view the project normally
        if current_user and getattr(current_user, 'is_admin', False):
            pass  # Admin sees the project as normal
        else:
            # Non-admin gets a 404
            from flask import abort
            abort(404)

    # ==========================================
    # Keep your original analytics & logic completely untouched below
    # ==========================================
    viewed_projects = session.get('viewed_projects', {})
    now = datetime.now(timezone.utc)
    
    COOLDOWN_HOURS = 24
    should_increment = True
    project_id_str = str(project_id)
    
    if project_id_str in viewed_projects:
        try:
            last_viewed_str = viewed_projects[project_id_str]
            last_viewed_time = datetime.fromisoformat(last_viewed_str)
            
            if last_viewed_time.tzinfo is None:
                last_viewed_time = last_viewed_time.replace(tzinfo=timezone.utc)
                
            if now - last_viewed_time < timedelta(hours=COOLDOWN_HOURS):
                should_increment = False
        except (ValueError, TypeError):
            pass
            
    if should_increment:
        if project.views is None:
            project.views = 0
        project.views += 1

        view_log = ProjectViewLog(
            project_id=project.id,
            user_id=current_user.id if current_user else None 
        )
        db.session.add(view_log)
        
        viewed_projects[project_id_str] = now.isoformat()
        session['viewed_projects'] = viewed_projects
        session.modified = True 
        
        db.session.commit()

    current_user_role = None
    is_invited = False
    invitation_id = None
    
    if current_user:
        if project.user_id == current_user.id:
            current_user_role = 'owner'
        else:
            member_record = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first()
            if member_record:
                current_user_role = member_record.role
            else:
                invite = JoinRequest.query.filter_by(project_id=project.id, user_id=current_user.id, status='invited').first()
                if invite:
                    is_invited = True
                    invitation_id = invite.id

    total_stars = ProjectStar.query.filter_by(project_id=project.id).count()
    
    user_has_starred = False
    if current_user:
        star_record = ProjectStar.query.filter_by(user_id=current_user.id, project_id=project.id).first()
        if star_record:
            user_has_starred = True

    return render_template(
        "Project_Page.html", 
        project=project, 
        current_user=current_user, 
        current_user_role=current_user_role,
        is_invited=is_invited,
        invitation_id=invitation_id,
        total_stars=total_stars,          
        user_has_starred=user_has_starred  
    )
@views.route('/upload-success')
def upload_success():
    return render_template("Upload_Success.html")

@views.route('/list_project', methods=['GET', 'POST'])
def list_project():
    if request.method == 'POST':
        name = request.form.get('project_name')
        repo = request.form.get('repo_url')
        langs = request.form.get('languages')
        roles = request.form.get('roles_needed')
        desc = request.form.get('description')
        
        current_user = get_current_user()
        if not current_user:
            flash("Please login first!", "error")
            return redirect(url_for('views.home'))

        # =============================================================
        # UPGRADED AUTOMATED SECURITY GUARDRAIL WITH AUDIT LOGGING
        # =============================================================
        # 1. First layer check using your internal active database keywords
        flagged_in_name = detect_inappropriate_content(name)
        flagged_in_desc = detect_inappropriate_content(desc)
        all_flags = flagged_in_name + flagged_in_desc

        # 2. Fallback local strict policy check for immediate demo stability
        scan_payload = f"{name} {desc}".lower()
        hardcoded_keywords = [
            'assignment-help', 'academic-cheating', 'earn-cash', 
            'buy-now', 'scam', 'paid-service', 'essay-writing', 
            'pay-someone', 'homework-help'
        ]
        
        for hk in hardcoded_keywords:
            if hk in scan_payload:
                all_flags.append({
                    'keyword': hk,
                    'category': 'Academic Integrity / Spam Policy Violation',
                    'severity': 3
                })

        if all_flags:
            primary_violation = all_flags[0]
            violation_details = ", ".join([f"'{f['keyword']}' ({f['category']})" for f in all_flags])
            
            # 3. CORE HIGHLIGHT: Automatically generate and insert a live Admin Activity Log
            try:
                log_entry = AdminLog()
                log_entry.admin_id = 1  # Standard system-level automation user ID
                log_entry.action = "Security Block"
                log_entry.target_type = "Project Submission"
                log_entry.target_id = current_user.id
                log_entry.details = (
                    f"Automated guardrail blocked submission from account [{current_user.email}]. "
                    f"Prohibited phrase detected: '{primary_violation['keyword']}' "
                    f"under policy category [{primary_violation['category']}]."
                )
                db.session.add(log_entry)
                db.session.commit()
            except Exception as log_err:
                db.session.rollback() # Gracesfully pass if database structures are refreshing

            # 4. Throw a professional English system alert notification back to the interface
            flash(
                f"[SECURITY GUARDRAIL VIOLATION] Submission denied. "
                f"Your text contains a restricted keyword pattern: '{primary_violation['keyword']}' "
                f"flagged under category [{primary_violation['category'].upper()}].", 
                category="error"
            )
            return render_template("List_Your_Project.html")
        # =============================================================

        new_project = Project()
        new_project.user_id = current_user.id
        new_project.project_name = name 
        new_project.repo_url = repo 
        new_project.languages = langs 
        new_project.roles_needed = roles 
        new_project.description = desc
        new_project.status = 'Active'

        db.session.add(new_project)
        db.session.commit()

        # Handle screenshots upload
        files = request.files.getlist('screenshots') 
        for file in files:
            if file and file.filename != '':
                ext = os.path.splitext(file.filename)[1]
                filename = str(uuid.uuid4()) + ext 
                
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                new_image = ProjectImage()
                new_image.filename = filename
                new_image.project_id = new_project.id
                db.session.add(new_image)

        db.session.commit()

        # =============================================================
        # 🏆 AUTO-ASSIGN "FIRST PROJECT" BADGE
        # =============================================================
        project_count = Project.query.filter_by(user_id=current_user.id).count()
        if project_count == 1:
            existing_badge = Badge.query.filter_by(user_id=current_user.id, badge='First Project').first()
            if not existing_badge:
                first_badge = Badge(user_id=current_user.id, badge='First Project')
                db.session.add(first_badge)
                db.session.commit()
                flash("Congratulations! You earned the 'First Project' badge! 🏆", "success")

        # 🏷️ AUTO-ASSIGN LANGUAGE BADGES
        sync_lang_badges(current_user.id)
        db.session.commit()

        return redirect(url_for('views.upload_success'))
    
    return render_template("List_Your_Project.html")

@views.route('/edit_project/<int:project_id>', methods=['GET', 'POST'])
def edit_project(project_id):
    current_user = get_current_user()
    if not current_user:
        flash("Please login to edit projects.", "error")
        return redirect(url_for('views.login'))

    project = Project.query.get_or_404(project_id)

    current_user_role = None
    if project.user_id == current_user.id:
        current_user_role = 'owner'
    else:
        member_record = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first()
        if member_record:
            current_user_role = member_record.role

    if current_user_role not in ['owner', 'admin']:
        flash("Permission Denied: Only project owners and admins can edit this project.", "error")
        return redirect(url_for('views.project_page', project_id=project.id))

    if request.method == 'POST':
        if current_user_role == 'owner':
            project.project_name = request.form.get('project_name')
            project.repo_url = request.form.get('repo_url')

        project.languages = request.form.get('languages')
        project.roles_needed = request.form.get('roles_needed')
        project.description = request.form.get('description')
        project.status = request.form.get('status')

        images_to_delete = request.form.getlist('delete_images')
        for img_id in images_to_delete:
            image_record = ProjectImage.query.get(img_id)
            if image_record and image_record.project_id == project.id:
                old_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_record.filename)
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
                db.session.delete(image_record)

        files = request.files.getlist('screenshots')
        for file in files:
            if file and file.filename != '':
                ext = os.path.splitext(file.filename)[1]
                new_filename = str(uuid.uuid4()) + ext
                
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], new_filename)
                file.save(file_path)
                
                new_image = ProjectImage()
                new_image.filename = new_filename
                new_image.project_id = project.id
                db.session.add(new_image)

        db.session.commit()
        # 🏷️ Recalculate language badges in case languages changed
        sync_lang_badges(project.user_id)
        db.session.commit()
        return redirect(url_for('views.project_page', project_id=project.id))

    return render_template("Edit_Project.html", project=project, current_user=current_user, current_user_role=current_user_role)

@views.route('/delete-project/<int:project_id>', methods=['POST'])
def delete_project(project_id):
    # 也可以改用下面的方式，防止已经软删除的项目被重复查询出来：
    # project = Project.query.filter_by(id=project_id).filter(Project.status != 'Deleted').first_or_404()
    project = Project.query.get_or_404(project_id)
    owner_id = project.user_id
    try:
        # Detach community posts (SET NULL) before deleting
        CommunityPost.query.filter_by(attached_project_id=project.id).update({'attached_project_id': None})

        # ❌ 注释掉或删掉这一行硬删除代码：
        # db.session.delete(project)
        db.session.flush()  # Flush so badge queries see the project as gone

        # 🏷️ Recalculate language badges
        sync_lang_badges(owner_id)

        # 🏷️ Revoke "First Project" badge if no projects remain
        if Project.query.filter_by(user_id=owner_id).count() == 0:
            _revoke_badge(owner_id, 'First Project')

        # 🏷️ Recalculate trending badges
        sync_trending_badges(owner_id)

        
        #  替换为这行软删除代码：把状态改为 'Deleted' 即可
        project.status = 'Deleted'
        
        db.session.commit()
        flash('Project deleted successfully!', category='success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting the project.', category='error')
        print(f"Error deleting project: {e}")
    return redirect(url_for('views.my_projects'))

# Reference: Werkzeug security - https://werkzeug.palletsprojects.com/en/stable/utils/#werkzeug.security.generate_password_hash
@views.route('/api/register', methods=['POST'])
def api_register():
    import json
    data     = request.get_json(silent=True) or {}
    email    = data.get('email', '').strip().lower()
    name     = data.get('name', '').strip()
    password = data.get('password', '')
    dev_interests = data.get('dev_interests', [])
    lang_interests = data.get('lang_interests', [])

    if not email or not password or not name:
        return jsonify({'error': 'All fields are required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    if not (email.endswith('@mmu.edu.my') or email.endswith('@student.mmu.edu.my')):
        return jsonify({'error': 'Only MMU email addresses (@mmu.edu.my or @student.mmu.edu.my) are allowed'}), 400

    pw_hash = generate_password_hash(password)
    
# --- MODIFIED: Generate OTP and store interests as JSON ---
    otp_code = f"{random.randint(0, 999999):06d}"
    interests_json = json.dumps({
        'dev_interests': dev_interests if dev_interests else [],
        'lang_interests': lang_interests if lang_interests else []
    })
    
    try:
        user = User()
        user.email = email
        user.name = name
        user.password_hash = pw_hash
        user.otp = otp_code
        user.interests = interests_json
        db.session.add(user)
        db.session.commit()
        
        if send_otp_email(email, otp_code):
            return jsonify({'success': True, 'message': 'Account created! Check email for OTP.'})
        else:
            db.session.delete(user)
            db.session.commit()
            return jsonify({'error': 'Failed to send verification email. Please try again.'}), 500
            
    except Exception as e:
        
        db.session.rollback()
        print(f"Registration error: {str(e)}")
        
        if 'unique' in str(e).lower() or 'email' in str(e).lower():
            return jsonify({'error': 'Email already registered'}), 409
            
        return jsonify({'error': f'Registration failed: {str(e)}'}), 400

@views.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not (email.endswith('@mmu.edu.my') or email.endswith('@student.mmu.edu.my')):
        return jsonify({'error': 'Only MMU email addresses (@mmu.edu.my or @student.mmu.edu.my) are allowed'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.password_hash or \
       not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid email or password'}), 401

    # --- ADDED: Check if account is verified ---
    if not user.is_verified:
        return jsonify({'error': 'Please verify your email first.'}), 403
    
    session['user_email'] = user.email
    session['user_name']  = user.name
    return jsonify({'success': True, 'email': user.email, 'name': user.name})


@views.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success': True})


@views.route('/api/me', methods=['GET'])
def api_me():
    if 'user_email' not in session:
        return jsonify({'loggedIn': False}), 401
    return jsonify({
        'loggedIn': True,
        'email':    session['user_email'],
        'name':     session['user_name'],
    })



# Profile API  (all require login)


@views.route('/api/profile', methods=['GET'])
def get_profile():
    err = require_login()
    if err:
        return err
    
    email = session['user_email']
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    skills = Skill.query.filter_by(user_id=user.id).all()
    badges = Badge.query.filter_by(user_id=user.id).all()
    
    avatar_url = f"/static/uploads/{user.avatar_path}" if user.avatar_path else ''
    interests_data = parse_interests(user.interests)
    # Combine both interest types for frontend
    combined_interests = interests_data.get('dev_interests', []) + interests_data.get('lang_interests', [])

    return jsonify({
        'id':             user.id,
        'email':          user.email,
        'name':           user.name,
        'faculty':        user.faculty,
        'bio':            user.bio or '',
        'avatar_url':     avatar_url,
        'rank':           user.rank,
        'karma':          user.karma,
        'skills':         [s.skill for s in skills],
        'badges':         [b.badge for b in badges],
        'interests':      combined_interests,
        'dev_interests':  interests_data.get('dev_interests', []),
        'lang_interests': interests_data.get('lang_interests', []),
        'is_admin':       user.is_admin or False,   # ← 加这行
    })


@views.route('/api/user/<int:user_id>', methods=['GET'])
def get_user_profile(user_id):
    """Get any user's profile data"""
    user = User.query.get_or_404(user_id)
    
    settings = user.settings
    is_private = settings and settings.profile_visibility == 'private'
    
    current_user = get_current_user()
    current_user_id = current_user.id if current_user else None
    
    if is_private and current_user_id != user.id:
        return jsonify({'error': 'This profile is private', 'is_private': True}), 403

    
    skills = Skill.query.filter_by(user_id=user.id).all()
    badges = Badge.query.filter_by(user_id=user.id).all()
    
    avatar_url = f"/static/uploads/{user.avatar_path}" if user.avatar_path else ''
    interests_data = parse_interests(user.interests)
    # Combine both interest types for frontend
    combined_interests = interests_data.get('dev_interests', []) + interests_data.get('lang_interests', [])

    return jsonify({
        'id':             user.id,
        'email':          user.email,
        'name':           user.name,
        'faculty':        user.faculty,
        'bio':            user.bio or '',
        'avatar_url':     avatar_url,
        'rank':           user.rank,
        'karma':          user.karma,
        'skills':         [s.skill for s in skills],
        'badges':         [b.badge for b in badges],
        'interests':      combined_interests,
        'dev_interests':  interests_data.get('dev_interests', []),
        'lang_interests': interests_data.get('lang_interests', []),
    })

@views.route('/api/profile', methods=['PUT'])
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
    # Handle combined interests from frontend
    interests = data.get('interests', [])
    dev_interests = data.get('dev_interests', interests)
    lang_interests = data.get('lang_interests', [])

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
                skill_obj = Skill()
                skill_obj.user_id = user.id
                skill_obj.skill = skill.strip()
                db.session.add(skill_obj)

    # Update interests as JSON
    if dev_interests is not None or lang_interests is not None:
        interests_json = json.dumps({
            'dev_interests': dev_interests if dev_interests else [],
            'lang_interests': lang_interests if lang_interests else []
        })
        user.interests = interests_json

    db.session.commit()

    return jsonify({'success': True, 'message': 'Profile updated'})


@views.route('/api/profile/avatar', methods=['POST'])
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

    return jsonify({'success': True, 'avatar_url': f'/static/uploads/{filename}'})


# ── Settings API ────────────────────────────────────────────────────────

@views.route('/api/settings', methods=['GET'])
def get_settings():
    """Retrieve user settings"""
    err = require_login()
    if err:
        return err
    
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Get or create user settings
    settings = user.settings
    if not settings:
        settings = UserSettings()
        settings.user_id = user.id
        db.session.add(settings)
        db.session.commit()
    
    return jsonify({
        'privacy': {
            'profile_visibility': settings.profile_visibility,
            'email_visibility': settings.email_visibility,
            'show_rank': settings.show_rank,
            'show_karma': settings.show_karma,
        },
        'notifications': {
            'qna_answers': settings.notify_qna_new_answers,
            'project_comments': settings.notify_project_comments,
            'profile_views': settings.notify_profile_views,
            'project_invites': settings.notify_project_invites,
            'suggestions': settings.notify_new_suggestions,
            'newsletter': settings.notify_newsletter,
        },
        'display': {
            'theme': settings.theme,
        },
        'other': {
            'direct_messages': settings.allow_direct_messages,
            'auto_accept': settings.auto_accept_collaborations,
        }
    })


@views.route('/api/settings', methods=['PUT'])
def update_settings():
    """Update user settings"""
    err = require_login()
    if err:
        return err
    
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Get or create user settings
    settings = user.settings
    if not settings:
        settings = UserSettings()
        settings.user_id = user.id
        db.session.add(settings)
        db.session.flush()
    
    data = request.get_json(silent=True) or {}
    
    # Update privacy settings
    privacy = data.get('privacy', {})
    if 'profile_visibility' in privacy:
        settings.profile_visibility = privacy['profile_visibility']
    if 'email_visibility' in privacy:
        settings.email_visibility = privacy['email_visibility']
    if 'show_rank' in privacy:
        settings.show_rank = privacy['show_rank']
    if 'show_karma' in privacy:
        settings.show_karma = privacy['show_karma']
    
    # Update notification settings
    notifications = data.get('notifications', {})
    if 'qna_answers' in notifications:
        settings.notify_qna_new_answers = notifications['qna_answers']
    if 'project_comments' in notifications:
        settings.notify_project_comments = notifications['project_comments']
    if 'profile_views' in notifications:
        settings.notify_profile_views = notifications['profile_views']
    if 'project_invites' in notifications:
        settings.notify_project_invites = notifications['project_invites']
    if 'suggestions' in notifications:
        settings.notify_new_suggestions = notifications['suggestions']
    if 'newsletter' in notifications:
        settings.notify_newsletter = notifications['newsletter']
    
    # Update display settings
    display = data.get('display', {})
    if 'theme' in display:
        settings.theme = display['theme']
    
    # Update other settings
    other = data.get('other', {})
    if 'direct_messages' in other:
        settings.allow_direct_messages = other['direct_messages']
    if 'auto_accept' in other:
        settings.auto_accept_collaborations = other['auto_accept']
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Settings updated successfully'})


# Comments API


@views.route('/api/comments', methods=['GET'])
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

@views.route('/api/comments', methods=['POST'])
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
    
    comment = Comment()
    comment.user_id = user.id
    comment.comment = comment_text
    db.session.add(comment)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Comment posted'})



# Projects API


@views.route('/api/projects', methods=['GET'])
def get_projects():
    err = require_login()
    if err:
        return err
    
    email = session['user_email']
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    projects = Project.query.filter(
    Project.user_id == user.id,
    Project.status != 'Suspended'
).order_by(Project.created_at.desc()).all()
    
    return jsonify([{
        'id': p.id,
        'project_name': p.project_name,
        'description': p.description,
        'status': p.status,
        'contributors': p.contributors,
        'created_at': p.created_at.isoformat(),
    } for p in projects])


@views.route('/api/all-projects', methods=['GET'])
def get_all_projects():
    """Get all projects for search page"""
    projects = Project.query.filter(
    Project.status != 'Suspended'
).order_by(Project.created_at.desc()).all()
    
    return jsonify([{
        'id': p.id,
        'project_name': p.project_name,
        'description': p.description,
        'status': p.status,
        'contributors': p.contributors,
        'languages': p.languages,
        'created_at': p.created_at.isoformat(),
        'views': p.views or 0,
    } for p in projects])


# Suggestions API


@views.route('/api/suggestions', methods=['GET'])
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
            'project_name': project.project_name,
            'description': project.description,
            'status': project.status,
            'contributors': project.contributors,
            'match_score': min(100, 50 + (skill_matches or 0) * 10),
        })
    
    return jsonify(result)


@views.route('/api/suggestions/<int:project_id>', methods=['POST'])
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
        suggestion = Suggestion()
        suggestion.user_id = user.id
        suggestion.project_id = project_id
        suggestion.match_score = 100
        db.session.add(suggestion)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Already suggested'}), 409
    
    return jsonify({'success': True, 'message': 'Project suggested to you!'})


# Q&A API

@views.route('/api/questions', methods=['GET'])
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

        image_urls = [f'/static/uploads/{img.image_path}' for img in q.images]

        result.append({
            'id':           q.id,
            'user_id':      q.user_id,
            'author_name':  author_name,
            'title':        q.title,
            'body':         q.body,
            'image_url':    f'/static/uploads/{q.image_path}' if q.image_path else '',
            'image_urls':   image_urls,
            'created_at':   q.created_at.isoformat(),
            'like_count':   like_count,
            'fav_count':    fav_count,
            'comment_count': cmt_count,
            'user_liked':   user_liked,
            'user_faved':   user_faved,
            'is_owner':     (current_user_id == q.user_id),
        })

    return jsonify(result)


@views.route('/api/questions', methods=['POST'])
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
    q = Question()
    q.user_id = user.id
    q.title = title
    q.body = body

    # Handle optional multiple images
    if 'images' in request.files:
        files = request.files.getlist('images')
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"q_{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                img = QuestionImage()
                img.image_path = filename
                q.images.append(img)

    db.session.add(q)
    db.session.commit()
    return jsonify({'success': True, 'id': q.id})


@views.route('/api/questions/<int:question_id>', methods=['DELETE'])
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


@views.route('/api/questions/<int:question_id>', methods=['PUT'])
def edit_question(question_id):
    err = require_login()
    if err:
        return err

    user = User.query.filter_by(email=session['user_email']).first()
    q = Question.query.get(question_id)

    if not q:
        return jsonify({'error': 'Question not found'}), 404
    if q.user_id != user.id:
        return jsonify({'error': 'Not authorised'}), 403

    # Support multipart (with images) and plain JSON
    if request.content_type and 'multipart' in request.content_type:
        title = request.form.get('title', '').strip()
        body = request.form.get('body', '').strip()
    else:
        data = request.get_json(silent=True) or {}
        title = data.get('title', '').strip()
        body = data.get('body', '').strip()

    if not title:
        return jsonify({'error': 'Title is required'}), 400
    if not body:
        return jsonify({'error': 'Question body is required'}), 400
    if len(title) > 300:
        return jsonify({'error': 'Title too long (max 300 chars)'}), 400
    if len(body) > 5000:
        return jsonify({'error': 'Body too long (max 5000 chars)'}), 400

    q.title = title
    q.body = body

    # Handle optional new images
    if 'images' in request.files:
        files = request.files.getlist('images')
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"q_{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                img = QuestionImage()
                img.image_path = filename
                q.images.append(img)

    db.session.commit()
    return jsonify({'success': True, 'id': q.id})


@views.route('/api/question-images/<int:image_id>', methods=['DELETE'])
def delete_question_image(image_id):
    err = require_login()
    if err:
        return err

    user = User.query.filter_by(email=session['user_email']).first()
    img = QuestionImage.query.get(image_id)
    if not img:
        return jsonify({'error': 'Image not found'}), 404
    
    q = img.question
    if q.user_id != user.id:
        return jsonify({'error': 'Not authorised'}), 403

    db.session.delete(img)
    db.session.commit()
    return jsonify({'success': True})


@views.route('/api/comment-images/<int:image_id>', methods=['DELETE'])
def delete_qna_comment_image(image_id):
    err = require_login()
    if err:
        return err

    user = User.query.filter_by(email=session['user_email']).first()
    img = QuestionCommentImage.query.get(image_id)
    if not img:
        return jsonify({'error': 'Image not found'}), 404
    
    c = img.comment
    if c.user_id != user.id:
        return jsonify({'error': 'Not authorised'}), 403

    db.session.delete(img)
    db.session.commit()
    return jsonify({'success': True})


@views.route('/api/questions/<int:question_id>/like', methods=['POST'])
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
        ql = QuestionLike()
        ql.user_id = user.id
        ql.question_id = question_id
        db.session.add(ql)
        liked = True

    db.session.commit()
    count = QuestionLike.query.filter_by(question_id=question_id).count()
    return jsonify({'liked': liked, 'like_count': count})


@views.route('/api/questions/<int:question_id>/favorite', methods=['POST'])
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
        qf = QuestionFavorite()
        qf.user_id = user.id
        qf.question_id = question_id
        db.session.add(qf)
        faved = True

    db.session.commit()
    count = QuestionFavorite.query.filter_by(question_id=question_id).count()
    return jsonify({'faved': faved, 'fav_count': count})


@views.route('/api/questions/<int:question_id>/comments', methods=['GET'])
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
        'author_id':   c.user_id,
        'author_name': name,
        'body':        c.body,
        'parent_id':   c.parent_id,
        'created_at':  c.created_at.isoformat(),
        'is_owner':    (current_user_id == c.user_id),
        'image_urls':  [f'/static/uploads/{img.image_path}' for img in c.images],
    } for c, name in rows]

    return jsonify(result)


@views.route('/api/questions/<int:question_id>/comments', methods=['POST'])
def post_question_comment(question_id):
    err = require_login()
    if err:
        return err

    # Support multipart (with images) and plain JSON
    if request.content_type and 'multipart' in request.content_type:
        body = request.form.get('body', '').strip()
    else:
        data = request.get_json(silent=True) or {}
        body = data.get('body', '').strip()

    if not body:
        return jsonify({'error': 'Comment cannot be empty'}), 400
    if len(body) > 1000:
        return jsonify({'error': 'Comment too long (max 1000 chars)'}), 400

    q = Question.query.get(question_id)
    if not q:
        return jsonify({'error': 'Question not found'}), 404

    parent_id = None
    if request.content_type and 'multipart' in request.content_type:
        parent_id = request.form.get('parent_id', None)
    else:
        data = request.get_json(silent=True) or {}
        parent_id = data.get('parent_id', None)
    
    if parent_id:
        parent = QuestionComment.query.get(parent_id)
        if not parent or parent.question_id != question_id:
            parent_id = None

    user = User.query.filter_by(email=session['user_email']).first()
    c = QuestionComment()
    c.user_id = user.id
    c.question_id = question_id
    c.body = body
    c.parent_id = parent_id
    
    # Handle optional multiple images
    if 'images' in request.files:
        files = request.files.getlist('images')
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"c_{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                img = QuestionCommentImage()
                img.image_path = filename
                c.images.append(img)
    
    db.session.add(c)
    db.session.commit()
    return jsonify({'success': True, 'id': c.id})


# ---------------------------------------------------------------------------
# Delete comment
# ---------------------------------------------------------------------------

@views.route('/api/questions/<int:question_id>/comments/<int:comment_id>', methods=['DELETE'])
def delete_question_comment(question_id, comment_id):
    err = require_login()
    if err:
        return err

    user = User.query.filter_by(email=session['user_email']).first()
    c = QuestionComment.query.get(comment_id)
    
    if not c or c.question_id != question_id:
        return jsonify({'error': 'Comment not found'}), 404
        
    q = Question.query.get(question_id)
    is_q_owner = (q and q.user_id == user.id)
    
    if c.user_id != user.id and not is_q_owner:
        return jsonify({'error': 'Not authorised'}), 403

    db.session.delete(c)
    db.session.commit()
    return jsonify({'success': True})

@views.route('/api/questions/<int:question_id>/comments/<int:comment_id>', methods=['PUT'])
def edit_question_comment(question_id, comment_id):
    err = require_login()
    if err:
        return err

    user = User.query.filter_by(email=session['user_email']).first()
    c = QuestionComment.query.get(comment_id)
    if not c or c.question_id != question_id:
        return jsonify({'error': 'Comment not found'}), 404
    if c.user_id != user.id:
        return jsonify({'error': 'Not authorised'}), 403

    # Support multipart (with images) and plain JSON
    if request.content_type and 'multipart' in request.content_type:
        body = request.form.get('body', '').strip()
    else:
        data = request.get_json(silent=True) or {}
        body = data.get('body', '').strip()

    if not body:
        return jsonify({'error': 'Comment cannot be empty'}), 400
    if len(body) > 1000:
        return jsonify({'error': 'Comment too long (max 1000 chars)'}), 400

    c.body = body
    
    # Handle optional new images
    if 'images' in request.files:
        files = request.files.getlist('images')
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"c_{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                img = QuestionCommentImage()
                img.image_path = filename
                c.images.append(img)
    
    db.session.commit()
    return jsonify({'success': True, 'body': c.body})


# ---------------------------------------------------------------------------
# Liked / Favorited question lists
# ---------------------------------------------------------------------------

def _build_question_result(q, author_name, current_user_id):
    like_count = QuestionLike.query.filter_by(question_id=q.id).count()
    fav_count  = QuestionFavorite.query.filter_by(question_id=q.id).count()
    cmt_count  = QuestionComment.query.filter_by(question_id=q.id).count()
    user_liked = QuestionLike.query.filter_by(user_id=current_user_id, question_id=q.id).first() is not None
    user_faved = QuestionFavorite.query.filter_by(user_id=current_user_id, question_id=q.id).first() is not None
    image_urls = [f'/static/uploads/{img.image_path}' for img in q.images]
    return {
        'id': q.id, 'user_id': q.user_id, 'author_name': author_name,
        'title': q.title, 'body': q.body,
        'image_url': f'/static/uploads/{q.image_path}' if q.image_path else '',
        'image_urls': image_urls,
        'created_at': q.created_at.isoformat(),
        'like_count': like_count, 'fav_count': fav_count, 'comment_count': cmt_count,
        'user_liked': user_liked, 'user_faved': user_faved,
        'is_owner': (current_user_id == q.user_id),
    }


@views.route('/api/questions/liked', methods=['GET'])
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


@views.route('/api/questions/favorited', methods=['GET'])
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



# =====================================================================
# API: Project Member Invitations 
# =====================================================================

@views.route('/api/project/<int:project_id>/add_member', methods=['POST'])
def add_member(project_id):
    """Owner invites a user via email. Sends an invitation instead of direct add."""
    err = require_login()
    if err: return err
    
    current_user = get_current_user()
    project = Project.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({"error": "Unauthorized. Only the Project Lead can invite members."}), 403

    data = request.get_json(silent=True) or {}
    email_to_add = data.get('email', '').strip().lower()

    if not email_to_add:
        return jsonify({"error": "Email is required"}), 400

    user_to_add = User.query.filter_by(email=email_to_add).first()

    if not user_to_add:
        return jsonify({"error": "User with this email not found"}), 404

    existing_member = ProjectMember.query.filter_by(project_id=project_id, user_id=user_to_add.id).first()
    if existing_member:
        return jsonify({"error": "User is already a member of this project"}), 400

    existing_request = JoinRequest.query.filter_by(project_id=project_id, user_id=user_to_add.id).first()
    
    if existing_request:
        if existing_request.status == 'invited':
            return jsonify({"error": "An invitation has already been sent to this user."}), 400
        elif existing_request.status == 'pending':
            existing_request.status = 'accepted'
            new_member = ProjectMember(project_id=project_id, user_id=user_to_add.id, role='member')  # type: ignore
            db.session.add(new_member)

            history = MemberHistory(user_id=user_to_add.id, project_id=project_id, action='joined', reason=None)  # type: ignore
            db.session.add(history)
            db.session.commit()
            return jsonify({"success": f"{user_to_add.name} had already applied to join. They are now added!", "user_name": user_to_add.name})
        elif existing_request.status == 'rejected':
            existing_request.status = 'invited'
            db.session.commit()
            return jsonify({"success": f"Invitation sent to {user_to_add.name}!", "user_name": user_to_add.name})

    new_invite = JoinRequest(user_id=user_to_add.id, project_id=project_id, status='invited')  # type: ignore
    db.session.add(new_invite)
    
    db.session.commit()

    return jsonify({"success": f"Invitation sent to {user_to_add.name}! Waiting for their approval.", "user_name": user_to_add.name})


@views.route('/api/my-invitations', methods=['GET'])
def get_my_invitations():
    """Get all pending invitations for the current logged-in user.
    Respects the notify_project_invites user setting — returns empty list if disabled.
    """
    err = require_login()
    if err: return err
    
    current_user = get_current_user()
    
    # Check whether the user has disabled project invite notifications
    settings = current_user.settings
    if settings and not settings.notify_project_invites:
        # Return empty list with a flag so the frontend knows it's disabled
        return jsonify([])
    
    invitations = JoinRequest.query.filter_by(
        user_id=current_user.id, 
        status='invited'
    ).order_by(JoinRequest.created_at.desc()).all()
    
    return jsonify([{
        'id': inv.id,
        'project_id': inv.project_id,
        'project_name': inv.project.project_name,
        'owner_name': inv.project.user.name, 
        'created_at': inv.created_at.isoformat()
    } for inv in invitations])


@views.route('/api/invitations/<int:request_id>/<action>', methods=['POST'])
def respond_to_invitation(request_id, action):
    """Accept or reject a project invitation"""
    err = require_login()
    if err: return err
    
    current_user = get_current_user()
    invitation = JoinRequest.query.get_or_404(request_id)
    
    if invitation.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    if invitation.status != 'invited':
        return jsonify({'error': 'This invitation is no longer valid'}), 400
        
    if action == 'accept':
        invitation.status = 'accepted'
        existing = ProjectMember.query.filter_by(project_id=invitation.project_id, user_id=current_user.id).first()
        if not existing:
            new_member = ProjectMember(project_id=invitation.project_id, user_id=current_user.id, role='member')  # type: ignore
            db.session.add(new_member)
        msg = 'Invitation accepted! You joined the project.'
    elif action == 'reject':
        invitation.status = 'rejected'
        msg = 'Invitation declined.'
    else:
        return jsonify({'error': 'Invalid action'}), 400
        
    db.session.commit()
    return jsonify({'success': msg})

@views.route('/api/project/<int:project_id>/member/<int:user_id>/role', methods=['PUT'])
def update_member_role(project_id, user_id):
    """Change member role (Only Owner can execute this)"""
    err = require_login()
    if err: return err
    
    project = Project.query.get_or_404(project_id)
    current_user = get_current_user()
    
    if project.user_id != current_user.id:
        return jsonify({"error": "Unauthorized. Only the Project Lead can manage roles."}), 403
        
    member_record = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first()
    if not member_record:
        return jsonify({"error": "Member not found in this project."}), 404
        
    data = request.get_json(silent=True) or {}
    new_role = data.get('role')
    
    if new_role not in ['admin', 'member']:
        return jsonify({"error": "Invalid role specified."}), 400
        
    member_record.role = new_role
    
    db.session.commit()
    
    return jsonify({"success": True, "message": f"Role updated to {new_role}"}), 200

@views.route('/api/project/<int:project_id>/member/<int:user_id>', methods=['DELETE'])
def remove_or_leave_member(project_id, user_id):
    err = require_login()
    if err: return err
    
    project = Project.query.get_or_404(project_id)
    current_user = get_current_user()
    
    current_user_role = None
    if project.user_id == current_user.id:
        current_user_role = 'owner'
    else:
        member_record = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first()
        if member_record:
            current_user_role = member_record.role

    target_member = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first()
    if not target_member:
        return jsonify({"error": "Member not found in this project."}), 404
    if current_user.id == user_id:
        if current_user_role == 'owner':
            return jsonify({"error": "Project owner cannot leave the project. Please transfer ownership first."}), 400
            
    else:
        if current_user_role not in ['owner', 'admin']:
            return jsonify({"error": "Unauthorized. Only project owners and admins can remove members."}), 403
            
        if current_user_role == 'admin':
            if user_id == project.user_id:
                return jsonify({"error": "Admins cannot remove the project owner."}), 403
            if target_member.role == 'admin':
                return jsonify({"error": "Admins cannot remove other admins."}), 403

    try:
        db.session.delete(target_member)
        db.session.commit()
        return jsonify({"success": True, "message": "Member removed successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500


# ─────────────────────────────────────────────────────────────────────────
# Join Request API
# ─────────────────────────────────────────────────────────────────────────

@views.route('/api/project/<int:project_id>/request-join', methods=['POST'])
def request_join_project(project_id):
    """User requests to join a project"""
    err = require_login()
    if err: return err
    
    current_user = get_current_user()
    project = Project.query.get_or_404(project_id)
    
    # Check if user is already a member
    existing_member = ProjectMember.query.filter_by(project_id=project_id, user_id=current_user.id).first()
    if existing_member:
        return jsonify({"error": "You are already a member of this project"}), 400
        
    # Prevent creator from applying to join their own project
    if project.user_id == current_user.id:
        return jsonify({"error": "You are the project owner."}), 400
    
    # Check if request already exists
    existing_request = JoinRequest.query.filter_by(
        user_id=current_user.id,
        project_id=project_id
    ).first()
    
    if existing_request:
        if existing_request.status == 'pending':
            return jsonify({"error": "You have already sent a join request"}), 400
        elif existing_request.status == 'rejected':
            # Delete the old rejected request and allow user to submit a new one
            db.session.delete(existing_request)
            db.session.commit()
        elif existing_request.status == 'accepted':
            existing_request.status = 'pending'
            db.session.commit()
            return jsonify({"success": "Join request sent successfully!"}), 200
    else:
        join_request = JoinRequest(user_id=current_user.id, project_id=project_id, status='pending')  # type: ignore
        db.session.add(join_request)
        db.session.commit()
        return jsonify({"success": "Join request sent successfully!"}), 201
    
@views.route('/api/project/<int:project_id>/join-requests', methods=['GET'])
def get_join_requests(project_id):
    """Get all join requests for a project (only for project lead)"""
    err = require_login()
    if err: return err
    
    current_user = get_current_user()
    project = Project.query.get_or_404(project_id)
    
    # Security check: Only the project lead can view requests
    if project.user_id != current_user.id:
        return jsonify({"error": "Unauthorized. Only the Project Lead can view requests."}), 403
    
    # Get pending requests
    requests = JoinRequest.query.filter_by(
        project_id=project_id,
        status='pending'
    ).order_by(JoinRequest.created_at.desc()).all()
    
    return jsonify([{
        'id': r.id,
        'user_id': r.user_id,
        'user_name': r.user.name,
        'user_email': r.user.email,
        'user_faculty': r.user.faculty,
        'created_at': r.created_at.isoformat()
    } for r in requests])


@views.route('/api/project/<int:project_id>/join-requests/<int:request_id>/accept', methods=['POST'])
def accept_join_request(project_id, request_id):
    """Accept a join request"""
    err = require_login()
    if err: return err
    
    current_user = get_current_user()
    project = Project.query.get_or_404(project_id)
    join_request = JoinRequest.query.get_or_404(request_id)
    
    # Security check: Only the project lead can accept requests
    if project.user_id != current_user.id:
        return jsonify({"error": "Unauthorized. Only the Project Lead can accept requests."}), 403
    
    if join_request.project_id != project_id:
        return jsonify({"error": "Request does not belong to this project"}), 400
    
    if join_request.status != 'pending':
        return jsonify({"error": f"Request is already {join_request.status}"}), 400
    
    user_to_add = User.query.get_or_404(join_request.user_id)
    
    existing_member = ProjectMember.query.filter_by(project_id=project_id, user_id=user_to_add.id).first()
    if not existing_member:
        new_member = ProjectMember(project_id=project_id, user_id=user_to_add.id, role='member')  # type: ignore
        db.session.add(new_member)
        
        # Create member history record
        history = MemberHistory(user_id=user_to_add.id, project_id=project_id, action='joined', reason=None)  # type: ignore
        db.session.add(history)
    
    # Update request status
    join_request.status = 'accepted'
    db.session.commit()
    
    return jsonify({"success": "Join request accepted!", "user_name": user_to_add.name})

@views.route('/api/project/<int:project_id>/join-requests/<int:request_id>/reject', methods=['POST'])
def reject_join_request(project_id, request_id):
    """Reject a join request"""
    err = require_login()
    if err: return err
    
    current_user = get_current_user()
    project = Project.query.get_or_404(project_id)
    join_request = JoinRequest.query.get_or_404(request_id)
    
    # Security check: Only the project lead can reject requests
    if project.user_id != current_user.id:
        return jsonify({"error": "Unauthorized. Only the Project Lead can reject requests."}), 403
    
    if join_request.project_id != project_id:
        return jsonify({"error": "Request does not belong to this project"}), 400
    
    if join_request.status != 'pending':
        return jsonify({"error": f"Request is already {join_request.status}"}), 400
    
    # Update request status
    join_request.status = 'rejected'
    db.session.commit()
    
    return jsonify({"success": "Join request rejected!"})


# ─────────────────────────────────────────────────────────────────────────
# Team Member Leave Request API
# ─────────────────────────────────────────────────────────────────────────

@views.route('/api/project/<int:project_id>/leave-project', methods=['POST'])
def leave_project_immediately(project_id):
    """Team member immediately leaves the project with optional message"""
    err = require_login()
    if err:
        return err
    
    project = Project.query.get_or_404(project_id)
    current_user = get_current_user()
    
    # Check if user is a team member
    if current_user not in project.members:
        return jsonify({'error': 'You are not a member of this project'}), 403
    
    data = request.get_json(silent=True) or {}
    reason = data.get('reason', '').strip()
    
    try:
        # Remove user from project members
        project.members.remove(current_user)
        
        # Clean up old join requests so user can rejoin later
        # Delete all previous join requests (rejected or accepted)
        old_requests = JoinRequest.query.filter_by(
            user_id=current_user.id,
            project_id=project_id
        ).all()
        for old_req in old_requests:
            db.session.delete(old_req)
        
        # Create member history record
        history = MemberHistory(user_id=current_user.id, project_id=project_id, action='left', reason=reason if reason else None)  # type: ignore
        
        db.session.add(history)
        db.session.commit()
        
        return jsonify({'success': 'You have left the project successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@views.route('/api/project/<int:project_id>/leave-request', methods=['POST'])
def request_leave_team(project_id):
    """Team member requests to leave a project"""
    err = require_login()
    if err:
        return err
    
    project = Project.query.get_or_404(project_id)
    current_user = get_current_user()
    
    # Check if user is a team member
    if current_user not in project.members:
        return jsonify({'error': 'You are not a member of this project'}), 403
    
    # Check if there's already a pending leave request
    existing = LeaveRequest.query.filter_by(
        user_id=current_user.id,
        project_id=project_id,
        status='pending'
    ).first()
    
    if existing:
        return jsonify({'error': 'You already have a pending leave request'}), 400
    
    data = request.get_json(silent=True) or {}
    reason = data.get('reason', '').strip()
    
    if not reason:
        return jsonify({'error': 'Reason is required'}), 400
    
    if len(reason) < 10:
        return jsonify({'error': 'Reason must be at least 10 characters'}), 400
    
    leave_req = LeaveRequest(user_id=current_user.id, project_id=project_id, reason=reason, status='pending')  # type: ignore
    
    db.session.add(leave_req)
    db.session.commit()
    
    return jsonify({
        'id': leave_req.id,
        'reason': leave_req.reason,
        'status': leave_req.status,
        'created_at': leave_req.created_at.isoformat(),
    }), 201


@views.route('/api/project/<int:project_id>/leave-requests', methods=['GET'])
def get_leave_requests(project_id):
    """Get all leave requests for a project (owner only)"""
    err = require_login()
    if err:
        return err
    
    project = Project.query.get_or_404(project_id)
    current_user = get_current_user()
    
    # Only project owner can view leave requests
    if project.user_id != current_user.id:
        return jsonify({'error': 'Only project owner can view leave requests'}), 403
    
    requests = LeaveRequest.query.filter_by(project_id=project_id).order_by(LeaveRequest.created_at.desc()).all()
    
    return jsonify([{
        'id': r.id,
        'user_id': r.user_id,
        'user_name': r.user.name,
        'user_email': r.user.email,
        'reason': r.reason,
        'status': r.status,
        'created_at': r.created_at.isoformat(),
    } for r in requests])


@views.route('/api/project/<int:project_id>/leave-requests/<int:request_id>/approve', methods=['POST'])
def approve_leave_request(project_id, request_id):
    """Approve a leave request and remove member from project"""
    err = require_login()
    if err:
        return err
    
    project = Project.query.get_or_404(project_id)
    leave_req = LeaveRequest.query.get_or_404(request_id)
    current_user = get_current_user()
    
    # Only project owner can approve
    if project.user_id != current_user.id:
        return jsonify({'error': 'Only project owner can approve leave requests'}), 403
    
    if leave_req.project_id != project_id:
        return jsonify({'error': 'Request not found in this project'}), 404
    
    if leave_req.status != 'pending':
        return jsonify({'error': 'Request is already ' + leave_req.status}), 400
    
    # Get the member to remove
    member = User.query.get(leave_req.user_id)
    if member and member in project.members:
        project.members.remove(member)
    
    # Update leave request status
    leave_req.status = 'approved'
    leave_req.approved_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'success': 'Leave request approved. Member removed from project.'})


@views.route('/api/project/<int:project_id>/leave-requests/<int:request_id>/reject', methods=['POST'])
def reject_leave_request(project_id, request_id):
    """Reject a leave request"""
    err = require_login()
    if err:
        return err
    
    project = Project.query.get_or_404(project_id)
    leave_req = LeaveRequest.query.get_or_404(request_id)
    current_user = get_current_user()
    
    # Only project owner can reject
    if project.user_id != current_user.id:
        return jsonify({'error': 'Only project owner can reject leave requests'}), 403
    
    if leave_req.project_id != project_id:
        return jsonify({'error': 'Request not found in this project'}), 404
    
    if leave_req.status != 'pending':
        return jsonify({'error': 'Request is already ' + leave_req.status}), 400
    
    leave_req.status = 'rejected'
    db.session.commit()
    
    return jsonify({'success': 'Leave request rejected.'})


@views.route('/api/project/<int:project_id>/my-leave-status', methods=['GET'])
def get_my_leave_status(project_id):
    """Get current user's leave request status for a project"""
    err = require_login()
    if err:
        return err
    
    current_user = get_current_user()
    
    leave_req = LeaveRequest.query.filter_by(
        user_id=current_user.id,
        project_id=project_id
    ).first()
    
    if not leave_req:
        return jsonify({'status': None})
    
    return jsonify({
        'id': leave_req.id,
        'status': leave_req.status,
        'reason': leave_req.reason,
        'created_at': leave_req.created_at.isoformat(),
        'approved_at': leave_req.approved_at.isoformat() if leave_req.approved_at else None,
    })


# ─────────────────────────────────────────────────────────────────────────
# Project Comments API
# ─────────────────────────────────────────────────────────────────────────

@views.route('/api/project/<int:project_id>/comments', methods=['GET'])
def get_project_comments(project_id):
    """Get all comments for a project, organized by type"""
    err = require_login()
    if err:
        return err
    
    project = Project.query.get_or_404(project_id)
    comments = ProjectComment.query.filter_by(project_id=project_id).order_by(ProjectComment.created_at.desc()).all()
    
    return jsonify([{
        'id': c.id,
        'author_id': c.user_id,
        'author_name': c.author.name,
        'author_email': c.author.email,
        'content': c.content,
        'comment_type': c.comment_type,
        'label': c.label,
        'user_role': c.user_role,
        'created_at': c.created_at.isoformat(),
        'updated_at': c.updated_at.isoformat(),
        'images': [{'id': img.id, 'url': f'/static/uploads/{img.image_path}'} for img in c.images],
    } for c in comments])


@views.route('/api/project/<int:project_id>/comments', methods=['POST'])
def create_project_comment(project_id):
    """Create a new comment on a project (supports multipart for image uploads)"""
    err = require_login()
    if err:
        return err
    
    project = Project.query.get_or_404(project_id)
    current_user = get_current_user()
    
    # Support both multipart (with images) and plain JSON
    if request.content_type and 'multipart' in request.content_type:
        content = request.form.get('content', '').strip()
        comment_type = request.form.get('comment_type', 'normal')
        label = request.form.get('label', None)
    else:
        data = request.get_json(silent=True) or {}
        content = data.get('content', '').strip()
        comment_type = data.get('comment_type', 'normal')
        label = data.get('label', None)
    
    if not content:
        return jsonify({'error': 'Comment content is required'}), 400

    # ─── 核心修改：在这里插入黑名单留言拦截雷达 ───
    triggered_word = contains_banned_keywords(content)
    if triggered_word:
        return jsonify({
            'error': f"Comment blocked: Your text contains the unallowed keyword '{triggered_word}'."
        }), 400
    # ──────────────────────────────────────────
    
    if comment_type not in ['normal', 'issue', 'suggestion']:
        return jsonify({'error': 'Invalid comment type'}), 400

    # 后面是你原本的处理逻辑（比如保存评论到数据库、处理图片等）...
    
# Determine user role
    user_role = 'user'
    if current_user.id == project.user_id:
        user_role = 'owner'
    else:
        is_member = ProjectMember.query.filter_by(project_id=project_id, user_id=current_user.id).first()
        if is_member:
            user_role = 'team-member'    
            
    comment = ProjectComment(project_id=project_id, user_id=current_user.id, content=content, comment_type=comment_type, label=label if user_role == 'owner' else None, user_role=user_role)  # type: ignore
    
    db.session.add(comment)
    db.session.flush()  # Get comment.id before committing
    
    # Handle multiple image uploads
    if 'images' in request.files:
        files = request.files.getlist('images')
        for file in files:
            if file and file.filename != '' and allowed_file(file.filename):
                ext = os.path.splitext(file.filename)[1]
                filename = str(uuid.uuid4()) + ext
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                img = ProjectCommentImage()
                img.comment_id = comment.id
                img.image_path = filename
                db.session.add(img)
    
    db.session.commit()
    
    return jsonify({
        'id': comment.id,
        'author_id': comment.user_id,
        'author_name': comment.author.name,
        'author_email': comment.author.email,
        'content': comment.content,
        'comment_type': comment.comment_type,
        'label': comment.label,
        'user_role': comment.user_role,
        'created_at': comment.created_at.isoformat(),
        'images': [{'id': img.id, 'url': f'/static/uploads/{img.image_path}'} for img in comment.images],
    }), 201


@views.route('/api/project/<int:project_id>/comments/<int:comment_id>', methods=['DELETE'])
def delete_project_comment(project_id, comment_id):
    """Delete a comment (comment author OR project owner)"""
    err = require_login()
    if err:
        return err
    
    project = Project.query.get_or_404(project_id)
    comment = ProjectComment.query.get_or_404(comment_id)
    current_user = get_current_user()
     
    # ─── FIXED: REMOVED THE PREMATURE BLOCK HERE ───

    if comment.project_id != project_id:
        return jsonify({'error': 'Comment not found in this project'}), 404
    
    # ─── This check handles both conditions perfectly ───
    # It allows the action ONLY if the user is either the comment author OR the project owner
    if current_user.id != comment.user_id and current_user.id != project.user_id:
        return jsonify({'error': 'You do not have permission to delete this comment'}), 403
    
    # Delete associated images from disk
    for img in comment.images:
        file_path = os.path.join(UPLOAD_FOLDER, img.image_path)
        if os.path.exists(file_path):
            os.remove(file_path)

# 1. Update the comment text to the placeholder message
    comment.content = "This message was deleted."
    
    # 2. Optional: Set a flag if your model has an 'is_deleted' column
    if hasattr(comment, 'is_deleted'):
        comment.is_deleted = True

    # 3. Clear attached images so they don't linger on a deleted message
    if hasattr(comment, 'images'):
        for img in comment.images:
            db.session.delete(img)
    

    db.session.commit()
    
    return jsonify({'success': 'Comment deleted'})


@views.route('/api/project/<int:project_id>/comments/<int:comment_id>', methods=['PUT'])
def edit_project_comment(project_id, comment_id):
    """Edit a comment (comment author only)"""
    err = require_login()
    if err:
        return err
    
    comment = ProjectComment.query.get_or_404(comment_id)
    current_user = get_current_user()
    
    if comment.project_id != project_id:
        return jsonify({'error': 'Comment not found in this project'}), 404
    
    if current_user.id != comment.user_id:
        return jsonify({'error': 'You can only edit your own comments'}), 403
    
    data = request.get_json(silent=True) or {}
    new_content = data.get('content', '').strip()
    
    if not new_content:
        return jsonify({'error': 'Comment content cannot be empty'}), 400
    
    comment.content = new_content
    db.session.commit()
    
    return jsonify({
        'id': comment.id,
        'content': comment.content,
        'updated_at': comment.updated_at.isoformat(),
    })


@views.route('/api/project/<int:project_id>/comments/<int:comment_id>/images/<int:image_id>', methods=['DELETE'])
def delete_comment_image(project_id, comment_id, image_id):
    """Delete a single image from a comment (comment author only)"""
    err = require_login()
    if err:
        return err

    comment = ProjectComment.query.get_or_404(comment_id)
    current_user = get_current_user()

    if comment.project_id != project_id:
        return jsonify({'error': 'Comment not found in this project'}), 404

    if current_user.id != comment.user_id:
        return jsonify({'error': 'You can only edit your own comments'}), 403

    img = ProjectCommentImage.query.get_or_404(image_id)
    if img.comment_id != comment_id:
        return jsonify({'error': 'Image not found in this comment'}), 404

    file_path = os.path.join(UPLOAD_FOLDER, img.image_path)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(img)
    db.session.commit()
    return jsonify({'success': 'Image deleted'})


@views.route('/api/project/<int:project_id>/comments/<int:comment_id>/images', methods=['POST'])
def add_comment_images(project_id, comment_id):
    """Add new images to an existing comment (comment author only)"""
    err = require_login()
    if err:
        return err

    comment = ProjectComment.query.get_or_404(comment_id)
    current_user = get_current_user()

    if comment.project_id != project_id:
        return jsonify({'error': 'Comment not found in this project'}), 404

    if current_user.id != comment.user_id:
        return jsonify({'error': 'You can only edit your own comments'}), 403

    if 'images' not in request.files:
        return jsonify({'error': 'No images provided'}), 400

    added = []
    files = request.files.getlist('images')
    for file in files:
        if file and file.filename != '' and allowed_file(file.filename):
            ext = os.path.splitext(file.filename)[1]
            filename = str(uuid.uuid4()) + ext
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            img = ProjectCommentImage()
            img.comment_id = comment.id
            img.image_path = filename
            db.session.add(img)
            db.session.flush()
            added.append({'id': img.id, 'url': f'/static/uploads/{filename}'})

    db.session.commit()
    return jsonify({'success': True, 'images': added})


@views.route('/api/project/<int:project_id>/comments/<int:comment_id>/label', methods=['PUT'])
def update_comment_label(project_id, comment_id):
    """Update comment label and type (owner only)"""
    err = require_login()
    if err:
        return err
    
    project = Project.query.get_or_404(project_id)
    comment = ProjectComment.query.get_or_404(comment_id)
    current_user = get_current_user()
    
    # Only owner can update labels
    if current_user.id != project.user_id:
        return jsonify({'error': 'Only project owner can update labels'}), 403
    
    if comment.project_id != project_id:
        return jsonify({'error': 'Comment not found in this project'}), 404
    
    data = request.get_json(silent=True) or {}
    label = data.get('label')
    
    if label:
        comment.label = label
    
    db.session.commit()
    
    return jsonify({
        'id': comment.id,
        'label': comment.label,
        'comment_type': comment.comment_type,
    })


@views.route('/api/project/<int:project_id>/comments/<int:comment_id>/move', methods=['PUT'])
def move_comment_type(project_id, comment_id):
    """Move comment to different type (owner only)"""
    err = require_login()
    if err:
        return err
    
    project = Project.query.get_or_404(project_id)
    comment = ProjectComment.query.get_or_404(comment_id)
    current_user = get_current_user()
    
    # Only owner can move comments
    if current_user.id != project.user_id:
        return jsonify({'error': 'Only project owner can move comments'}), 403
    
    if comment.project_id != project_id:
        return jsonify({'error': 'Comment not found in this project'}), 404
    
    data = request.get_json(silent=True) or {}
    new_type = data.get('comment_type', 'normal')
    
    if new_type not in ['normal', 'issue', 'suggestion']:
        return jsonify({'error': 'Invalid comment type'}), 400
    
    comment.comment_type = new_type
    # Label is preserved when moving to normal - it will be hidden in the UI
    # When moving back to issue/suggestion, the label will be visible again
    
    db.session.commit()
    
    return jsonify({
        'id': comment.id,
        'comment_type': comment.comment_type,
        'label': comment.label,
    })


@views.route('/api/comment-labels', methods=['GET'])
def get_comment_labels():
    """Get all available comment labels"""
    labels = CommentLabel.query.all()
    
    return jsonify([{
        'id': l.id,
        'name': l.name,
        'color': l.color,
        'description': l.description,
    } for l in labels])


@views.route('/api/comment-labels', methods=['POST'])
def create_comment_label():
    """Create a new comment label (admin/owner only)"""
    err = require_login()
    if err:
        return err
    
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    color = data.get('color', 'gray')
    description = data.get('description', '')
    
    if not name:
        return jsonify({'error': 'Label name is required'}), 400
    
    existing = CommentLabel.query.filter_by(name=name).first()
    if existing:
        return jsonify({'error': 'Label already exists'}), 400
    
    label = CommentLabel()
    label.name = name
    label.color = color
    label.description = description
    db.session.add(label)
    db.session.commit()
    
    return jsonify({
        'id': label.id,
        'name': label.name,
        'color': label.color,
        'description': label.description,
    }), 201

# 1. AI Suggestions (home page) - based on user interests/skills
# 2. Similar Projects (project page) - based on a reference project

def _calculate_unified_match_score(
    candidate_project,
    reference_data=None,
    user_interests=None,
    user_skills=None,
    mode='ai'
):
    """
    Unified matching algorithm for both AI suggestions and similar projects.
    
    Args:
        candidate_project: Project object to score
        reference_data: Dict with keys: 'languages', 'description' (for similar projects mode)
        user_interests: List of user interests (for AI suggestions mode)
        user_skills: List of user skills (for AI suggestions mode)
        mode: 'ai' for AI suggestions or 'similar' for similar projects
    
    Returns:
        Score from 0-100 representing project relevance
    """
    
    STOPWORDS = {
        'the', 'a', 'an', 'and', 'or', 'in', 'on', 'is', 'to', 'for', 'of',
        'with', 'that', 'this', 'it', 'as', 'are', 'was', 'be', 'from', 'at',
        'by', 'we', 'our', 'your', 'not', 'has', 'have', 'will', 'can', 'i',
        'its', 'an', 'using', 'used', 'use', 'based', 'built', 'build',
        'project', 'help', 'need', 'team', 'member', 'members'
    }
    
    PROGRAMMING_LANGUAGES = {
        'python': ['python', 'py'],
        'javascript': ['javascript', 'js'],
        'typescript': ['typescript', 'ts'],
        'java': ['java'],
        'c++': ['c++', 'cpp'],
        'c#': ['c#', 'csharp', '.net', 'dotnet'],
        'php': ['php'],
        'ruby': ['ruby', 'rails'],
        'go': ['go', 'golang'],
        'rust': ['rust'],
        'kotlin': ['kotlin'],
        'swift': ['swift'],
        'sql': ['sql', 'plsql', 'mysql', 'postgres', 'postgresql'],
        'html': ['html', 'html5'],
        'css': ['css', 'scss', 'sass', 'less'],
        'react': ['react', 'reactjs', 'react.js'],
        'vue': ['vue', 'vuejs', 'vue.js'],
        'angular': ['angular', 'angularjs'],
        'nodejs': ['nodejs', 'node.js', 'node'],
        'django': ['django'],
        'flask': ['flask'],
        'spring': ['spring', 'springboot', 'spring boot'],
        'docker': ['docker'],
        'kubernetes': ['kubernetes', 'k8s'],
        'terraform': ['terraform'],
    }
    
    interest_keywords = {
        'web development': ['web', 'frontend', 'backend', 'react', 'vue', 'django', 'flask', 'nodejs', 'node.js', 'express', 'html', 'css', 'javascript', 'typescript', 'responsive', 'api', 'rest', 'graphql'],
        'mobile development': ['mobile', 'ios', 'android', 'flutter', 'react native', 'swift', 'kotlin', 'app', 'native', 'cross-platform'],
        'ai/ml': ['ai', 'ml', 'machine learning', 'deep learning', 'tensorflow', 'pytorch', 'nlp', 'cv', 'neural', 'model', 'algorithm', 'prediction'],
        'data science': ['data', 'science', 'analytics', 'pandas', 'numpy', 'visualization', 'dashboard', 'bi', 'warehouse', 'etl', 'spark'],
        'devops': ['devops', 'docker', 'kubernetes', 'ci/cd', 'jenkins', 'automation', 'infrastructure', 'deployment', 'pipeline'],
        'cloud': ['cloud', 'aws', 'azure', 'gcp', 'google cloud', 'serverless', 'lambda', 'ec2', 'rds'],
        'blockchain': ['blockchain', 'crypto', 'cryptocurrency', 'web3', 'ethereum', 'smart contract', 'solidity'],
        'iot': ['iot', 'embedded', 'arduino', 'raspberry', 'sensor', 'microcontroller', 'hardware'],
        'python': ['python', 'django', 'flask', 'pandas', 'numpy', 'scikit', 'jupyter', 'fastapi'],
        'java': ['java', 'spring', 'springboot', 'android', 'maven', 'gradle', 'microservices'],
        'c++': ['c++', 'cpp', 'gaming', 'graphics', 'performance', 'embedded', 'real-time'],
        'c#': ['c#', 'csharp', '.net', 'dotnet', 'unity', 'windows', 'blazor', 'aspnet'],
        'javascript': ['javascript', 'js', 'nodejs', 'node.js', 'react', 'vue', 'angular', 'typescript'],
        'database': ['database', 'sql', 'mongodb', 'postgres', 'postgresql', 'mysql', 'redis', 'cassandra', 'elastic'],
        'design': ['design', 'ui', 'ux', 'figma', 'adobe', 'photoshop', 'wireframe', 'prototype'],
        'security': ['security', 'encryption', 'cryptography', 'penetration', 'authentication', 'authorization', 'oauth', 'jwt'],
    }
    
    score = 0
    candidate_langs = (candidate_project.languages or '').lower()
    candidate_desc = (candidate_project.description or '').lower()
    candidate_roles = (candidate_project.roles_needed or '').lower()
    
    candidate_langs_set = set(l.strip().lower() for l in candidate_langs.split(',') if l.strip())
    candidate_desc_words = set(w for w in candidate_desc.split() if w not in STOPWORDS and len(w) > 2)
    
    if mode == 'similar':
        # SIMILAR PROJECTS MODE: Compare with reference project
        ref_langs = (reference_data.get('languages', '') or '').lower()
        ref_desc = (reference_data.get('description', '') or '').lower()
        
        ref_langs_set = set(l.strip().lower() for l in ref_langs.split(',') if l.strip())
        ref_desc_words = set(w for w in ref_desc.split() if w not in STOPWORDS and len(w) > 2)
        
        # Language overlap (30 pts max)
        lang_overlap = len(candidate_langs_set & ref_langs_set)
        lang_score = min(lang_overlap * 15, 30)
        score += lang_score
        
        # Description keyword overlap (25 pts max)
        if ref_desc_words and candidate_desc_words:
            desc_overlap = len(candidate_desc_words & ref_desc_words)
            desc_score = min(desc_overlap * 3, 25)
            score += desc_score
        
        # User interests bonus (20 pts max) - if user logged in
        if user_interests:
            user_interests_lower = [i.lower() for i in user_interests]
            combined_text = candidate_langs + ' ' + candidate_desc
            interest_hits = 0
            for interest in user_interests_lower:
                keywords = interest_keywords.get(interest, [])
                for keyword in keywords:
                    if keyword in combined_text:
                        interest_hits += 1
            
            interest_score = min(interest_hits * 5, 20)
            score += interest_score
        
        # Baseline score of 15 to ensure visibility
        score = min(100, 15 + score)
        
    else:  # mode == 'ai'
        # AI SUGGESTIONS MODE: Compare with user interests/skills
        if not user_interests:
            return 0
        
        user_interests_lower = [i.lower() for i in user_interests]
        
        # Factor 1: Direct Programming Language Matching (35 pts max)
        language_match_bonus = 0
        for interest in user_interests_lower:
            if interest in PROGRAMMING_LANGUAGES:
                lang_variants = PROGRAMMING_LANGUAGES[interest]
                for variant in lang_variants:
                    if variant in candidate_langs:
                        language_match_bonus += 12
            
            if interest in candidate_langs:
                language_match_bonus += 15
        
        for lang_name, lang_variants in PROGRAMMING_LANGUAGES.items():
            for variant in lang_variants:
                if variant in candidate_langs:
                    if lang_name in user_interests_lower or lang_name.lower() in ' '.join(user_interests_lower):
                        language_match_bonus += 6
        
        language_match_bonus = min(language_match_bonus, 35)
        score += language_match_bonus
        
        # Factor 2: Direct Interest Keyword Matching (30 pts max)
        interest_keyword_hits = set()
        for interest in user_interests_lower:
            keywords = interest_keywords.get(interest, [])
            for keyword in keywords:
                if keyword in candidate_desc or keyword in candidate_langs:
                    interest_keyword_hits.add(keyword)
        
        interest_match_score = min(len(interest_keyword_hits) * 2, 30)
        score += interest_match_score
        
        # Factor 3: Language Overlap with Interest Keywords (20 pts max)
        language_keyword_score = 0
        for interest in user_interests_lower:
            keywords = interest_keywords.get(interest, [])
            for keyword in keywords:
                for proj_lang in candidate_langs_set:
                    if keyword in proj_lang or proj_lang in keyword:
                        language_keyword_score += 6
        
        language_keyword_score = min(language_keyword_score, 20)
        score += language_keyword_score
        
        # Factor 4: Description Quality & Keyword Density (10 pts max)
        if candidate_desc:
            desc_keyword_matches = 0
            for interest in user_interests_lower:
                keywords = interest_keywords.get(interest, [])
                for keyword in keywords:
                    keyword_words = set(keyword.split())
                    if keyword_words & candidate_desc_words:
                        desc_keyword_matches += 1
            
            desc_match_score = min(desc_keyword_matches * 2, 10)
            score += desc_match_score
        
        # Factor 5: Skills-to-Roles Alignment Bonus (5 pts max)
        if user_skills and candidate_roles:
            user_skills_lower = [s.lower() for s in user_skills]
            skills_in_roles = 0
            for skill in user_skills_lower:
                if skill in candidate_roles:
                    skills_in_roles += 1
            
            skills_bonus = min(skills_in_roles * 2, 5)
            score += skills_bonus
        
        # Precision filters
        if score > 70:
            pass  # High quality, keep as is
        elif score < 30:
            score = max(score, 10)  # Minimum 10% for showing
        
        score = min(100, max(0, score))
    
    return int(score)





@views.route('/api/ai-suggestions', methods=['GET'])
def get_ai_suggestions():
    """
    Get AI-powered project suggestions based on user interests and skills.
    Uses the unified matching algorithm.
    """
    err = require_login()
    if err:
        return err
    
    email = session.get('user_email')
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Parse user interests using the shared function
    interests_data = parse_interests(user.interests)
    user_interests = interests_data.get('dev_interests', []) + interests_data.get('lang_interests', [])
    
    if not user_interests:
        return jsonify({
            'success': True,
            'user_interests': [],
            'suggestions': [],
            'total': 0,
            'message': 'Please set your interests to get suggestions',
            'algorithm_version': 'unified-v1'
        })
    
    # Get user's skills for enhanced matching
    my_skills = [s.skill for s in Skill.query.filter_by(user_id=user.id).all()]
    
    # Get projects already suggested to this user
    already_suggested = db.session.query(Suggestion.project_id).filter_by(user_id=user.id).all()
    already_suggested_ids = [s[0] for s in already_suggested]
    
    # Get all projects from OTHER users (with quality filtering)
    all_projects = Project.query.filter(
        Project.user_id != user.id,
        ~Project.id.in_(already_suggested_ids),
        Project.status != 'Archived',
        Project.project_name != '',
        (Project.languages != '') | (Project.description != '')
    ).all()
    
    # Score projects using unified algorithm in 'ai' mode
    scored_projects = []
    for project in all_projects:
        match_score = _calculate_unified_match_score(
            candidate_project=project,
            user_interests=user_interests,
            user_skills=my_skills,
            mode='ai'
        )
        
        if match_score >= 30:
            scored_projects.append((project, match_score))
    
    # Sort by score (descending), then by project activity (newer first)
    scored_projects.sort(key=lambda x: (-x[1], -x[0].created_at.timestamp()))
    
    # Return top 12 suggestions
    result = []
    for project, match_score in scored_projects[:12]:
        owner = User.query.get(project.user_id)
        
        # Generate contextual match reason
        match_reason = 'Matches your interests'
        if match_score >= 80:
            match_reason = 'Excellent match for your profile'
        elif match_score >= 70:
            match_reason = 'Strong match for your skills'
        elif match_score >= 50:
            match_reason = 'Good match for your interests'
        
        result.append({
            'id': project.id,
            'project_id': project.id,
            'project_name': project.project_name,
            'description': project.description,
            'owner_name': owner.name if owner else 'Unknown',
            'owner_id': project.user_id,
            'status': project.status,
            'contributors': project.contributors or 0,
            'languages': project.languages,
            'roles_needed': project.roles_needed,
            'match_reason': match_reason,
            'match_score': int(match_score),
        })
    
    return jsonify({
        'success': True,
        'user_interests': user_interests,
        'suggestions': result,
        'total': len(result)
    })


# --- API Endpoint: Get user profile by ID ---
@views.route('/api/user/<int:user_id>/profile', methods=['GET'])
def get_public_user_profile(user_id):
    """Get public profile information for a specific user"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    settings = user.settings
    is_private = settings and settings.profile_visibility == 'private'
    
    current_user = get_current_user()
    current_user_id = current_user.id if current_user else None
    
    if is_private and current_user_id != user.id:
        return jsonify({'error': 'This profile is private', 'is_private': True}), 403
    
    skills = Skill.query.filter_by(user_id=user.id).all()
    badges = Badge.query.filter_by(user_id=user.id).all()
    
    avatar_url = f"/static/uploads/{user.avatar_path}" if user.avatar_path else ''
    interests_list = [i.strip() for i in user.interests.split(',') if i.strip()] if user.interests else []

    return jsonify({
        'id': user.id,
        'email': user.email,
        'name': user.name,
        'faculty': user.faculty,
        'bio': user.bio or '',
        'avatar_url': avatar_url,
        'rank': user.rank,
        'karma': user.karma,
        'skills': [s.skill for s in skills],
        'badges': [b.badge for b in badges],
        'interests': interests_list,
    })


# --- API Endpoint: Get user's projects by ID ---
@views.route('/api/user/<int:user_id>/projects', methods=['GET'])
def get_user_projects(user_id):
    """Get all projects created and joined by a specific user"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    settings = user.settings
    is_private = settings and settings.profile_visibility == 'private'
    
    current_user = get_current_user()
    current_user_id = current_user.id if current_user else None
    
    if is_private and current_user_id != user.id:
        return jsonify({'error': 'This profile is private'}), 403
    
    # Get projects created by user
    owned_projects = Project.query.filter_by(user_id=user.id).order_by(
        Project.created_at.desc()
    ).all()
    
    # Get projects joined by user
    joined_projects = user.joined_projects
    
    result = {
        'owned_projects': [{
            'id': p.id,
            'project_name': p.project_name,
            'description': p.description,
            'status': p.status,
            'contributors': p.contributors,
            'created_at': p.created_at.isoformat(),
            'roles_needed': p.roles_needed,
        } for p in owned_projects],
        'joined_projects': [{
            'id': p.id,
            'project_name': p.project_name,
            'description': p.description,
            'status': p.status,
            'contributors': p.contributors,
            'created_at': p.created_at.isoformat(),
            'roles_needed': p.roles_needed,
        } for p in joined_projects],
    }
    
    return jsonify(result)


# --- Route: View user profile page ---
@views.route('/user/<int:user_id>/page')
def view_user_profile_page(user_id):
    """Display a user's profile page"""
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('views.home'))
    
    return render_template("Profile.html", view_user_id=user_id)


@views.route('/api/project/<int:project_id>/similar', methods=['GET'])
def get_similar_projects(project_id):
    """
    Get projects similar to the given project.
    Uses the unified matching algorithm.
    Includes user interests for personalization if logged in.
    """
    project = Project.query.get_or_404(project_id)

    # Detect logged-in user and their interests
    user = None
    user_interests = []
    if 'user_email' in session:
        user = User.query.filter_by(email=session['user_email']).first()
        if user and user.interests:
            user_interests = [i.strip().lower() for i in user.interests.split(',') if i.strip()]

    # Reference data from the current project
    reference_data = {
        'languages': project.languages,
        'description': project.description
    }

    # Candidate projects: exclude self
    query = Project.query.filter(Project.id != project_id)
    
    # Exclude projects owned by the current user if logged in
    if user:
        query = query.filter(Project.user_id != user.id)
    
    all_projects = query.all()

    # Score projects using unified algorithm in 'similar' mode
    scored = []
    for p in all_projects:
        match_score = _calculate_unified_match_score(
            candidate_project=p,
            reference_data=reference_data,
            user_interests=user_interests if user else None,
            mode='similar'
        )
        
        scored.append((p, match_score))

    # Sort: highest score first, then newest
    scored.sort(key=lambda x: (-x[1], -x[0].created_at.timestamp()))

    result = []
    for p, score in scored[:5]:
        owner = User.query.get(p.user_id)
        result.append({
            'id':           p.id,
            'project_name': p.project_name,
            'description':  p.description,
            'owner_name':   owner.name if owner else 'Unknown',
            'status':       p.status,
            'languages':    p.languages,
            'roles_needed': p.roles_needed,
            'match_score':  score,
        })

    return jsonify({'similar': result, 'total': len(result), 'algorithm_version': 'unified-v1'})


@views.route('/api/save-interest', methods=['POST'])
def save_interest():
    """
    Save or update user's project interests
    """
    err = require_login()
    if err:
        return err
    
    email = session.get('user_email')
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json(silent=True) or {}
    interests = data.get('interests', [])
    
    if not interests:
        return jsonify({'error': 'At least one interest must be selected'}), 400
    
    # Save interests as comma-separated string
    user.interests = ','.join(interests)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Interests updated successfully',
        'interests': interests
    })

# =====================================================================
# API: Community Timeline Posts 
# =====================================================================

@views.route('/api/community_posts', methods=['GET'])
def get_community_posts():
    current_user = get_current_user()
    current_user_id = current_user.id if current_user else None
    filter_type = request.args.get('filter', 'all')
    
    query = CommunityPost.query
    if filter_type == 'questions':
        query = query.filter_by(category='Question')
    elif filter_type == 'discussions':
        query = query.filter_by(category='Discussion')
    elif filter_type == 'posts':
        query = query.filter_by(category='Posts')
    elif filter_type == 'liked' and current_user_id:
        query = query.join(CommunityPostLike).filter(CommunityPostLike.user_id == current_user_id)
    elif filter_type == 'saved' and current_user_id:
        query = query.join(CommunityPostFavorite).filter(CommunityPostFavorite.user_id == current_user_id)

    posts = query.order_by(CommunityPost.created_at.desc()).limit(30).all()
    
    result = []
    for p in posts:
        proj_data = None
        if p.attached_project:
            proj_data = {'id': p.attached_project.id, 'name': p.attached_project.project_name}
            
        like_count = len(p.likes)
        fav_count = len(p.favorites)
        comment_count = len(p.comments)
        
        user_liked = False
        user_faved = False
        if current_user_id:
            user_liked = any(like.user_id == current_user_id for like in p.likes)
            user_faved = any(fav.user_id == current_user_id for fav in p.favorites)
            
        image_urls = [f"/static/uploads/{img.image_path}" for img in p.images]
        if p.image_path and f"/static/uploads/{p.image_path}" not in image_urls:
            image_urls.insert(0, f"/static/uploads/{p.image_path}")
            
        result.append({
            'id': p.id,
            'user_name': p.author.name if p.author else 'Unknown',
            'is_owner': current_user_id == p.user_id,
            'content': p.content,
            'category': p.category,
            'created_at': p.created_at.isoformat(),
            'image_urls': image_urls,
            'link_url': p.link_url,
            'attached_project': proj_data,
            'like_count': like_count,
            'fav_count': fav_count,
            'comment_count': comment_count,
            'user_liked': user_liked,
            'user_faved': user_faved
        })
    return jsonify(result)

@views.route('/api/community_posts', methods=['POST'])
def create_community_post():
    err = require_login()
    if err: return err
    
    current_user = get_current_user()
    content = request.form.get('content', '').strip()
    category = request.form.get('category', 'Posts')
    link_url = request.form.get('link_url', '').strip()
    attached_project_id = request.form.get('attached_project_id')
    
    if not content: return jsonify({'error': 'Post content cannot be empty'}), 400
    
    if not attached_project_id or not attached_project_id.isdigit():
        return jsonify({'error': 'You must attach a project to make a post.'}), 400
        
    proj = Project.query.get(int(attached_project_id))
    if not proj:
        return jsonify({'error': 'The selected project does not exist.'}), 404
        
    post = CommunityPost(
        user_id=current_user.id, 
        content=content, 
        category=category,
        attached_project_id=proj.id
    )
    if link_url: post.link_url = link_url
        
    if 'images' in request.files:
        import uuid
        files = request.files.getlist('images')
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"post_{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(current_app.config.get('UPLOAD_FOLDER', UPLOAD_FOLDER), filename))
                img_record = CommunityPostImage(image_path=filename)
                post.images.append(img_record)

    db.session.add(post)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Posted successfully'})

@views.route('/api/community_posts/<int:post_id>', methods=['DELETE'])
def delete_community_post(post_id):
    err = require_login()
    if err: return err
    current_user = get_current_user()
    post = CommunityPost.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    db.session.delete(post)
    db.session.commit()
    return jsonify({'success': True})

@views.route('/api/community_posts/<int:post_id>/like', methods=['POST'])
def toggle_community_post_like(post_id):
    err = require_login()
    if err: return err
    current_user = get_current_user()
    existing_like = CommunityPostLike.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing_like:
        db.session.delete(existing_like)
        liked = False
    else:
        db.session.add(CommunityPostLike(user_id=current_user.id, post_id=post_id))
        liked = True
    db.session.commit()
    count = CommunityPostLike.query.filter_by(post_id=post_id).count()
    return jsonify({'success': True, 'liked': liked, 'like_count': count})

@views.route('/api/community_posts/<int:post_id>/favorite', methods=['POST'])
def toggle_community_post_favorite(post_id):
    err = require_login()
    if err: return err
    current_user = get_current_user()
    existing_fav = CommunityPostFavorite.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing_fav:
        db.session.delete(existing_fav)
        faved = False
    else:
        db.session.add(CommunityPostFavorite(user_id=current_user.id, post_id=post_id))
        faved = True
    db.session.commit()
    count = CommunityPostFavorite.query.filter_by(post_id=post_id).count()
    return jsonify({'success': True, 'faved': faved, 'fav_count': count})

@views.route('/api/community_posts/<int:post_id>/comments', methods=['GET', 'POST'])
def manage_community_post_comments(post_id):
    err = require_login()
    if err: return err
    current_user = get_current_user()
    
    if request.method == 'GET':
        comments = CommunityPostComment.query.filter_by(post_id=post_id).order_by(CommunityPostComment.created_at.asc()).all()
        result = [{
            'id': c.id,
            'user_name': c.author.name,
            'is_owner': c.user_id == current_user.id,
            'content': c.content,
            'parent_id': c.parent_id,
            'created_at': c.created_at.isoformat(),
            'image_urls': [f"/static/uploads/{img.image_path}" for img in c.images]
        } for c in comments]
        return jsonify(result)
        
    if request.method == 'POST':
        if request.content_type and 'multipart' in request.content_type:
            content = request.form.get('content', '').strip()
            parent_id = request.form.get('parent_id')
        else:
            data = request.get_json(silent=True) or {}
            content = data.get('content', '').strip()
            parent_id = data.get('parent_id')
        
        if not content: return jsonify({'error': 'Comment cannot be empty'}), 400
        if parent_id and str(parent_id).isdigit(): parent_id = int(parent_id)
        else: parent_id = None
            
        comment = CommunityPostComment(post_id=post_id, user_id=current_user.id, content=content, parent_id=parent_id)
        
        if 'images' in request.files:
            import uuid
            files = request.files.getlist('images')
            for file in files:
                if file and file.filename and allowed_file(file.filename):
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    filename = f"c_{uuid.uuid4().hex}.{ext}"
                    file.save(os.path.join(current_app.config.get('UPLOAD_FOLDER', UPLOAD_FOLDER), filename))
                    img = CommunityPostCommentImage(image_path=filename)
                    comment.images.append(img)
                    
        db.session.add(comment)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Comment added'})

@views.route('/api/community_posts/<int:post_id>/comments/<int:comment_id>', methods=['DELETE'])
def delete_community_post_comment(post_id, comment_id):
    err = require_login()
    if err: return err
    current_user = get_current_user()
    c = CommunityPostComment.query.get_or_404(comment_id)
    if c.post_id != post_id: return jsonify({'error': 'Mismatch'}), 400
    if c.user_id != current_user.id: return jsonify({'error': 'Unauthorized'}), 403
    db.session.delete(c)
    db.session.commit()
    return jsonify({'success': True})


@views.route('/hottest')
def hottest_projects():
    all_projects = Project.query.filter(Project.status != 'Archived').all()
    
    all_time_data = []
    trending_data = []
    
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    
    for p in all_projects:
        project_comment_count = ProjectComment.query.filter_by(project_id=p.id).count()
        views = p.views or 0
        
        attached_posts = CommunityPost.query.filter_by(attached_project_id=p.id).all()
        post_ids = [post.id for post in attached_posts]
        post_like_count = 0
        if post_ids:
            post_like_count = CommunityPostLike.query.filter(CommunityPostLike.post_id.in_(post_ids)).count()
            
        project_star_count = ProjectStar.query.filter_by(project_id=p.id).count()
            
        primary_lang = p.languages.split(',')[0].strip() if p.languages else 'N/A'
        
        total_score = (views * 1) + (post_like_count * 5) + (project_comment_count * 1) + (project_star_count * 20)
        
        project_dict_all_time = {
            'id': p.id,
            'title': p.project_name,          
            'description': p.description,
            'language': primary_lang,
            'views': views,            
            'comments': project_comment_count,
            'likes': post_like_count,  
            'saves': project_star_count,  
            'total_score': total_score
        }
        all_time_data.append(project_dict_all_time)

        recent_comments = ProjectComment.query.filter(
            ProjectComment.project_id == p.id,
            ProjectComment.created_at >= seven_days_ago
        ).count()
        
        recent_views = ProjectViewLog.query.filter(
            ProjectViewLog.project_id == p.id,
            ProjectViewLog.created_at >= seven_days_ago
        ).count()
        
        recent_likes = 0
        if post_ids:
            recent_likes = CommunityPostLike.query.filter(
                CommunityPostLike.post_id.in_(post_ids),
                CommunityPostLike.created_at >= seven_days_ago
            ).count()
            
        recent_stars = ProjectStar.query.filter(
            ProjectStar.project_id == p.id,
            ProjectStar.created_at >= seven_days_ago
        ).count()
            
        trending_score = (recent_views * 1) + (recent_likes * 5) + (recent_comments * 1) + (recent_stars * 20)
        
        if trending_score > 0:
            project_dict_trending = {
                'id': p.id,
                'title': p.project_name,          
                'description': p.description,
                'language': primary_lang,
                'views': views, 
                'comments': project_comment_count,
                'likes': post_like_count,  
                'saves': project_star_count,  
                'total_score': total_score,
                'trending_score': trending_score 
            }
            trending_data.append(project_dict_trending)
            
    top_all_time = sorted(all_time_data, key=lambda x: x['total_score'], reverse=True)[:10]
    top_trending = sorted(trending_data, key=lambda x: x['trending_score'], reverse=True)[:10]

    # =============================================================
    # 🏆 AUTO-ASSIGN HOTTEST / TRENDING BADGES
    # =============================================================
    # Collect owner IDs in each top-10 list
    top_all_time_owner_ids  = set()
    top_trending_owner_ids  = set()

    for entry in top_all_time:
        p = Project.query.get(entry['id'])
        if p:
            top_all_time_owner_ids.add(p.user_id)

    for entry in top_trending:
        p = Project.query.get(entry['id'])
        if p:
            top_trending_owner_ids.add(p.user_id)

    # Award to those in the list, revoke from those who dropped out
    all_users_with_badge = {b.user_id for b in Badge.query.filter(
        Badge.badge.in_(['Hottest Project', 'Trending Project'])).all()}

    affected_users = top_all_time_owner_ids | top_trending_owner_ids | all_users_with_badge
    for uid in affected_users:
        if uid in top_all_time_owner_ids:
            _award_badge(uid, 'Hottest Project')
        else:
            _revoke_badge(uid, 'Hottest Project')

        if uid in top_trending_owner_ids:
            _award_badge(uid, 'Trending Project')
        else:
            _revoke_badge(uid, 'Trending Project')

    db.session.commit()
    return render_template("Trending.html", all_time_projects=top_all_time, trending_projects=top_trending)

@views.route('/api/project/<int:project_id>/updates', methods=['GET', 'POST'])
def manage_project_updates(project_id):
    err = require_login()
    if err and request.method == 'POST': 
        return err

    project = Project.query.get_or_404(project_id)
    current_user = get_current_user()
    
    current_user_role = 'user'
    if current_user:
        if project.user_id == current_user.id:
            current_user_role = 'owner'
        else:
            member_record = ProjectMember.query.filter_by(project_id=project_id, user_id=current_user.id).first()
            if member_record:
                current_user_role = member_record.role

    if request.method == 'GET':
        updates = ProjectUpdate.query.filter_by(project_id=project_id).order_by(ProjectUpdate.created_at.desc()).all()
        result = []
        for u in updates:
            is_appr = getattr(u, 'is_approved', True)
            if is_appr is None:
                is_appr = True
                
            if is_appr or current_user_role in ['owner', 'admin'] or (current_user and u.user_id == current_user.id):
                images_data = []
                if hasattr(u, 'images'):
                    for img in u.images:
                        images_data.append({
                            'id': img.id,
                            'url': url_for('static', filename=f'uploads/{img.image_path}')
                        })

                result.append({
                    'id': u.id,
                    'title': u.title,
                    'status': u.status,
                    'content': u.content,
                    'author_name': u.author.name if u.author else 'Unknown',
                    'created_at': u.created_at.isoformat(),
                    'is_approved': is_appr,
                    'images': images_data  # 新增：将图片数据返回给前端
                })
        return jsonify(result)

    if request.method == 'POST':
        if current_user_role not in ['owner', 'admin', 'member']:
            return jsonify({'error': 'Only project members can post updates'}), 403

        if request.content_type and 'multipart' in request.content_type:
            title = request.form.get('title', '').strip()
            status = request.form.get('status', 'On Track')
            content = request.form.get('content', '').strip()
        else:
            data = request.get_json(silent=True) or {}
            title = data.get('title', '').strip()
            status = data.get('status', 'On Track')
            content = data.get('content', '').strip()

        if not title or not content:
            return jsonify({'error': 'Title and content are required'}), 400

        auto_approve = current_user_role in ['owner', 'admin']

        new_update = ProjectUpdate(
            project_id=project_id,
            user_id=current_user.id,
            title=title,
            status=status,
            content=content,
            is_approved=auto_approve
        )
        db.session.add(new_update)
        db.session.flush() 

        if 'images' in request.files:
            import uuid
            import os
            
            ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            def allowed_file(filename):
                return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

            files = request.files.getlist('images')
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'static/uploads')
            os.makedirs(upload_folder, exist_ok=True)
            
            for file in files:
                if file and file.filename != '' and allowed_file(file.filename):
                    ext = os.path.splitext(file.filename)[1]
                    filename = str(uuid.uuid4()) + ext
                    file.save(os.path.join(upload_folder, filename))
                    
                    try:
                        from .models import ProjectUpdateImage
                        img = ProjectUpdateImage(update_id=new_update.id, image_path=filename)
                        db.session.add(img)
                    except ImportError:
                        pass 

        db.session.commit()

        msg = 'Update posted successfully' if auto_approve else 'Update submitted for approval'
        return jsonify({'success': True, 'message': msg})
@views.route('/api/project/<int:project_id>/updates/<int:update_id>/<action>', methods=['POST'])
def review_project_update(project_id, update_id, action):
    err = require_login()
    if err: return err
    
    project = Project.query.get_or_404(project_id)
    current_user = get_current_user()
    
    is_owner = (project.user_id == current_user.id)
    is_admin = False
    if not is_owner:
        member_record = ProjectMember.query.filter_by(project_id=project_id, user_id=current_user.id).first()
        if member_record and member_record.role == 'admin':
            is_admin = True
            
    if not (is_owner or is_admin):
        return jsonify({'error': 'Unauthorized. Only project leads and admins can review updates.'}), 403
        
    update = ProjectUpdate.query.get_or_404(update_id)
    if update.project_id != project_id:
        return jsonify({'error': 'Update mismatch'}), 400
        
    if action == 'approve':
        update.is_approved = True
        db.session.commit()
        return jsonify({'success': True, 'message': 'Update approved and published.'})
    elif action == 'reject':
        db.session.delete(update)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Update rejected and removed.'})
    else:
        return jsonify({'error': 'Invalid action'}), 400


# =====================================================================
# ─── 管理员一键删除不良内容功能（ADMIN MODERATION） ───
# =====================================================================

def require_admin():
    """安全拦截：验证当前登录用户是否为管理员"""
    email = session.get('user_email')
    if not email:
        return jsonify({'error': 'Please log in first.'}), 401
    
    user = User.query.filter_by(email=email).first()
    if not user or not getattr(user, 'is_admin', False):
        return jsonify({'error': 'Access denied. Unauthorized admin account.'}), 403
    return None


# Reference: Flask-SQLAlchemy filtering - https://flask-sqlalchemy.palletsprojects.com/en/stable/queries/
@views.route('/admin/dashboard')
def admin_dashboard_page():
    """Render admin moderation panel with projects, comments, posts, and pending reports."""
    email = session.get('user_email')
    if not email:
        return redirect(url_for('views.api_login'))

    user = User.query.filter_by(email=email).first()


    if not user or not getattr(user, 'is_admin', False):
        return "Access Denied. Admins Only.", 403

    all_projects = Project.query.filter(
        Project.status != 'Archived',
        Project.status != 'Deleted',
        Project.status != 'Suspended'
    ).order_by(Project.created_at.desc()).all()
    all_comments = ProjectComment.query.order_by(ProjectComment.created_at.desc()).limit(50).all()
    all_posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).limit(50).all()

    pending_reports_raw = ContentReport.query.filter_by(status='pending').order_by(
        ContentReport.created_at.desc()
    ).all()
    pending_reports = _enrich_pending_reports(pending_reports_raw)

    recent_logs = AdminLog.query.order_by(AdminLog.created_at.desc()).limit(20).all()
    suspended_users = SuspendedUser.query.filter_by(is_active=True).all()

    return render_template(
        "admin_dashboard.html",
        projects=all_projects,
        comments=all_comments,
        posts=all_posts,
        pending_reports=pending_reports,
        pending_count=len(pending_reports),
        recent_logs=recent_logs,
        suspended_users=suspended_users,
        admin_user=user,
    )

@views.route('/api/timeline_feed', methods=['GET'])
def get_timeline_feed():
    current_user = get_current_user()
    current_user_id = current_user.id if current_user else None
    
    # 1. 提取当前用户所有关注（Star）的项目 ID 集合
    starred_project_ids = set()
    if current_user_id:
        from .models import ProjectStar, MYT  # 确保引入对应模型与区时
        stars = ProjectStar.query.filter_by(user_id=current_user_id).all()
        starred_project_ids = {s.project_id for s in stars}

    unified_feed = []
    # 统一采用模型的 MYT 区时作为当前时间基准，防止跨时区引发时差计算错误
    from .models import MYT
    now = datetime.now(MYT)

    # 2. 汇入数据源 A：社区讨论与提问帖子
    posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).limit(30).all()
    for p in posts:
        proj_id = p.attached_project_id
        # 核心权重一：只要项目在关注集合中，即赋予断层高优级别 (1)，否则为 (0)
        is_starred = 1 if (proj_id and proj_id in starred_project_ids) else 0
        
        # 计算发布时长差（小时）
        p_created = p.created_at.replace(tzinfo=MYT) if p.created_at.tzinfo is None else p.created_at
        age_hours = max(0.0, (now - p_created).total_seconds() / 3600.0)
        
        # 计算互动热度分
        like_count = len(p.likes)
        comment_count = len(p.comments)
        base_score = 20 + (like_count * 5) + (comment_count * 10)
        # 核心权重二：流内时间重力衰减
        feed_score = base_score / ((age_hours + 2) ** 1.5)
        
        image_urls = [f"/static/uploads/{img.image_path}" for img in p.images]
        
        unified_feed.append({
            'feed_id': f"post_{p.id}",
            'id': p.id,
            'feed_type': 'post',
            'category': p.category,
            'user_name': p.author.name if p.author else 'Unknown',
            'content': p.content,
            'created_at': p.created_at.isoformat(),
            'image_urls': image_urls,
            'link_url': p.link_url,
            'attached_project': {'id': p.attached_project.id, 'name': p.attached_project.project_name} if p.attached_project else None,
            'like_count': like_count,
            'comment_count': comment_count,
            'user_liked': any(like.user_id == current_user_id for like in p.likes) if current_user_id else False,
            'user_faved': any(fav.user_id == current_user_id for fav in p.favorites) if current_user_id else False,
            'is_starred': is_starred,
            'score': feed_score
        })

    # =========================================================================
    # 3. 汇入数据源 B：项目的官方更新进展 (ProjectUpdate)
    # =========================================================================
    if starred_project_ids: # 如果用户有关注的项目，才去查询更新
        updates = ProjectUpdate.query.filter(
            ProjectUpdate.is_approved == True,
            ProjectUpdate.project_id.in_(starred_project_ids) 
        ).order_by(ProjectUpdate.created_at.desc()).limit(20).all()
        
        for u in updates:
            is_starred = 1 
            
            u_created = u.created_at.replace(tzinfo=MYT) if u.created_at.tzinfo is None else u.created_at
            age_hours = max(0.0, (now - u_created).total_seconds() / 3600.0)
            
            base_score = 50
            feed_score = base_score / ((age_hours + 2) ** 1.5)
            
            # ✨ 新增：提取 Update 的图片 URL
            image_urls = [f"/static/uploads/{img.image_path}" for img in u.images] if hasattr(u, 'images') else []
            
            unified_feed.append({
                'feed_id': f"update_{u.id}",
                'id': u.id,
                'feed_type': 'update',
                'category': 'Project Update',
                'user_name': u.author.name if u.author else 'Unknown',
                'title': u.title,
                'status': u.status,
                'content': u.content,
                'image_urls': image_urls,  # ✨ 新增：将图片发给前端
                'created_at': u.created_at.isoformat(),
                'attached_project': {'id': u.project.id, 'name': u.project.project_name} if u.project else None,
                'is_starred': is_starred,
                'score': feed_score
            })
            
    # 4. 执行级联精准排序：reverse=True 确保 is_starred 从 1 到 0 递减，score 从高到低递减
    unified_feed.sort(key=lambda x: (x['is_starred'], x['score']), reverse=True)

    return jsonify(unified_feed[:30])

@views.route('/api/project/<int:project_id>/star', methods=['POST'])
def toggle_project_star(project_id):
    # 1. 验证用户是否登录 (请根据你实际 views.py 里获取登录用户的方法调整)
    email = session.get('user_email')
    if not email:
        return jsonify({'error': 'Please login to star a project.'}), 401
        
    current_user = User.query.filter_by(email=email).first()
    if not current_user:
        return jsonify({'error': 'User not found.'}), 404

    # 2. 验证项目是否存在
    project = Project.query.get_or_404(project_id)
    
    # 3. 检查是否已经收藏过
    existing_star = ProjectStar.query.filter_by(user_id=current_user.id, project_id=project.id).first()
    
    if existing_star:
        # 已经收藏过 -> 执行取消收藏 (Unlike)
        db.session.delete(existing_star)
        db.session.commit()
        is_starred = False
    else:
        # 尚未收藏 -> 执行收藏 (Like)
        new_star = ProjectStar(user_id=current_user.id, project_id=project.id)
        db.session.add(new_star)
        db.session.commit()
        is_starred = True
        
    # 4. 获取该项目最新的总收藏数，返回给前端实时更新 UI
    star_count = ProjectStar.query.filter_by(project_id=project.id).count()
    
    return jsonify({
        'success': True,
        'starred': is_starred,
        'star_count': star_count,
        'message': 'Project starred!' if is_starred else 'Project unstarred.'
    })
