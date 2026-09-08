from flask import Blueprint

sitehead_bp = Blueprint("sitehead", __name__, url_prefix="/sitehead")

from . import routes
