from flask import Blueprint, render_template

from .services import ensure_storage_ready

web_bp = Blueprint("web", __name__)


@web_bp.get("/")
def index():
    ensure_storage_ready()
    return render_template("index.html")
