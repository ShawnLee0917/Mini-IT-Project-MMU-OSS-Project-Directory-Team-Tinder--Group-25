import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash, jsonify, session

from .models import Question, QuestionComment, QuestionFavorite, QuestionLike, db, User, Skill, Badge, Comment, Project, ProjectImage, Suggestion, ProjectComment, CommentLabel

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

@views.route('/search')
def search():
    all_projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template("Search.html", projects=all_projects)

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

    if not email or not password or not name:
        return jsonify({'error': 'All fields are required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    pw_hash = generate_password_hash(password)
    try:
        user = User(email=email, name=name, password_hash=pw_hash)
        db.session.add(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Email already registered'}), 409
    
    return jsonify({'success': True, 'message': 'Account created!'})


@views.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    user = User.query.filter_by(email=email).first()
    if not user or not user.password_hash or \
       not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid email or password'}), 401

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

    return jsonify({'success': True, 'avatar_url': f'/uploads/{filename}'})


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

        result.append({
            'id':           q.id,
            'user_id':      q.user_id,
            'author_name':  author_name,
            'title':        q.title,
            'body':         q.body,
            'image_url':    f'/uploads/{q.image_path}' if q.image_path else '',
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

    # Handle optional image
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"q_{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            q.image_path = filename

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
    } for c, name in rows]

    return jsonify(result)


@views.route('/api/questions/<int:question_id>/comments', methods=['POST'])
def post_question_comment(question_id):
    err = require_login()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    body = data.get('body', '').strip()

    if not body:
        return jsonify({'error': 'Comment cannot be empty'}), 400
    if len(body) > 1000:
        return jsonify({'error': 'Comment too long (max 1000 chars)'}), 400

    q = Question.query.get(question_id)
    if not q:
        return jsonify({'error': 'Question not found'}), 404

    parent_id = data.get('parent_id', None)
    if parent_id:
        parent = QuestionComment.query.get(parent_id)
        if not parent or parent.question_id != question_id:
            parent_id = None

    user = User.query.filter_by(email=session['user_email']).first()
    c = QuestionComment(user_id=user.id, question_id=question_id, body=body, parent_id=parent_id)
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

    data = request.get_json(silent=True) or {}
    body = data.get('body', '').strip()

    if not body:
        return jsonify({'error': 'Comment cannot be empty'}), 400
    if len(body) > 1000:
        return jsonify({'error': 'Comment too long (max 1000 chars)'}), 400

    c.body = body
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
    return {
        'id': q.id, 'user_id': q.user_id, 'author_name': author_name,
        'title': q.title, 'body': q.body,
        'image_url': f'/uploads/{q.image_path}' if q.image_path else '',
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