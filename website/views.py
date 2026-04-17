from flask import Blueprint, render_template, request, redirect, url_for
from .models import Project
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

        print(f"project {name} saved into database")

        return redirect(url_for('views.list_project'))
    
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

        db.session.commit()

        return redirect(url_for('views.project_page', project_id=project.id))

    return render_template("Edit_Project.html", project=project)