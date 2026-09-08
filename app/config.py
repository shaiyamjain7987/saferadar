import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-dev-secret-key')

    # Database — default to project instance/site.db
    basedir = os.path.abspath(os.path.dirname(__file__))
    _instance_dir = os.path.join(basedir, '..', 'instance')
    os.makedirs(_instance_dir, exist_ok=True)
    _default_db = Path(_instance_dir, 'site.db').resolve().as_posix()
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f"sqlite:///{_default_db}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ML Models
    WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'base')

    # External APIs
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    BHASHINI_API_KEY = os.getenv('BHASHINI_API_KEY')
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')

    # Exotel
    EXOTEL_API_KEY = os.getenv('EXOTEL_API_KEY')
    EXOTEL_API_TOKEN = os.getenv('EXOTEL_API_TOKEN')
    EXOTEL_SID = os.getenv('EXOTEL_SID')
    EXOTEL_VIRTUAL_NUMBER = os.getenv('EXOTEL_VIRTUAL_NUMBER')
    # India accounts use api.in.exotel.com
    EXOTEL_SUBDOMAIN = os.getenv('EXOTEL_SUBDOMAIN', 'api.in.exotel.com')

    # Public HTTPS URL so Exotel can reach this app (set later via ngrok)
    PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', '').rstrip('/')

    # Uploads
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
