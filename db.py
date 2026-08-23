import os
import json
import duckdb
from datetime import datetime

DB_FILE = "screening_desk.duckdb"

def get_db():
    con = duckdb.connect(DB_FILE)
    return con

def init_db():
    con = get_db()

   
    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id VARCHAR PRIMARY KEY,
            name VARCHAR,
            email VARCHAR,
            password_hash VARCHAR,
            role VARCHAR,
            created_at TIMESTAMP
        )
    """)

   
    con.execute("""
        CREATE TABLE IF NOT EXISTS screening_runs (
            run_id VARCHAR PRIMARY KEY,
            hr_user_id VARCHAR,
            role VARCHAR,
            job_description TEXT,
            processed_jd_json TEXT,
            created_at TIMESTAMP
        )
    """)
    
    try:
        con.execute("ALTER TABLE screening_runs ADD COLUMN hr_user_id VARCHAR")
    except Exception:
        pass

    # Create candidates table
    con.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            candidate_id VARCHAR PRIMARY KEY,
            run_id VARCHAR,
            name VARCHAR,
            email VARCHAR,
            phone VARCHAR,
            location VARCHAR,
            experience_years DOUBLE,
            degree VARCHAR,
            score DOUBLE,
            rank INTEGER,
            skills_json TEXT,
            missing_skills_json TEXT,
            score_breakdown_json TEXT,
            why_score_json TEXT,
            raw_parsed_json TEXT,
            file_path VARCHAR,
            filename VARCHAR,
            FOREIGN KEY (run_id) REFERENCES screening_runs(run_id)
        )
    """)

   
    con.execute("""
        CREATE TABLE IF NOT EXISTS resume_reports (
            report_id VARCHAR PRIMARY KEY,
            candidate_user_id VARCHAR,
            filename VARCHAR,
            file_path VARCHAR,
            resume_text TEXT,
            parsed_json TEXT,
            ats_score DOUBLE,
            report_json TEXT,
            created_at TIMESTAMP,
            FOREIGN KEY (candidate_user_id) REFERENCES users(user_id)
        )
    """)

    con.close()




def create_user(user_id, name, email, password_hash, role):
    con = get_db()
    con.execute(
        "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
        [user_id, name, email, password_hash, role, datetime.utcnow()]
    )
    con.close()

def get_user_by_email(email, role=None):
    con = get_db()
    if role:
        row = con.execute(
            "SELECT * FROM users WHERE lower(email) = lower(?) AND role = ?",
            [email, role]
        ).fetchone()
    else:
        row = con.execute(
            "SELECT * FROM users WHERE lower(email) = lower(?)",
            [email]
        ).fetchone()
    con.close()
    if not row:
        return None
    return {
        "user_id": row[0],
        "name": row[1],
        "email": row[2],
        "password_hash": row[3],
        "role": row[4],
        "created_at": row[5],
    }

def get_user_by_id(user_id):
    con = get_db()
    row = con.execute("SELECT * FROM users WHERE user_id = ?", [user_id]).fetchone()
    con.close()
    if not row:
        return None
    return {
        "user_id": row[0],
        "name": row[1],
        "email": row[2],
        "password_hash": row[3],
        "role": row[4],
        "created_at": row[5],
    }




def save_screening_run(run_id, hr_user_id, role, job_description, processed_jd, ranked_candidates, saved_files_map):
    con = get_db()
    now = datetime.utcnow()

    con.execute(
        "INSERT INTO screening_runs VALUES (?, ?, ?, ?, ?, ?)",
        [run_id, hr_user_id, role, job_description, json.dumps(processed_jd), now]
    )

    for c in ranked_candidates:
        cand_id = c.get("candidate_id")
        parsed = c.get("parsed_data", {})
        file_info = saved_files_map.get(c.get("filename"), {})

        con.execute(
            """
            INSERT INTO candidates VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                cand_id,
                run_id,
                c.get("name"),
                parsed.get("Email"),
                parsed.get("Phone"),
                parsed.get("Location", [None])[0] if isinstance(parsed.get("Location"), list) and parsed.get("Location") else parsed.get("Location"),
                c.get("years", 0),
                ", ".join(parsed.get("Degree", [])) if isinstance(parsed.get("Degree"), list) else parsed.get("Degree"),
                c.get("score"),
                c.get("rank"),
                json.dumps(c.get("matched_skills", [])),
                json.dumps(c.get("missing_skills", [])),
                json.dumps(c.get("score_breakdown", {})),
                json.dumps(c.get("why_score", {})),
                json.dumps(parsed),
                file_info.get("path"),
                c.get("filename")
            ]
        )
    con.close()

def _run_row_to_dict(run):
    return {
        "run_id": run[0],
        "hr_user_id": run[1],
        "role": run[2],
        "job_description": run[3],
        "processed_jd": json.loads(run[4]) if run[4] else {},
        "created_at": run[5]
    }

def get_screening_run(run_id, hr_user_id=None):
    con = get_db()
    if hr_user_id:
        run = con.execute("SELECT * FROM screening_runs WHERE run_id = ? AND hr_user_id = ?", [run_id, hr_user_id]).fetchone()
    else:
        run = con.execute("SELECT * FROM screening_runs WHERE run_id = ?", [run_id]).fetchone()
    if not run:
        con.close()
        return None, []

    candidates = con.execute("SELECT * FROM candidates WHERE run_id = ? ORDER BY rank ASC", [run_id]).fetchall()
    con.close()

    run_dict = _run_row_to_dict(run)

    candidate_list = []
    for row in candidates:
        candidate_list.append({
            "candidate_id": row[0],
            "run_id": row[1],
            "name": row[2],
            "email": row[3],
            "phone": row[4],
            "location": row[5],
            "experience_years": row[6],
            "degree": row[7],
            "score": row[8],
            "rank": row[9],
            "matched_skills": json.loads(row[10]) if row[10] else [],
            "missing_skills": json.loads(row[11]) if row[11] else [],
            "score_breakdown": json.loads(row[12]) if row[12] else {},
            "why_score": json.loads(row[13]) if row[13] else {},
            "parsed_data": json.loads(row[14]) if row[14] else {},
            "file_path": row[15],
            "filename": row[16]
        })

    return run_dict, candidate_list

def get_run(run_id, hr_user_id=None):
    con = get_db()
    if hr_user_id:
        run = con.execute("SELECT * FROM screening_runs WHERE run_id = ? AND hr_user_id = ?", [run_id, hr_user_id]).fetchone()
    else:
        run = con.execute("SELECT * FROM screening_runs WHERE run_id = ?", [run_id]).fetchone()
    con.close()
    if not run:
        return None
    return _run_row_to_dict(run)

def get_candidates_for_run(run_id, hr_user_id=None):
    # Ownership is enforced by only returning candidates for a run the caller owns
    if hr_user_id is not None:
        run = get_run(run_id, hr_user_id=hr_user_id)
        if not run:
            return []
    con = get_db()
    candidates = con.execute("SELECT * FROM candidates WHERE run_id = ? ORDER BY rank ASC", [run_id]).fetchall()
    con.close()

    candidate_list = []
    for row in candidates:
        candidate_list.append({
            "candidate_id": row[0],
            "run_id": row[1],
            "name": row[2],
            "email": row[3],
            "phone": row[4],
            "location": row[5],
            "experience_years": row[6],
            "degree": row[7],
            "score": row[8],
            "rank": row[9],
            "matched_skills": json.loads(row[10]) if row[10] else [],
            "missing_skills": json.loads(row[11]) if row[11] else [],
            "score_breakdown": json.loads(row[12]) if row[12] else {},
            "why_score": json.loads(row[13]) if row[13] else {},
            "parsed_data": json.loads(row[14]) if row[14] else {},
            "file_path": row[15],
            "filename": row[16]
        })
    return candidate_list

def get_candidate_by_id(candidate_id, hr_user_id=None):
    con = get_db()
    if hr_user_id:
        row = con.execute(
            """
            SELECT c.* FROM candidates c
            JOIN screening_runs r ON c.run_id = r.run_id
            WHERE c.candidate_id = ? AND r.hr_user_id = ?
            """,
            [candidate_id, hr_user_id]
        ).fetchone()
    else:
        row = con.execute("SELECT * FROM candidates WHERE candidate_id = ?", [candidate_id]).fetchone()
    con.close()
    if not row:
        return None
    return {
        "candidate_id": row[0],
        "run_id": row[1],
        "name": row[2],
        "email": row[3],
        "phone": row[4],
        "location": row[5],
        "experience_years": row[6],
        "degree": row[7],
        "score": row[8],
        "rank": row[9],
        "matched_skills": json.loads(row[10]) if row[10] else [],
        "missing_skills": json.loads(row[11]) if row[11] else [],
        "score_breakdown": json.loads(row[12]) if row[12] else {},
        "why_score": json.loads(row[13]) if row[13] else {},
        "parsed_data": json.loads(row[14]) if row[14] else {},
        "file_path": row[15],
        "filename": row[16]
    }

def get_all_runs(hr_user_id):
    con = get_db()
    runs = con.execute("""
        SELECT r.run_id, r.role, r.created_at, COUNT(c.candidate_id) as total_candidates, AVG(c.score) as avg_score
        FROM screening_runs r
        LEFT JOIN candidates c ON r.run_id = c.run_id
        WHERE r.hr_user_id = ?
        GROUP BY r.run_id, r.role, r.created_at
        ORDER BY r.created_at DESC
    """, [hr_user_id]).fetchall()
    con.close()
    return [{
        "run_id": r[0],
        "role": r[1],
        "created_at": r[2],
        "total_candidates": r[3],
        "avg_score": round(r[4], 1) if r[4] else 0.0
    } for r in runs]

def delete_run(run_id, hr_user_id):
    con = get_db()
    owned = con.execute("SELECT 1 FROM screening_runs WHERE run_id = ? AND hr_user_id = ?", [run_id, hr_user_id]).fetchone()
    if not owned:
        con.close()
        return False
    con.execute("DELETE FROM candidates WHERE run_id = ?", [run_id])
    con.execute("DELETE FROM screening_runs WHERE run_id = ?", [run_id])
    con.close()
    return True

def get_global_analytics(hr_user_id):
    con = get_db()
    all_candidates = con.execute("""
        SELECT c.skills_json, c.score, c.score_breakdown_json, c.experience_years
        FROM candidates c
        JOIN screening_runs r ON c.run_id = r.run_id
        WHERE r.hr_user_id = ?
    """, [hr_user_id]).fetchall()
    con.close()

    skill_counts = {}
    scores = []
    breakdowns = {"skills": [], "experience": [], "degree": [], "role": []}
    candidates = []

    for row in all_candidates:
        skills = json.loads(row[0]) if row[0] else []
        for s in skills:
            s_clean = s.strip().title()
            skill_counts[s_clean] = skill_counts.get(s_clean, 0) + 1

        if row[1] is not None:
            scores.append(row[1])

        score_breakdown = json.loads(row[2]) if row[2] else {}
        if score_breakdown:
            for k in breakdowns:
                if k in score_breakdown:
                    breakdowns[k].append(score_breakdown[k])

        candidates.append({
            "score_breakdown": score_breakdown,
            "experience_years": row[3],
        })

    top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "top_skills": top_skills,
        "scores": scores,
        "candidates": candidates,
        "avg_breakdowns": {
            k: round(sum(v)/len(v), 1) if v else 0 for k, v in breakdowns.items()
        }
    }

def get_all_candidates(hr_user_id):
    con = get_db()
    rows = con.execute("""
        SELECT c.*, r.role FROM candidates c
        JOIN screening_runs r ON c.run_id = r.run_id
        WHERE r.hr_user_id = ?
        ORDER BY c.score DESC
    """, [hr_user_id]).fetchall()
    con.close()

    candidate_list = []
    for row in rows:
        candidate_list.append({
            "candidate_id": row[0],
            "run_id": row[1],
            "name": row[2],
            "email": row[3],
            "phone": row[4],
            "location": row[5],
            "experience_years": row[6],
            "degree": row[7],
            "score": row[8],
            "rank": row[9],
            "matched_skills": json.loads(row[10]) if row[10] else [],
            "missing_skills": json.loads(row[11]) if row[11] else [],
            "score_breakdown": json.loads(row[12]) if row[12] else {},
            "why_score": json.loads(row[13]) if row[13] else {},
            "parsed_data": json.loads(row[14]) if row[14] else {},
            "file_path": row[15],
            "filename": row[16],
            "id": row[0],
            "years": row[6],
            "role_title": row[17],
        })
    return candidate_list




def save_resume_report(report_id, candidate_user_id, filename, file_path, resume_text, parsed_data, report):
    con = get_db()
    # Enforce single-resume-per-candidate: remove any previous report first
    old_paths = con.execute(
        "SELECT file_path FROM resume_reports WHERE candidate_user_id = ?",
        [candidate_user_id]
    ).fetchall()
    con.execute("DELETE FROM resume_reports WHERE candidate_user_id = ?", [candidate_user_id])

    con.execute(
        "INSERT INTO resume_reports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            report_id,
            candidate_user_id,
            filename,
            file_path,
            resume_text,
            json.dumps(parsed_data),
            report.get("ats_score"),
            json.dumps(report),
            datetime.utcnow()
        ]
    )
    con.close()

    # Clean up old resume files from disk
    for (old_path,) in old_paths:
        if old_path and old_path != file_path and os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

def _report_row_to_dict(row):
    return {
        "report_id": row[0],
        "candidate_user_id": row[1],
        "filename": row[2],
        "file_path": row[3],
        "resume_text": row[4],
        "parsed_data": json.loads(row[5]) if row[5] else {},
        "ats_score": row[6],
        "report": json.loads(row[7]) if row[7] else {},
        "created_at": row[8],
    }

def get_latest_resume_report(candidate_user_id):
    con = get_db()
    row = con.execute(
        "SELECT * FROM resume_reports WHERE candidate_user_id = ? ORDER BY created_at DESC LIMIT 1",
        [candidate_user_id]
    ).fetchone()
    con.close()
    if not row:
        return None
    return _report_row_to_dict(row)

def get_resume_report_by_id(report_id, candidate_user_id=None):
    con = get_db()
    if candidate_user_id:
        row = con.execute(
            "SELECT * FROM resume_reports WHERE report_id = ? AND candidate_user_id = ?",
            [report_id, candidate_user_id]
        ).fetchone()
    else:
        row = con.execute("SELECT * FROM resume_reports WHERE report_id = ?", [report_id]).fetchone()
    con.close()
    if not row:
        return None
    return _report_row_to_dict(row)
