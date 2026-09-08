from flask import Blueprint

ivr_bp = Blueprint("ivr", __name__, url_prefix="/ivr")

from . import routes
