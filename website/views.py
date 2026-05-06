import os
import random
import smtplib
import sys
import logging
from email.mime.text import MIMEText
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash, jsonify, session
from .models import Question, QuestionComment, QuestionFavorite, QuestionLike, db, User, Skill, Badge, Comment, Project, ProjectImage, Suggestion, ProjectComment, CommentLabel, QuestionCommentImage, QuestionImage, JoinRequest

views = Blueprint('views', __name__)


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

# --- ADDED: Auto-Email Sending Function ---
def send_otp_email(receiver_email, otp_code):
    # =====================================================================
    # ⚠️ 关键步骤: 在这里替换为你真实的 Gmail 邮箱和 16 位 Google App Password ⚠️
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

    own_projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.created_at.desc()).all()
    
    joined_projects = current_user.joined_projects

    return render_template("My_Projects.html", own_projects=own_projects, joined_projects=joined_projects)

@views.route('/profile')
def profile():
    return render_template("Profile.html")

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
    project = Project.query.get_or_404(project_id)
    return render_template("Project_Page.html", project=project, current_user=get_current_user())

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

        new_project = Project(
            user_id=current_user.id,
            project_name=name, 
            repo_url=repo, 
            languages=langs, 
            roles_needed=roles, 
            description=desc,
            status='Active'
        )

        db.session.add(new_project)
        db.session.commit()

        files = request.files.getlist('screenshots') 
        for file in files:
            if file and file.filename != '':
                ext = os.path.splitext(file.filename)[1]
                filename = str(uuid.uuid4()) + ext 
                
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                new_image = ProjectImage(filename=filename, project_id=new_project.id)
                db.session.add(new_image)

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

    is_owner = (project.user_id == current_user.id)
    is_member = (current_user in project.members)

    if not (is_owner or is_member):
        flash("Permission Denied: Only project owners and members can edit this project.", "error")
        return redirect(url_for('views.project_page', project_id=project.id))

    if request.method == 'POST':
        if is_owner:
            project.project_name = request.form.get('project_name')
            project.repo_url = request.form.get('repo_url')

        project.languages = request.form.get('languages')
        project.roles_needed = request.form.get('roles_needed')
        project.description = request.form.get('description')

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
                
                new_image = ProjectImage(filename=new_filename, project_id=project.id)
                db.session.add(new_image)

        db.session.commit()
        return redirect(url_for('views.project_page', project_id=project.id))

    return render_template("Edit_Project.html", project=project, current_user=current_user)

@views.route('/delete-project/<int:project_id>', methods=['POST'])
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    try:
        db.session.delete(project)
        db.session.commit()
        flash('Project deleted successfully!', category='success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting the project.', category='error')
        print(f"Error: {e}")
    return redirect(url_for('views.my_projects'))

@views.route('/api/register', methods=['POST'])
def api_register():
    data     = request.get_json(silent=True) or {}
    email    = data.get('email', '').strip().lower()
    name     = data.get('name', '').strip()
    password = data.get('password', '')
    interests = data.get('interests', [])

    if not email or not password or not name:
        return jsonify({'error': 'All fields are required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    if not (email.endswith('@mmu.edu.my') or email.endswith('@student.mmu.edu.my')):
        return jsonify({'error': 'Only MMU email addresses (@mmu.edu.my or @student.mmu.edu.my) are allowed'}), 400

    pw_hash = generate_password_hash(password)
    
# --- MODIFIED: Generate OTP ---
    otp_code = f"{random.randint(0, 999999):06d}"
    
    try:
        user = User(
            email=email, 
            name=name, 
            password_hash=pw_hash, 
            otp=otp_code,
            interests=','.join(interests) if interests else ''
        )
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
    
    interests_list = [i.strip() for i in user.interests.split(',') if i.strip()] if user.interests else []

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
        'interests':  interests_list,
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

    interests = data.get('interests')
    if interests is not None:
        user.interests = ','.join([i.strip() for i in interests if i.strip()])

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
    
    comment = Comment(user_id=user.id, comment=comment_text)
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
    
    projects = Project.query.filter_by(user_id=user.id).order_by(
        Project.created_at.desc()
    ).all()
    
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
    projects = Project.query.order_by(Project.created_at.desc()).all()
    
    return jsonify([{
        'id': p.id,
        'project_name': p.project_name,
        'description': p.description,
        'status': p.status,
        'contributors': p.contributors,
        'languages': p.languages,
        'created_at': p.created_at.isoformat(),
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
        suggestion = Suggestion(user_id=user.id, project_id=project_id, match_score=100)
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
    q = Question(user_id=user.id, title=title, body=body)

    # Handle optional multiple images
    if 'images' in request.files:
        files = request.files.getlist('images')
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"q_{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                img = QuestionImage(image_path=filename)
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
                img = QuestionImage(image_path=filename)
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
def delete_comment_image(image_id):
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
        db.session.add(QuestionLike(user_id=user.id, question_id=question_id))
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
        db.session.add(QuestionFavorite(user_id=user.id, question_id=question_id))
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
    c = QuestionComment(user_id=user.id, question_id=question_id, body=body, parent_id=parent_id)
    
    # Handle optional multiple images
    if 'images' in request.files:
        files = request.files.getlist('images')
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"c_{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                img = QuestionCommentImage(image_path=filename)
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
    if c.user_id != user.id:
        return jsonify({'error': 'Not authorised'}), 403

    db.session.delete(c)
    db.session.commit()
    return jsonify({'success': True})

@views.route('/delete-question/<int:id>')
def delete_confirm(id):
    question = Question.query.get_or_404(id) # Or your database logic
    return render_template("delete_question.html", question=question)


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
                img = QuestionCommentImage(image_path=filename)
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



@views.route('/api/project/<int:project_id>/add_member', methods=['POST'])
def add_member(project_id):
    err = require_login()
    if err: return err
    
    current_user = get_current_user()
    project = Project.query.get_or_404(project_id)

    # Security check: Only the project lead (creator) can add members
    if project.user_id != current_user.id:
        return jsonify({"error": "Unauthorized. Only the Project Lead can add members."}), 403

    data = request.get_json(silent=True) or {}
    email_to_add = data.get('email', '').strip().lower()

    if not email_to_add:
        return jsonify({"error": "Email is required"}), 400

    user_to_add = User.query.filter_by(email=email_to_add).first()

    if not user_to_add:
        return jsonify({"error": "User with this email not found"}), 404

    if user_to_add in project.members:
        return jsonify({"error": "User is already a member of this project"}), 400

    # Add the user to the project's members list
    project.members.append(user_to_add)
    db.session.commit()

    return jsonify({"success": "Member added successfully!", "user_name": user_to_add.name})


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
    if current_user in project.members:
        return jsonify({"error": "You are already a member of this project"}), 400
    
    # Check if request already exists
    existing_request = JoinRequest.query.filter_by(
        user_id=current_user.id,
        project_id=project_id
    ).first()
    
    if existing_request:
        if existing_request.status == 'pending':
            return jsonify({"error": "You have already sent a join request"}), 400
        elif existing_request.status == 'rejected':
            return jsonify({"error": "Your join request was rejected"}), 400
    
    # Create new join request
    join_request = JoinRequest(
        user_id=current_user.id,
        project_id=project_id,
        status='pending'
    )
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
    
    # Add user to project members
    user_to_add = User.query.get_or_404(join_request.user_id)
    if user_to_add not in project.members:
        project.members.append(user_to_add)
    
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
    } for c in comments])


@views.route('/api/project/<int:project_id>/comments', methods=['POST'])
def create_project_comment(project_id):
    """Create a new comment on a project"""
    err = require_login()
    if err:
        return err
    
    project = Project.query.get_or_404(project_id)
    current_user = get_current_user()
    
    data = request.get_json(silent=True) or {}
    content = data.get('content', '').strip()
    comment_type = data.get('comment_type', 'normal')  # 'normal', 'issue', 'suggestion'
    label = data.get('label', None)
    
    if not content:
        return jsonify({'error': 'Comment content is required'}), 400
    
    if comment_type not in ['normal', 'issue', 'suggestion']:
        return jsonify({'error': 'Invalid comment type'}), 400
    
    # Determine user role
    user_role = 'user'
    if current_user.id == project.user_id:
        user_role = 'owner'
    elif current_user in project.members:
        user_role = 'team-member'
    
    comment = ProjectComment(
        project_id=project_id,
        user_id=current_user.id,
        content=content,
        comment_type=comment_type,
        label=label if user_role == 'owner' else None,  # Only owner can set labels
        user_role=user_role
    )
    
    db.session.add(comment)
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
    }), 201


@views.route('/api/project/<int:project_id>/comments/<int:comment_id>', methods=['DELETE'])
def delete_project_comment(project_id, comment_id):
    """Delete a comment (owner only)"""
    err = require_login()
    if err:
        return err
    
    project = Project.query.get_or_404(project_id)
    comment = ProjectComment.query.get_or_404(comment_id)
    current_user = get_current_user()
    
    # Only owner can delete comments
    if current_user.id != project.user_id:
        return jsonify({'error': 'Only project owner can delete comments'}), 403
    
    if comment.project_id != project_id:
        return jsonify({'error': 'Comment not found in this project'}), 404
    
    db.session.delete(comment)
    db.session.commit()
    
    return jsonify({'success': 'Comment deleted'})


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
    # Reset label when moving to normal
    if new_type == 'normal':
        comment.label = None
    
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
    
    label = CommentLabel(name=name, color=color, description=description)
    db.session.add(label)
    db.session.commit()
    
    return jsonify({
        'id': label.id,
        'name': label.name,
        'color': label.color,
        'description': label.description,
    }), 201

# ─────────────────────────────────────────────────────────────────────────
# UNIFIED SUGGESTION SYSTEM - COMBINED MATCHING ALGORITHM
# ─────────────────────────────────────────────────────────────────────────
# This unified system handles both:
# 1. AI Suggestions (home page) - based on user interests/skills
# 2. Similar Projects (project page) - based on a reference project
# ─────────────────────────────────────────────────────────────────────────

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


def _calculate_match_score(user_interests, project_languages, project_description, user_skills=None, project_roles=None):
    """
    Calculate how well a project matches user interests with advanced precision scoring.
    
    Scoring factors:
    1. Direct programming language matching (35 pts max) - NEW!
    2. Direct interest keyword matching (30 pts max)
    3. Language overlap with interests (20 pts max)
    4. Description keyword alignment (10 pts max)
    5. Skills-to-roles alignment bonus (5 pts max)
    
    Returns a score from 0-100 for precise project recommendations.
    """
    
    # Programming language mapping - maps languages to development areas
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
    
    # Comprehensive keyword mapping for interests
    interest_keywords = {
        'web development': ['web', 'frontend', 'backend', 'react', 'vue', 'django', 'flask', 'nodejs', 'node.js', 'express', 'html', 'css', 'javascript', 'typescript', 'html5', 'responsive', 'api', 'rest', 'graphql'],
        'mobile development': ['mobile', 'ios', 'android', 'flutter', 'react native', 'swift', 'kotlin', 'app', 'native', 'cross-platform', 'xamarin'],
        'ai/ml': ['ai', 'ml', 'machine learning', 'deep learning', 'tensorflow', 'pytorch', 'nlp', 'cv', 'neural', 'neural network', 'model', 'algorithm', 'prediction', 'classifier', 'regression'],
        'data science': ['data', 'science', 'analytics', 'pandas', 'numpy', 'data analysis', 'visualization', 'dashboard', 'bi', 'warehouse', 'etl', 'spark', 'hadoop'],
        'devops': ['devops', 'docker', 'kubernetes', 'ci/cd', 'jenkins', 'automation', 'infrastructure', 'deployment', 'pipeline', 'monitoring', 'logging', 'terraform'],
        'cloud': ['cloud', 'aws', 'azure', 'gcp', 'google cloud', 'serverless', 'cloud computing', 'lambda', 'ec2', 'rds', 'storage', 'distributed'],
        'blockchain': ['blockchain', 'crypto', 'cryptocurrency', 'web3', 'ethereum', 'smart contract', 'solidity', 'dapp', 'defi', 'nft', 'web3.js'],
        'iot': ['iot', 'embedded', 'arduino', 'raspberry', 'sensor', 'microcontroller', 'hardware', 'firmware', 'real-time', 'edge'],
        'python': ['python', 'django', 'flask', 'pandas', 'numpy', 'scikit', 'jupyter', 'pipenv', 'poetry', 'asyncio', 'fastapi'],
        'java': ['java', 'spring', 'springboot', 'android', 'maven', 'gradle', 'jvm', 'microservices', 'orm', 'hibernate'],
        'c++': ['c++', 'cpp', 'gaming', 'graphics', 'performance', 'linux', 'embedded', 'real-time', 'unreal', 'opencv'],
        'c#': ['c#', 'csharp', '.net', 'dotnet', 'unity', 'windows', 'blazor', 'aspnet', 'asp.net', 'entity framework'],
        'javascript': ['javascript', 'js', 'nodejs', 'node.js', 'react', 'vue', 'angular', 'typescript', 'web'],
        'database': ['database', 'sql', 'mongodb', 'postgres', 'postgresql', 'mysql', 'redis', 'cassandra', 'elastic', 'nosql', 'db'],
        'design': ['design', 'ui', 'ux', 'figma', 'adobe', 'photoshop', 'wireframe', 'prototype', 'usability', 'sketch', 'accessibility'],
        'security': ['security', 'encryption', 'cryptography', 'penetration', 'authentication', 'authorization', 'oauth', 'jwt', 'ssl', 'tls'],
    }
    
    score = 0
    
    # Convert to lowercase
    user_interests_lower = [i.lower() for i in user_interests]
    project_langs_lower = (project_languages or '').lower()
    project_desc_lower = (project_description or '').lower()
    
    # Parse project languages into set
    project_langs_set = set(l.strip().lower() for l in project_langs_lower.split(',') if l.strip())
    
    # --- Factor 1: Direct Programming Language Matching (35 pts max) ---
    # This is NEW and prioritizes exact language matches
    language_match_bonus = 0
    
    # Check if any user interest is a programming language
    for interest in user_interests_lower:
        # Get all variants of this language
        if interest in PROGRAMMING_LANGUAGES:
            lang_variants = PROGRAMMING_LANGUAGES[interest]
            # Check if project uses this language
            for variant in lang_variants:
                if variant in project_langs_lower:
                    language_match_bonus += 12  # 12 pts per language match
        
        # Also check if interest is in project languages directly
        if interest in project_langs_lower:
            language_match_bonus += 15  # 15 pts for exact interest match
    
    # Also check all programming languages against user interests
    for lang_name, lang_variants in PROGRAMMING_LANGUAGES.items():
        for variant in lang_variants:
            if variant in project_langs_lower:
                # Check if this language matches any user interest
                if lang_name in user_interests_lower:
                    language_match_bonus += 8  # Already counted above
                elif lang_name.lower() in ' '.join(user_interests_lower):
                    language_match_bonus += 6
    
    language_match_bonus = min(language_match_bonus, 35)
    score += language_match_bonus
    
    # --- Factor 2: Direct Interest Keyword Matching (30 pts max) ---
    interest_keyword_hits = set()
    for interest in user_interests_lower:
        keywords = interest_keywords.get(interest, [])
        for keyword in keywords:
            if keyword in project_desc_lower or keyword in project_langs_lower:
                interest_keyword_hits.add(keyword)
    
    # Award points for unique keyword matches (2 pts each, max 30)
    interest_match_score = min(len(interest_keyword_hits) * 2, 30)
    score += interest_match_score
    
    # --- Factor 3: Language Overlap with Interest Keywords (20 pts max) ---
    language_keyword_score = 0
    for interest in user_interests_lower:
        keywords = interest_keywords.get(interest, [])
        for keyword in keywords:
            # Check if any keyword matches a project language
            for proj_lang in project_langs_set:
                if keyword in proj_lang or proj_lang in keyword:
                    language_keyword_score += 6
    
    language_keyword_score = min(language_keyword_score, 20)
    score += language_keyword_score
    
    # --- Factor 4: Description Quality & Keyword Density (10 pts max) ---
    STOPWORDS = {
        'the', 'a', 'an', 'and', 'or', 'in', 'on', 'is', 'to', 'for', 'of', 'with',
        'that', 'this', 'it', 'as', 'are', 'was', 'be', 'from', 'at', 'by', 'we',
        'our', 'your', 'not', 'has', 'have', 'will', 'can', 'i', 'its', 'using',
        'used', 'use', 'based', 'built', 'build', 'project', 'help', 'need', 'team',
    }
    
    if project_desc_lower:
        desc_words = set(word for word in project_desc_lower.split() if word not in STOPWORDS and len(word) > 2)
        
        # Count keywords from interests that appear in description
        desc_keyword_matches = 0
        for interest in user_interests_lower:
            keywords = interest_keywords.get(interest, [])
            for keyword in keywords:
                keyword_words = set(keyword.split())
                if keyword_words & desc_words:
                    desc_keyword_matches += 1
        
        desc_match_score = min(desc_keyword_matches * 2, 10)
        score += desc_match_score
    
    # --- Factor 5: Skills-to-Roles Alignment Bonus (5 pts max) ---
    if user_skills and project_roles:
        user_skills_lower = [s.lower() for s in (user_skills or [])]
        roles_needed = (project_roles or '').lower()
        
        skills_in_roles = 0
        for skill in user_skills_lower:
            if skill in roles_needed:
                skills_in_roles += 1
        
        skills_bonus = min(skills_in_roles * 2, 5)
        score += skills_bonus
    
    # Normalize and ensure score is between 0-100
    score = min(100, max(0, score))
    
    # Apply a precision boost for high-relevance matches
    if score > 70:
        # Already high quality, keep as is
        pass
    elif score < 30:
        # Filter out very low matches
        score = max(score, 10)  # Minimum 10% for showing
    
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
    
    # Parse user interests
    user_interests = [i.strip() for i in user.interests.split(',') if i.strip()] if user.interests else []
    
    if not user_interests:
        return jsonify({'message': 'Please set your interests to get suggestions', 'suggestions': []})
    
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
            'match_score': match_score,
            'match_reason': match_reason,
            'created_at': project.created_at.isoformat(),
        })
    
    return jsonify({
        'success': True,
        'user_interests': user_interests,
        'suggestions': result,
        'total': len(result),
        'algorithm_version': 'unified-v1'
    })


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