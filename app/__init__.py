from flask import Flask
from config import Config
from extensions import db, migrate, mail

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    # Register blueprints
    from app.blueprints.main import main as main_blueprint
    
    app.register_blueprint(main_blueprint)

    # Initialize the config
    config_class.init_app(app)

    # Create all database tables
    with app.app_context():
        db.create_all()

    return app

# Create the Flask application instance
app = create_app() 