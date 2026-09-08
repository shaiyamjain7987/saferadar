from app import create_app
from app.extensions import db
from app.models import Site, User, Report
from datetime import date, timedelta
import random

app = create_app()

def seed_db():
    with app.app_context():
        db.create_all()
        # Sites
        sites = [
            Site(name="Site A - Duliajan", code="SITE-A"),
            Site(name="Site B - Moran", code="SITE-B")
        ]
        for s in sites:
            if not Site.query.filter_by(code=s.code).first():
                db.session.add(s)
        db.session.commit()

        site_a = Site.query.filter_by(code="SITE-A").first()

        # Users
        admin = User.query.filter_by(email="admin@oil.com").first()
        if not admin:
            admin = User(name="Admin", email="admin@oil.com", role="site_head", site_id=site_a.id)
            admin.set_password("password")
            db.session.add(admin)

        worker1 = User.query.filter_by(email="worker1@oil.com").first()
        if not worker1:
            worker1 = User(name="Worker One", email="worker1@oil.com", role="worker", site_id=site_a.id)
            worker1.set_password("password")
            db.session.add(worker1)

        db.session.commit()
        
        # Synthetic Demo Reports
        if Report.query.count() == 0:
            precursors = ["Energy Isolation Failure", "Confined Space Entry without Gas Test", "Line of Fire Exposure"]
            hazards = ["Unexpected startup", "Toxic atmosphere", "Struck by moving object"]
            rules = ["Energy Isolation", "Confined Space", "Line of Fire"]
            
            for i in range(10):
                idx = random.randint(0, 2)
                r = Report(
                    worker_id=worker1.id,
                    site_id=site_a.id,
                    report_date=date.today() - timedelta(days=random.randint(0, 30)),
                    location=f"Unit {random.randint(1,5)}",
                    area="Maintenance Area",
                    description="This is a synthetic demo report.",
                    original_language="en",
                    activity="Maintenance",
                    hazard=hazards[idx],
                    precursor=precursors[idx],
                    barrier_failure="LOTO not followed" if idx==0 else "Permit missing",
                    life_saving_rule=rules[idx],
                    sif_potential=(idx==0),
                    sif_score=85 if idx==0 else 20,
                    risk_level="HIGH" if idx==0 else "LOW",
                    explanation="Synthetic explanation for demo purposes."
                )
                db.session.add(r)
            db.session.commit()
            print("Seeded database with demo data.")

if __name__ == "__main__":
    seed_db()
