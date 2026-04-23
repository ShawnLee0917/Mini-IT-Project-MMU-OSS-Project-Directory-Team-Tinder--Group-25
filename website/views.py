import os
from werkzeug.utils import secure_filename
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, current_app
from .models import Project, ProjectImage
from . import db

views = Blueprint('views', __name__)

@views.route('/list_project', methods=['GET', 'POST'])
def list_project():
    if request.method == 'POST':
         
        name = request.form.get('project_name')
        repo = request.form.get('repo_url')
        langs = request.form.get('languages')
        roles = request.form.get('roles_needed')
        desc = request.form.get('description')
    

        new_project = Project(
            project_name=name, 
            repo_url=repo, 
            languages=langs, 
            roles_needed=roles, 
            description=desc
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

@views.route('/')
def home():
    
    return render_template("Navigation.html")

@views.route('/search')
def search():

    all_projects = Project.query.order_by(Project.date_created.desc()).all()
    return render_template("Search.html", projects=all_projects)

@views.route('/my_projects')
def my_projects():
    all_projects = Project.query.order_by(Project.date_created.desc()).all()
 
    return render_template("My_Projects.html", projects=all_projects)

@views.route('/profile')
def profile():
    projects = Project.query.order_by(Project.date_created.desc()).all()

    return render_template("Profile.html", projects=projects)

@views.route('/project/<int:project_id>')
def project_page(project_id):

    project = Project.query.get_or_404(project_id)
    
    return render_template("Project_Page.html", project=project)

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

@views.route('/upload-success')
def upload_success():
    return render_template("Upload_Success.html")