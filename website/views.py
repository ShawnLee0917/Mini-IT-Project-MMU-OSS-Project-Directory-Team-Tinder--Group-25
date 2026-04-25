import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash, jsonify, session

# 导入所有模型，包括新的 Suggestion
from .models import db, User, Skill, Badge, Comment, Project, ProjectImage, Suggestion

views = Blueprint('views', __name__)

# ==========================================
# 辅助函数 (Helper Functions)
# ==========================================

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def require_login():
    if 'user_email' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    return None

def get_current_user():
    """获取当前登录的用户，如果没登录，默认返回演示账户防止程序崩溃"""
    email = session.get('user_email', 'student@mmu.edu.my')
    user = User.query.filter_by(email=email).first()
    return user


# ==========================================
# HTML 页面路由 (HTML Page Routes)
# ==========================================

@views.route('/')
@views.route('/home')
def home():
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
    all_projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template("My_Projects.html", projects=all_projects)

@views.route('/profile')
def profile():
    return render_template("Profile.html")

@views.route('/project/<int:project_id>')
def project_page(project_id):
    project = Project.query.get_or_404(project_id)
    return render_template("Project_Page.html", project=project)

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
    project = Project.query.get_or_404(project_id)

    if request.method == 'POST':
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

    return render_template("Edit_Project.html", project=project)

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
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    name = data.get('name', '').strip()
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
    if not user or not user.password_hash or not check_password_hash(user.password_hash, password):
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
        'email': session['user_email'],
        'name': session['user_name'],
    })


@views.route('/api/profile', methods=['GET'])
def get_profile():
    err = require_login()
    if err: return err
    user = get_current_user()
    
    skills = Skill.query.filter_by(user_id=user.id).all()
    badges = Badge.query.filter_by(user_id=user.id).all()
    avatar_url = f"/static/uploads/{user.avatar_path}" if user.avatar_path else ''
    
    return jsonify({
        'email': user.email, 'name': user.name, 'faculty': user.faculty,
        'bio': user.bio or '', 'avatar_url': avatar_url, 'rank': user.rank,
        'karma': user.karma, 'skills': [s.skill for s in skills], 'badges': [b.badge for b in badges],
    })


@views.route('/api/profile', methods=['PUT'])
def update_profile():
    err = require_login()
    if err: return err

    data = request.get_json(silent=True) or {}
    user = get_current_user()

    if data.get('name'):
        user.name = data.get('name')
        session['user_name'] = data.get('name')
    if data.get('faculty'):
        user.faculty = data.get('faculty')
    user.bio = data.get('bio', '')

    skills = data.get('skills')
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
    if err: return err

    if 'avatar' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))

    user = get_current_user()
    user.avatar_path = filename
    db.session.commit()

    return jsonify({'success': True, 'avatar_url': f'/static/uploads/{filename}'})


@views.route('/api/comments', methods=['GET', 'POST'])
def handle_comments():
    if request.method == 'GET':
        comments = db.session.query(Comment, User.name).join(User).order_by(Comment.created_at.desc()).limit(50).all()
        return jsonify([{
            'id': c.id, 'user_id': c.user_id, 'user_name': uname,
            'comment': c.comment, 'created_at': c.created_at.isoformat()
        } for c, uname in comments])
    
    if request.method == 'POST':
        err = require_login()
        if err: return err
        
        data = request.get_json(silent=True) or {}
        comment_text = data.get('comment', '').strip()
        if not comment_text:
            return jsonify({'error': 'Comment cannot be empty'}), 400
        
        user = get_current_user()
        comment = Comment(user_id=user.id, comment=comment_text)
        db.session.add(comment)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Comment posted'})


@views.route('/api/projects', methods=['GET'])
def api_projects():
    err = require_login()
    if err: return err
    user = get_current_user()
    
    projects = Project.query.filter_by(user_id=user.id).order_by(Project.created_at.desc()).all()
    return jsonify([{
        'id': p.id, 'name': p.project_name, 'description': p.description,
        'status': p.status, 'contributors': p.contributors, 'created_at': p.created_at.isoformat()
    } for p in projects])


@views.route('/api/suggestions', methods=['GET'])
def get_suggestions():
    err = require_login()
    if err: return err
    user = get_current_user()
    
    already_suggested = db.session.query(Suggestion.project_id).filter_by(user_id=user.id).all()
    already_suggested_ids = [s[0] for s in already_suggested]
    
    suggestions = db.session.query(
        Project, User.name, db.func.count(Skill.id).label('skill_matches')
    ).join(User, Project.user_id == User.id).outerjoin(
        Skill, Skill.user_id == User.id
    ).filter(
        Project.user_id != user.id,
        ~Project.id.in_(already_suggested_ids)
    ).group_by(Project.id).order_by(
        db.desc('skill_matches'), db.desc(Project.created_at)
    ).limit(5).all()
    
    result = []
    for project, owner_name, skill_matches in suggestions:
        result.append({
            'id': project.id, 'project_id': project.id, 'owner_name': owner_name,
            'name': project.project_name, 'description': project.description,
            'status': project.status, 'contributors': project.contributors,
            'match_score': min(100, 50 + (skill_matches or 0) * 10),
        })
    return jsonify(result)


@views.route('/api/suggestions/<int:project_id>', methods=['POST'])
def accept_suggestion(project_id):
    err = require_login()
    if err: return err
    user = get_current_user()
    
    project = Project.query.get(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    try:
        suggestion = Suggestion(user_id=user.id, project_id=project_id, match_score=100)
        db.session.add(suggestion)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Already suggested'}), 409
    
    return jsonify({'success': True, 'message': 'Project suggested to you!'})