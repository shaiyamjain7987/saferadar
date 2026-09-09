import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-dev-secret-key')
    IS_VERCEL = os.getenv('VERCEL') == '1'
    SEED_DEMO_DATA = os.getenv('SEED_DEMO_DATA', '1' if IS_VERCEL else '0') == '1'

    # Database — default to project instance/site.db
    basedir = os.path.abspath(os.path.dirname(__file__))
    _instance_dir = os.path.join(basedir, '..', 'instance')
    if not IS_VERCEL:
        os.makedirs(_instance_dir, exist_ok=True)
    _default_db_dir = '/tmp' if IS_VERCEL else _instance_dir
    os.makedirs(_default_db_dir, exist_ok=True)
    _default_db = Path(_default_db_dir, 'site.db').resolve().as_posix()
    _database_url = os.getenv('DATABASE_URL', f"sqlite:///{_default_db}")
    if _database_url.startswith('postgres://'):
        _database_url = _database_url.replace('postgres://', 'postgresql+psycopg://', 1)
    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ML Models
    WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'base')

    # External APIs
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    BHASHINI_API_KEY = os.getenv('BHASHINI_API_KEY')
    BHASHINI_ASR_LANGUAGE = os.getenv('BHASHINI_ASR_LANGUAGE', 'auto')
    BHASHINI_ASR_SERVICE_ID = os.getenv('BHASHINI_ASR_SERVICE_ID')
    BHASHINI_TRANSLATE_SERVICE_ID = os.getenv('BHASHINI_TRANSLATE_SERVICE_ID')
    IVR_WORKER_EMAIL = os.getenv('IVR_WORKER_EMAIL', 'worker1@oil.com')
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
    UPLOAD_FOLDER = os.getenv(
        'UPLOAD_FOLDER',
        '/tmp/saferadar-uploads' if IS_VERCEL else os.path.join(basedir, 'static', 'uploads'),
    )
