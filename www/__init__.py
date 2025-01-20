import sys
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Add the lib directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib')))

from lib.orm.database import Database  # Import after adding lib to path

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    
    # Initialize the Database
    db_instance = Database()
    
    # Configure SQLAlchemy to use the engine from db_instance
    app.config['SQLALCHEMY_DATABASE_URI'] = str(db_instance.engine.url)
    db.init_app(app)
    
    with app.app_context():
        from . import routes  # Import routes
        db.create_all()  # Create database tables
    
    return app