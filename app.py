import os
import uuid
import csv
import io
import traceback
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, Response, jsonify, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import json
from pipeline import process_candidates, process_resume
from ats_report import generate_ats_report
import db
import auth

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_EXTENSIONS = {"pdf"}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Initialize DB
db.init_db()

class UploadedFileAdapter:
    def __init__(self, filename, data):
        self.name = filename
        self._data = data

    def getvalue(self):
        return self._data

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def landing():
    if "user_id" in session:
        if session.get("role") == "hr":
            return redirect(url_for("index"))
        elif session.get("role") == "candidate":
            return redirect(url_for("candidate_dashboard"))
    return render_template("landing.html")


@app.route("/login/hr", methods=["GET", "POST"])
def login_hr():
    return _handle_login("hr")


@app.route("/login/candidate", methods=["GET", "POST"])
def login_candidate():
    return _handle_login("candidate")


def _handle_login(role):
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""

        if not email or not password:
            flash("Enter both email and password.", "error")
            return redirect(url_for("login_hr" if role == "hr" else "login_candidate"))

        user = db.get_user_by_email(email, role=role)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return redirect(url_for("login_hr" if role == "hr" else "login_candidate"))

        session.clear()
        session["user_id"] = user["user_id"]
        session["role"] = user["role"]
        session["name"] = user["name"]

        if role == "hr":
            return redirect(url_for("index"))
        return redirect(url_for("candidate_dashboard"))

    return render_template("login.html", role=role)


@app.route("/signup/hr", methods=["GET", "POST"])
def signup_hr():
    return _handle_signup("hr")


@app.route("/signup/candidate", methods=["GET", "POST"])
def signup_candidate():
    return _handle_signup("candidate")


def _handle_signup(role):
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        errors = []
        if not name:
            errors.append("Enter your name.")
        if not email:
            errors.append("Enter your email address.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if email and db.get_user_by_email(email, role=role):
            errors.append("An account with that email already exists.")

        if errors:
            for message in errors:
                flash(message, "error")
            return redirect(url_for("signup_hr" if role == "hr" else "signup_candidate"))

        user_id = str(uuid.uuid4())
        db.create_user(
            user_id=user_id,
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role=role
        )

        session.clear()
        session["user_id"] = user_id
        session["role"] = role
        session["name"] = name

        flash("Account created successfully.", "success")
        if role == "hr":
            return redirect(url_for("index"))
        return redirect(url_for("candidate_dashboard"))

    return render_template("signup.html", role=role)


@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.", "success")
    return redirect(url_for("landing"))



@app.route("/dashboard", methods=["GET"])
@auth.login_required(role="hr")
def index():
    return render_template("index.html", active_page="dashboard")

@app.route("/process", methods=["POST"])
@auth.login_required(role="hr")
def process():
    role = (request.form.get("role") or "").strip()
    job_description = (request.form.get("job_description") or "").strip()
    uploaded = request.files.getlist("resumes")

    errors = []
    if not role:
        errors.append("Enter a role title.")
    if not job_description:
        errors.append("Enter a job description.")

    uploaded = [f for f in uploaded if f and f.filename]
    if not uploaded:
        errors.append("Attach at least one resume (PDF).")

    for f in uploaded:
        if not allowed_file(f.filename):
            errors.append(f"'{f.filename}' isn't a PDF — only .pdf files are accepted.")

    if errors:
        for message in errors:
            flash(message, "error")
        return redirect(url_for("index"))

    files_for_pipeline = []
    saved_files_map = {}

    for f in uploaded:
        filename = secure_filename(f.filename) or f.filename
        data = f.read()

        # Save original file to disk for downloading
        file_uuid = str(uuid.uuid4())
        disk_filename = f"{file_uuid}_{filename}"
        disk_path = os.path.join(app.config["UPLOAD_FOLDER"], disk_filename)
        with open(disk_path, "wb") as out_f:
            out_f.write(data)

        files_for_pipeline.append(UploadedFileAdapter(filename, data))
        saved_files_map[filename] = {"path": disk_path, "filename": filename}

    try:
        result = process_candidates(
            role=role,
            job_description=job_description,
            uploaded_files=files_for_pipeline,
        )
    except Exception as exc:
        app.logger.error("Pipeline failed: %s\n%s", exc, traceback.format_exc())
        flash(f"Something went wrong while processing candidates: {exc}", "error")
        return redirect(url_for("index"))

    # Generate unique candidate IDs and assign them before saving
    for c in result.get("ranked_candidates", []):
        c["candidate_id"] = str(uuid.uuid4())

    run_id = str(uuid.uuid4())
    db.save_screening_run(
        run_id=run_id,
        hr_user_id=session["user_id"],
        role=role,
        job_description=job_description,
        processed_jd=result.get("processed_jd"),
        ranked_candidates=result.get("ranked_candidates", []),
        saved_files_map=saved_files_map
    )

    return redirect(url_for("results", run_id=run_id))

@app.route("/results/<run_id>", methods=["GET"])
@auth.login_required(role="hr")
def results(run_id):
    run, candidates = db.get_screening_run(run_id, hr_user_id=session["user_id"])
    if not run:
        flash("Screening record not found.", "error")
        return redirect(url_for("index"))

    # Calculate summary metrics
    total_candidates = len(candidates)
    avg_score = round(sum(c["score"] for c in candidates) / total_candidates, 1) if total_candidates > 0 else 0
    high_fit_count = sum(1 for c in candidates if c["score"] >= 75)
    high_fit_pct = round((high_fit_count / total_candidates) * 100, 1) if total_candidates > 0 else 0

    # Determine top category across all candidates
    skill_counts = {}
    for c in candidates:
        for s in c.get("matched_skills", []):
            skill_counts[s] = skill_counts.get(s, 0) + 1
    top_skill = max(skill_counts, key=skill_counts.get) if skill_counts else "N/A"

    metrics = {
        "total": total_candidates,
        "avg_score": avg_score,
        "high_fit_pct": high_fit_pct,
        "top_skill": top_skill
    }

    return render_template("results.html", run=run, candidates=candidates, metrics=metrics, active_page="results")

@app.route("/candidate/<candidate_id>", methods=["GET"])
@auth.login_required(role="hr")
def candidate_detail(candidate_id):
    candidate = db.get_candidate_by_id(candidate_id, hr_user_id=session["user_id"])
    if not candidate:
        flash("Candidate not found.", "error")
        return redirect(url_for("index"))
    return render_template("candidate.html", candidate=candidate, active_page="results")

@app.route("/candidate/<candidate_id>/download-resume")
@auth.login_required(role="hr")
def download_resume(candidate_id):
    candidate = db.get_candidate_by_id(candidate_id, hr_user_id=session["user_id"])
    if not candidate or not candidate.get("file_path") or not os.path.exists(candidate["file_path"]):
        flash("Resume PDF file not found on server.", "error")
        return redirect(url_for("candidate_detail", candidate_id=candidate_id))
    return send_file(candidate["file_path"], as_attachment=True, download_name=candidate["filename"])

@app.route("/candidate/<candidate_id>/export/json")
@auth.login_required(role="hr")
def export_candidate_json(candidate_id):
    candidate = db.get_candidate_by_id(candidate_id, hr_user_id=session["user_id"])
    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404
    return Response(
        json.dumps(candidate, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment;filename=candidate_{candidate_id}.json"}
    )

@app.route("/analytics", methods=["GET"])
@auth.login_required(role="hr")
def analytics():
    data = db.get_global_analytics(session["user_id"])
    return render_template("analytics.html", analytics=data, active_page="analytics")

@app.route("/history", methods=["GET"])
@auth.login_required(role="hr")
def history():
    runs = db.get_all_runs(session["user_id"])
    return render_template("history.html", runs=runs, active_page="history")

@app.route("/history/delete/<run_id>", methods=["POST"])
@auth.login_required(role="hr")
def delete_history(run_id):
    deleted = db.delete_run(run_id, session["user_id"])
    if deleted:
        flash("Screening record deleted successfully.", "success")
    else:
        flash("Screening record not found.", "error")
    return redirect(url_for("history"))

@app.route("/export/csv/<run_id>")
@auth.login_required(role="hr")
def export_csv(run_id):
    run, candidates = db.get_screening_run(run_id, hr_user_id=session["user_id"])
    if not run:
        flash("Screening record not found.", "error")
        return redirect(url_for("index"))

    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    writer.writerow([
        "Rank", "Candidate Name", "Total Score", "Email", "Phone", "Location",
        "Experience Score", "Skills Score", "Degree Score", "Role Fit Score",
        "Matched Skills", "Missing Skills"
    ])

    for c in candidates:
        bd = c.get("score_breakdown", {})
        writer.writerow([
            c.get("rank"),
            c.get("name"),
            c.get("score"),
            c.get("email"),
            c.get("phone"),
            c.get("location"),
            bd.get("experience"),
            bd.get("skills"),
            bd.get("degree"),
            bd.get("role"),
            "; ".join(c.get("matched_skills", [])),
            "; ".join(c.get("missing_skills", []))
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=screening_run_{run_id}.csv"}
    )

@app.errorhandler(413)
def too_large(_e):
    flash("Upload too large — total resume size must stay under 50MB.", "error")
    return redirect(url_for("index"))

@app.route("/candidates", methods=["GET"])
@auth.login_required(role="hr")
def candidates():
    candidates_list = db.get_all_candidates(session["user_id"])

    query = (request.args.get("q") or "").strip().lower()
    if query:
        def matches(c):
            haystack = [
                c.get("name") or "",
                c.get("email") or "",
                c.get("location") or "",
                c.get("role_title") or "",
                c.get("degree") or "",
            ]
            haystack += c.get("matched_skills") or []
            return any(query in str(field).lower() for field in haystack)

        candidates_list = [c for c in candidates_list if matches(c)]

    return render_template(
        "candidates.html",
        candidates=candidates_list,
        active_page="candidates",
        search_query=request.args.get("q", "")
    )

@app.route('/run/<run_id>/all-data')
@auth.login_required(role="hr")
def view_all_data(run_id):
    run = db.get_run(run_id, hr_user_id=session["user_id"])
    if not run:
        flash("Screening record not found.", "error")
        return redirect(url_for("index"))
    candidates = db.get_candidates_for_run(run_id, hr_user_id=session["user_id"])
    return render_template('all_data.html', run=run, candidates=candidates)

@app.route('/run/<run_id>/export-all-csv')
@auth.login_required(role="hr")
def export_all_csv(run_id):
    run = db.get_run(run_id, hr_user_id=session["user_id"])
    if not run:
        flash("Screening record not found.", "error")
        return redirect(url_for("index"))
    candidates = db.get_candidates_for_run(run_id, hr_user_id=session["user_id"])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Rank', 'Name', 'Score', 'Experience (Yrs)', 'Email', 'Phone', 'Location', 'Degree', 'Matched Skills', 'Missing Skills'])

    for c in candidates:
        parsed = c.get('parsed_data', {})
        writer.writerow([
            c.get('rank'),
            c.get('name'),
            c.get('score'),
            c.get('experience_years', 'N/A'),
            c.get('email') or parsed.get('Email', ''),
            c.get('phone') or parsed.get('Phone', ''),
            c.get('location') or (parsed.get('Location', [''])[0] if parsed.get('Location') else ''),
            c.get('degree') or ', '.join(parsed.get('Degree', [])),
            ', '.join(c.get('matched_skills', [])),
            ', '.join(c.get('missing_skills', []))
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=all_candidates_run_{run_id}.csv"}
    )



@app.route("/candidate/dashboard", methods=["GET"])
@auth.login_required(role="candidate")
def candidate_dashboard():
    report = db.get_latest_resume_report(session["user_id"])
    return render_template("candidate_dashboard.html", report=report, active_page="candidate_dashboard")

@app.route("/candidate/upload", methods=["POST"])
@auth.login_required(role="candidate")
def candidate_upload():
    f = request.files.get("resume")

    if not f or not f.filename:
        flash("Attach your resume (PDF).", "error")
        return redirect(url_for("candidate_dashboard"))

    if not allowed_file(f.filename):
        flash("Only PDF files are accepted.", "error")
        return redirect(url_for("candidate_dashboard"))

    filename = secure_filename(f.filename) or f.filename
    data = f.read()

    file_uuid = str(uuid.uuid4())
    disk_filename = f"{file_uuid}_{filename}"
    disk_path = os.path.join(app.config["UPLOAD_FOLDER"], disk_filename)
    with open(disk_path, "wb") as out_f:
        out_f.write(data)

    adapter = UploadedFileAdapter(filename, data)

    try:
        result = process_resume(adapter)
    except Exception as exc:
        app.logger.error("ATS resume processing failed: %s\n%s", exc, traceback.format_exc())
        flash(f"Something went wrong while analyzing your resume: {exc}", "error")
        return redirect(url_for("candidate_dashboard"))

    report = generate_ats_report(result.get("resume_text", ""), result.get("parsed_data", {}))

    report_id = str(uuid.uuid4())
    db.save_resume_report(
        report_id=report_id,
        candidate_user_id=session["user_id"],
        filename=filename,
        file_path=disk_path,
        resume_text=result.get("resume_text", ""),
        parsed_data=result.get("parsed_data", {}),
        report=report
    )

    return redirect(url_for("candidate_report", report_id=report_id))

@app.route("/candidate/report/<report_id>", methods=["GET"])
@auth.login_required(role="candidate")
def candidate_report(report_id):
    report = db.get_resume_report_by_id(report_id, candidate_user_id=session["user_id"])
    if not report:
        flash("Report not found.", "error")
        return redirect(url_for("candidate_dashboard"))
    return render_template("candidate_report.html", report=report, active_page="candidate_dashboard")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
