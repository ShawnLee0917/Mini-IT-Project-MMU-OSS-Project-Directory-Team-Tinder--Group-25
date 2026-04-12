from . import db
from datetime import datetime

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_name = db.Column(db.String(150), nullable=False)
    repo_url = db.Column(db.String(300), nullable=False)
    languages = db.Column(db.String(150))
    roles_needed = db.Column(db.String(100))
    description = db.Column(db.Text)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)