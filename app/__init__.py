from flask import Flask
from .config import Config
from .extensions import db, login_manager, migrate
from .models import User

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints (to be created)
    from .auth import auth_bp
    from .worker import worker_bp
    from .sitehead import sitehead_bp
    from .api import api_bp
    from .ivr import ivr_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(worker_bp)
    app.register_blueprint(sitehead_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(ivr_bp)

    return app
