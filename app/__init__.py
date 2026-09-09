from flask import Flask
from .config import Config
from .extensions import db, login_manager, migrate
from .models import Site, User


def _initialize_database(app):
    with app.app_context():
        db.create_all()
        if not app.config["SEED_DEMO_DATA"]:
            return

        site = Site.query.filter_by(code="SITE-A").first()
        if site is None:
            site = Site(name="Site A - Duliajan", code="SITE-A")
            db.session.add(site)
            db.session.flush()

        demo_users = (
            ("Admin", "admin@oil.com", "site_head"),
            ("Worker One", "worker1@oil.com", "worker"),
        )
        for name, email, role in demo_users:
            if User.query.filter_by(email=email).first() is None:
                user = User(name=name, email=email, role=role, site_id=site.id)
                user.set_password("password")
                db.session.add(user)

        db.session.commit()

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

    _initialize_database(app)

    return app
