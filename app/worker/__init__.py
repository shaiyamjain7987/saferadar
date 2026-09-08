from flask import Blueprint

worker_bp = Blueprint("worker", __name__, url_prefix="/worker")

from . import routes
