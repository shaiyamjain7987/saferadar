from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import SQLAlchemyError

from . import auth_bp
from ..extensions import db
from ..models import User, Site

@auth_bp.route("/", methods=["GET", "POST"])
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.is_worker:
            return redirect(url_for("worker.dashboard"))
        else:
            return redirect(url_for("sitehead.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not current_app.secret_key:
            current_app.logger.error("SECRET_KEY is not configured")
            return render_template(
                "auth/login.html",
                login_error="Login is temporarily unavailable. Configure SECRET_KEY.",
            ), 503

        try:
            if not current_app.extensions.get("database_ready", False):
                raise RuntimeError("Database initialization did not complete")

            user = User.query.filter_by(email=email).first()
            authenticated = user is not None and user.check_password(password)
            if authenticated:
                login_user(user)
                if user.is_worker:
                    return redirect(url_for("worker.dashboard"))
                return redirect(url_for("sitehead.dashboard"))
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError):
            db.session.rollback()
            current_app.logger.exception("Login authentication failed")
            flash("Login is temporarily unavailable. Check the database configuration.", "danger")
            return render_template("auth/login.html"), 503

        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html")

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    sites = Site.query.order_by(Site.name).all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        site_id = request.form.get("site_id")
        role = request.form.get("role", "worker").strip()
        if role not in ("worker", "site_head"):
            role = "worker"

        if not (name and email and password and site_id):
            flash("All fields are required.", "danger")
            return render_template("auth/signup.html", sites=sites)

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("auth/signup.html", sites=sites)

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
            return render_template("auth/signup.html", sites=sites)

        user = User(name=name, email=email, role=role, site_id=site_id)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash("Account created successfully.", "success")
        if user.is_worker:
            return redirect(url_for("worker.dashboard"))
        return redirect(url_for("sitehead.dashboard"))

    return render_template("auth/signup.html", sites=sites)

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
