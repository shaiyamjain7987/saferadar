import os
import uuid
from collections import defaultdict
from datetime import datetime

from flask import Response, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from . import sitehead_bp
from ..constants import AREAS
from ..extensions import db
from ..models import Alert, CorrectiveAction, Report, Site, User
from ..services.language_service import detect_language, translate_to_english
from ..services.nlp_service import analyze_safety_text
from ..services.risk_service import calculate_sif_score


def _require_site_head():
    if not (current_user.is_site_head or current_user.role == "admin"):
        return redirect(url_for("worker.dashboard"))
    return None


def _save_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    upload_dir = os.path.join(current_app.root_path, "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(secure_filename(file_storage.filename))[1].lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    file_storage.save(os.path.join(upload_dir, filename))
    return filename


def _filtered_reports(site_id):
    query = Report.query.filter_by(site_id=site_id)
    filters = {
        "area": request.args.get("area", "").strip(),
        "classification": request.args.get("classification", "").strip(),
        "date_from": request.args.get("date_from", "").strip(),
        "date_to": request.args.get("date_to", "").strip(),
    }

    if filters["area"]:
        query = query.filter(Report.area == filters["area"])
    if filters["classification"] == "sif":
        query = query.filter(Report.sif_potential.is_(True))
    elif filters["classification"] == "nonsif":
        query = query.filter(Report.sif_potential.is_(False))
    if filters["date_from"]:
        try:
            query = query.filter(
                Report.report_date >= datetime.strptime(filters["date_from"], "%Y-%m-%d").date()
            )
        except ValueError:
            pass
    if filters["date_to"]:
        try:
            query = query.filter(
                Report.report_date <= datetime.strptime(filters["date_to"], "%Y-%m-%d").date()
            )
        except ValueError:
            pass

    reports = query.order_by(Report.report_date.desc(), Report.id.desc()).all()
    return reports, filters


def _trend_series(reports):
    buckets = defaultdict(lambda: {"total": 0, "sif": 0})
    for r in reports:
        if not r.report_date:
            continue
        key = r.report_date.isoformat()
        buckets[key]["total"] += 1
        if r.sif_potential:
            buckets[key]["sif"] += 1
    dates = sorted(buckets.keys())
    return (
        dates,
        [buckets[d]["total"] for d in dates],
        [buckets[d]["sif"] for d in dates],
    )


@sitehead_bp.route("/")
@sitehead_bp.route("/dashboard")
@login_required
def dashboard():
    blocked = _require_site_head()
    if blocked:
        return blocked

    site = current_user.site
    reports, filters = _filtered_reports(site.id)
    all_site_reports = Report.query.filter_by(site_id=site.id).all()

    total_reports = len(all_site_reports)
    sif_reports = [r for r in all_site_reports if r.sif_potential]
    sif_count = len(sif_reports)

    rule_counts = {}
    for r in sif_reports:
        if r.life_saving_rule:
            rule_counts[r.life_saving_rule] = rule_counts.get(r.life_saving_rule, 0) + 1
    sorted_rules = sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)
    top_rule = sorted_rules[0][0] if sorted_rules else "None"
    rule_labels = [k for k, _ in sorted_rules]
    rule_values = [v for _, v in sorted_rules]

    pattern_map = {}
    for r in sif_reports:
        key = (f"{r.area} / {r.activity or '—'}", r.life_saving_rule)
        pattern_map[key] = pattern_map.get(key, 0) + 1
    pattern_rows = sorted(
        [[k[0], k[1], v] for k, v in pattern_map.items()],
        key=lambda x: x[2],
        reverse=True,
    )

    workers_list = User.query.filter_by(site_id=site.id, role="worker").all()
    workers_data = []
    for w in workers_list:
        w_reports = [r for r in all_site_reports if r.worker_id == w.id]
        workers_data.append(
            {
                "user": w,
                "total": len(w_reports),
                "sif_count": sum(1 for r in w_reports if r.sif_potential),
            }
        )

    trend_dates, trend_total, trend_sif = _trend_series(all_site_reports)
    areas = sorted({r.area for r in all_site_reports if r.area})

    return render_template(
        "sitehead/dashboard.html",
        site=site,
        total_reports=total_reports,
        sif_count=sif_count,
        top_rule=top_rule,
        rule_labels=rule_labels,
        rule_values=rule_values,
        pattern_rows=pattern_rows,
        workers=workers_data,
        reports=reports,
        areas=areas,
        filters=filters,
        trend_dates=trend_dates,
        trend_total=trend_total,
        trend_sif=trend_sif,
    )


@sitehead_bp.route("/reports")
@login_required
def reports():
    blocked = _require_site_head()
    if blocked:
        return blocked

    site_reports, filters = _filtered_reports(current_user.site_id)
    areas = sorted({r.area for r in Report.query.filter_by(site_id=current_user.site_id).all() if r.area})
    return render_template(
        "sitehead/reports.html",
        reports=site_reports,
        filters=filters,
        areas=areas,
    )


@sitehead_bp.route("/report/<int:report_id>", methods=["GET", "POST"])
@login_required
def report_detail(report_id):
    blocked = _require_site_head()
    if blocked:
        return blocked

    report = Report.query.filter_by(id=report_id, site_id=current_user.site_id).first_or_404()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "update_status":
            status = request.form.get("status", report.status)
            if status in {"Open", "Under Investigation", "Closed"}:
                report.status = status
                db.session.commit()
                flash("Report status updated.", "success")
        elif action == "add_corrective":
            description = (request.form.get("description") or "").strip()
            priority = request.form.get("priority") or "Medium"
            assigned_to = request.form.get("assigned_to") or None
            due_raw = (request.form.get("due_date") or "").strip()
            due_date = None
            if due_raw:
                try:
                    due_date = datetime.strptime(due_raw, "%Y-%m-%d").date()
                except ValueError:
                    flash("Invalid due date.", "danger")
                    return redirect(url_for("sitehead.report_detail", report_id=report.id))
            if not description:
                flash("Corrective action description is required.", "danger")
            else:
                ca = CorrectiveAction(
                    report_id=report.id,
                    assigned_to=int(assigned_to) if assigned_to else None,
                    description=description,
                    priority=priority,
                    due_date=due_date,
                    status="Open",
                )
                db.session.add(ca)
                db.session.commit()
                flash("Corrective action added.", "success")
        return redirect(url_for("sitehead.report_detail", report_id=report.id))

    workers = User.query.filter_by(site_id=current_user.site_id, role="worker").all()
    return render_template("sitehead/report_detail.html", report=report, workers=workers)


@sitehead_bp.route("/alerts", methods=["GET", "POST"])
@login_required
def alerts():
    blocked = _require_site_head()
    if blocked:
        return blocked

    if request.method == "POST":
        alert_id = request.form.get("alert_id")
        alert = Alert.query.filter_by(id=alert_id, site_id=current_user.site_id).first()
        if alert:
            alert.is_acknowledged = True
            db.session.commit()
            flash("Alert acknowledged.", "success")
        return redirect(url_for("sitehead.alerts"))

    site_alerts = (
        Alert.query.filter_by(site_id=current_user.site_id)
        .order_by(Alert.created_at.desc())
        .all()
    )
    return render_template("sitehead/alerts.html", alerts=site_alerts)


def _team_workers_data():
    site_reports = Report.query.filter_by(site_id=current_user.site_id).all()
    workers_list = User.query.filter_by(site_id=current_user.site_id, role="worker").order_by(User.name).all()
    workers_data = []
    for w in workers_list:
        w_reports = [r for r in site_reports if r.worker_id == w.id]
        workers_data.append(
            {
                "user": w,
                "total": len(w_reports),
                "sif_count": sum(1 for r in w_reports if r.sif_potential),
                "open_actions": CorrectiveAction.query.filter_by(
                    assigned_to=w.id, status="Open"
                ).count(),
            }
        )
    return workers_data


@sitehead_bp.route("/team", methods=["GET", "POST"])
@login_required
def team():
    blocked = _require_site_head()
    if blocked:
        return blocked

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not (name and email and password):
            flash("Name, email, and password are required to add a worker.", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("That email is already registered.", "danger")
        else:
            worker = User(
                name=name,
                email=email,
                role="worker",
                site_id=current_user.site_id,
            )
            worker.set_password(password)
            db.session.add(worker)
            db.session.commit()
            flash(f"Worker {name} added. They can log in with {email}.", "success")
            return redirect(url_for("sitehead.team"))

    return render_template("sitehead/team.html", workers=_team_workers_data())


@sitehead_bp.route("/report/new", methods=["GET", "POST"])
@login_required
def report_new():
    blocked = _require_site_head()
    if blocked:
        return blocked

    workers = User.query.filter_by(site_id=current_user.site_id, role="worker").order_by(User.name).all()

    if request.method == "POST":
        description = (request.form.get("description") or "").strip()
        location = (request.form.get("location") or "").strip()
        area = (request.form.get("area") or "").strip()
        date_raw = (request.form.get("report_date") or "").strip()
        worker_id = request.form.get("worker_id") or str(current_user.id)

        if not (description and location and area and date_raw):
            flash("All required fields must be filled.", "danger")
            return render_template("sitehead/report_form.html", areas=AREAS, workers=workers)

        try:
            report_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid date format.", "danger")
            return render_template("sitehead/report_form.html", areas=AREAS, workers=workers)

        reporter = User.query.filter_by(id=int(worker_id), site_id=current_user.site_id).first()
        if not reporter:
            reporter = current_user

        lang = detect_language(description)
        english_text = translate_to_english(description, lang)
        analysis = analyze_safety_text(english_text)
        risk = calculate_sif_score(analysis)
        image_filename = _save_image(request.files.get("image"))

        report = Report(
            worker_id=reporter.id,
            site_id=current_user.site_id,
            report_date=report_date,
            location=location,
            area=area,
            description=english_text,
            original_language=lang,
            image_filename=image_filename,
            activity=analysis.get("activity"),
            hazard=analysis.get("hazard"),
            precursor=analysis.get("precursor"),
            barrier_failure=analysis.get("barrier_failure"),
            life_saving_rule=analysis.get("life_saving_rule"),
            sif_potential=bool(analysis.get("sif_potential") or risk.get("risk_level") == "HIGH"),
            sif_score=risk.get("score"),
            risk_level=risk.get("risk_level"),
            explanation=risk.get("explanation"),
            status="Open",
        )
        db.session.add(report)
        db.session.flush()

        if report.risk_level == "HIGH" or report.sif_potential:
            db.session.add(
                Alert(
                    site_id=report.site_id,
                    title="HIGH SIF ALERT",
                    message=(
                        f"High risk report #{report.id}: {report.precursor or 'SIF precursor'}. "
                        f"{report.explanation or ''}"
                    ).strip(),
                    level="CRITICAL",
                )
            )
        db.session.commit()
        flash("Report submitted successfully.", "success")
        return redirect(url_for("sitehead.report_detail", report_id=report.id))

    return render_template("sitehead/report_form.html", areas=AREAS, workers=workers)


@sitehead_bp.route("/ranking")
@login_required
def ranking():
    blocked = _require_site_head()
    if blocked:
        return blocked

    sites = Site.query.all()
    site_rankings = []
    for s in sites:
        site_reports = Report.query.filter_by(site_id=s.id).all()
        total = len(site_reports)
        sif = sum(1 for r in site_reports if r.sif_potential)
        density = (sif / total * 100) if total > 0 else 0
        site_rankings.append(
            {
                "site": s,
                "total": total,
                "sif": sif,
                "density": round(density, 1),
            }
        )
    site_rankings.sort(key=lambda x: x["density"], reverse=True)
    return render_template("sitehead/ranking.html", rankings=site_rankings)


@sitehead_bp.route("/export.csv")
@login_required
def export_csv():
    blocked = _require_site_head()
    if blocked:
        return blocked

    reports, _ = _filtered_reports(current_user.site_id)
    lines = ["id,date,worker,area,location,sif_potential,life_saving_rule,risk_level,status"]
    for r in reports:
        lines.append(
            ",".join(
                [
                    str(r.id),
                    r.report_date.isoformat() if r.report_date else "",
                    f'"{(r.worker.name if r.worker else "").replace(chr(34), "")}"',
                    f'"{(r.area or "").replace(chr(34), "")}"',
                    f'"{(r.location or "").replace(chr(34), "")}"',
                    "1" if r.sif_potential else "0",
                    f'"{(r.life_saving_rule or "").replace(chr(34), "")}"',
                    r.risk_level or "",
                    r.status or "",
                ]
            )
        )
    return Response(
        "\n".join(lines),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=site_reports.csv"},
    )
