from app import create_app
from app.extensions import db

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all() # Create sqlite tables for demo
    app.run(debug=True, port=5000)
