import re

SECTION_PATTERNS = {
    "Work Experience": r"\b(work experience|professional experience|employment history|experience)\b",
    "Education": r"\b(education|academic background|qualifications)\b",
    "Skills": r"\b(skills|technical skills|core competencies)\b",
    "Projects": r"\b(projects|personal projects|academic projects)\b",
    "Summary/Objective": r"\b(summary|objective|career objective|professional summary|about me)\b",
}

ACTION_VERBS = {
    "led", "built", "developed", "designed", "managed", "created", "implemented",
    "improved", "increased", "reduced", "launched", "delivered", "achieved",
    "optimized", "automated", "coordinated", "analyzed", "engineered", "drove",
    "spearheaded", "established", "streamlined", "executed", "collaborated",
    "mentored", "architected", "deployed", "resolved", "generated"
}

BULLET_CHARS = ("•", "-", "*", "◦", "‣")


def _word_count(text):
    return len(re.findall(r"[A-Za-z]+", text))


def _has_section(text_lower, pattern):
    return re.search(pattern, text_lower) is not None


def _count_bullets(text):
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(BULLET_CHARS):
            count += 1
    return count


def _count_action_verbs(text):
    words = re.findall(r"[A-Za-z]+", text.lower())
    return sum(1 for w in words if w in ACTION_VERBS)


def generate_ats_report(resume_text, parsed_data):
    """
    Produces a professional, actionable ATS-friendliness report for a single
    candidate-uploaded resume. Returns a dict with an overall score, a list
    of individual checks (pass/warn/fail), key strengths, and improvement
    suggestions.
    """
    text = resume_text or ""
    text_lower = text.lower()
    parsed_data = parsed_data or {}

    checks = []
    total_points = 0
    max_points = 0

    def add_check(name, status, message, points, weight):
        nonlocal total_points, max_points
        max_points += weight
        total_points += points
        checks.append({
            "name": name,
            "status": status,  # "pass" | "warn" | "fail"
            "message": message,
        })

    # --- Contact info -----------------------------------------------------
    email = parsed_data.get("Email")
    phone = parsed_data.get("Phone")

    if email:
        add_check("Email Address", "pass", "A valid email address was found — recruiters and ATS software can reach you.", 10, 10)
    else:
        add_check("Email Address", "fail", "No email address was detected. Add a professional email near the top of your resume.", 0, 10)

    if phone:
        add_check("Phone Number", "pass", "A phone number was found on your resume.", 10, 10)
    else:
        add_check("Phone Number", "fail", "No phone number was detected. Include a reachable phone number in your header.", 0, 10)

    # --- Name ---------------------------------------------------------------
    name = parsed_data.get("Name")
    if name:
        add_check("Candidate Name", "pass", "Your name was clearly detected at the top of the document.", 5, 5)
    else:
        add_check("Candidate Name", "warn", "Your name wasn't clearly detected. Make sure it's on its own line at the very top, without unusual fonts, icons, or a header/footer.", 2, 5)

    # --- Skills ---------------------------------------------------------------
    skills = parsed_data.get("Skills", [])
    skill_count = len(skills)
    if skill_count >= 8:
        add_check("Skills Section", "pass", f"{skill_count} distinct skills were detected — a strong, keyword-rich skills section.", 15, 15)
    elif skill_count >= 3:
        add_check("Skills Section", "warn", f"Only {skill_count} skills were detected. Add more relevant technical and soft skills so ATS keyword matching works in your favor.", 8, 15)
    else:
        add_check("Skills Section", "fail", "Very few or no skills were detected. Add a dedicated 'Skills' section listing your key tools, technologies, and competencies.", 0, 15)

    # --- Section headers -----------------------------------------------------
    section_points = 0
    section_weight = 30
    missing_sections = []
    for section_name, pattern in SECTION_PATTERNS.items():
        if _has_section(text_lower, pattern):
            section_points += section_weight / len(SECTION_PATTERNS)
        else:
            missing_sections.append(section_name)

    if not missing_sections:
        add_check("Standard Sections", "pass", "All standard resume sections were found (Summary, Experience, Education, Skills, Projects).", section_weight, section_weight)
    elif len(missing_sections) <= 2:
        add_check("Standard Sections", "warn", f"Missing or unclear section(s): {', '.join(missing_sections)}. Use clear, standard headings so ATS software can categorize your content correctly.", section_points, section_weight)
    else:
        add_check("Standard Sections", "fail", f"Several standard sections are missing or unclear: {', '.join(missing_sections)}. Structure your resume with clear headings like 'Work Experience', 'Education', and 'Skills'.", section_points, section_weight)

    # --- Length ---------------------------------------------------------------
    word_count = _word_count(text)
    if 350 <= word_count <= 1100:
        add_check("Resume Length", "pass", f"Your resume is about {word_count} words — a good length for ATS parsing and recruiter readability.", 10, 10)
    elif word_count < 350:
        add_check("Resume Length", "warn", f"Your resume is quite short (~{word_count} words). Add more detail on your experience, achievements, and skills.", 5, 10)
    else:
        add_check("Resume Length", "warn", f"Your resume is quite long (~{word_count} words). Consider trimming it to focus on your most relevant and recent experience.", 5, 10)

    # --- Bullet usage -----------------------------------------------------------
    bullet_count = _count_bullets(text)
    if bullet_count >= 5:
        add_check("Bullet Points", "pass", "Your resume uses bullet points to describe experience — this improves both readability and ATS parsing.", 10, 10)
    elif bullet_count >= 1:
        add_check("Bullet Points", "warn", "A few bullet points were found. Use bullet points consistently for each role to make achievements easy to scan.", 5, 10)
    else:
        add_check("Bullet Points", "fail", "No bullet points were detected. Break up paragraphs of text under each role into concise bullet points.", 0, 10)

    # --- Action verbs -----------------------------------------------------------
    verb_count = _count_action_verbs(text)
    if verb_count >= 6:
        add_check("Action-Oriented Language", "pass", f"Found {verb_count} strong action verbs (e.g. 'built', 'led', 'improved') — this makes your impact clear.", 10, 10)
    elif verb_count >= 2:
        add_check("Action-Oriented Language", "warn", f"Only {verb_count} strong action verbs were found. Start bullet points with verbs like 'developed', 'led', or 'increased' to highlight impact.", 5, 10)
    else:
        add_check("Action-Oriented Language", "fail", "Few or no strong action verbs were found. Rewrite bullet points to start with impactful verbs describing what you did and achieved.", 0, 10)

    # --- Overall score -----------------------------------------------------------
    ats_score = round((total_points / max_points) * 100) if max_points else 0
    ats_score = max(0, min(100, ats_score))

    strengths = [c["message"] for c in checks if c["status"] == "pass"]
    improvements = [c["message"] for c in checks if c["status"] in ("warn", "fail")]

    if ats_score >= 80:
        summary = "Your resume is well-optimized for ATS systems, with only minor improvements possible."
    elif ats_score >= 55:
        summary = "Your resume has a solid foundation but has a few gaps that could hurt your ATS match rate."
    else:
        summary = "Your resume may struggle to pass ATS screening in its current form. Addressing the items below should meaningfully improve it."

    return {
        "ats_score": ats_score,
        "summary": summary,
        "checks": checks,
        "strengths": strengths,
        "improvements": improvements,
        "word_count": word_count,
        "skill_count": skill_count,
    }
