import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash, jsonify, session
from .models import db, User, Skill, Badge, Comment, Project, ProjectImage, Suggestion

views = Blueprint('views', __name__)

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
def home():
    return render_template("Navigation.html")

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
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template("Profile.html", projects=projects)

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
        print(f"project {name} saved into database")
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

@views.route('/api/suggestions', methods=['GET'])
def get_suggestions():
    err = require_login()
    if err: return err
    user = get_current_user()
    
    suggestions = Project.query.filter(Project.user_id != user.id).limit(5).all()
    result = []
    for project in suggestions:
        result.append({
            'id': project.id, 'name': project.project_name, 
            'description': project.description, 'match_score': 95
        })
    return jsonify(result)

@views.route('/login')
def login():
    return render_template("login.html")

@views.route('/register')
def register():
    return render_template("register.html")