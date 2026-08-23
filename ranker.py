import re
from typing import Any, Dict, List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity




WEIGHTS = {
    "skills": 0.50,
    "experience": 0.20,
    "degree": 0.15,
    "role": 0.15,
}




def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, list):
        value = " ".join(str(x) for x in value)

    if isinstance(value, dict):
        value = " ".join(str(x) for x in value.values())

    return re.sub(
        r"\s+",
        " ",
        str(value).lower().strip()
    )


def normalize_list(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, str):
        return [
            x.strip()
            for x in re.split(r"[,;|\n]+", value)
            if x.strip()
        ]

    if isinstance(value, list):
        result = []

        for item in value:
            if isinstance(item, str):
                item = item.strip()

                if item:
                    result.append(item)

        return result

    return []




def clean_skill(skill: str) -> str:
    skill = normalize_text(skill)

    skill = re.sub(
        r"[^a-z0-9+#.\- ]",
        " ",
        skill
    )

    skill = re.sub(
        r"\s+",
        " ",
        skill
    ).strip()

    return skill


def skill_matches(candidate_skill: str, required_skill: str) -> bool:
    candidate_skill = clean_skill(candidate_skill)
    required_skill = clean_skill(required_skill)

    if not candidate_skill or not required_skill:
        return False

    if candidate_skill == required_skill:
        return True

    if (
        candidate_skill in required_skill
        or required_skill in candidate_skill
    ):
        return True

    candidate_words = set(candidate_skill.split())
    required_words = set(required_skill.split())

    if not candidate_words or not required_words:
        return False

    overlap = len(
        candidate_words.intersection(required_words)
    )

    return overlap >= min(
        len(candidate_words),
        len(required_words)
    )


def calculate_skill_score(
    candidate_skills: List[str],
    required_skills: List[str]
):
    candidate_skills = [
        clean_skill(x)
        for x in candidate_skills
        if clean_skill(x)
    ]

    required_skills = [
        clean_skill(x)
        for x in required_skills
        if clean_skill(x)
    ]

    if not required_skills:
        return 100.0, [], []

    matched = []
    missing = []

    for required in required_skills:

        found = False

        for candidate in candidate_skills:

            if skill_matches(candidate, required):
                matched.append(required)
                found = True
                break

        if not found:
            missing.append(required)

    score = (
        len(matched) / len(required_skills)
    ) * 100

    return score, matched, missing




def extract_years(value: Any) -> float:
    text = normalize_text(value)

    if not text:
        return 0.0

    patterns = [
        r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)",
        r"(\d+(?:\.\d+)?)\s*(?:year|yr)",
    ]

    values = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        for match in matches:

            try:
                values.append(float(match))
            except ValueError:
                pass

    if not values:
        return 0.0

    return max(values)


def calculate_experience_score(
    candidate_experience: Any,
    job_description: str
):
    candidate_years = extract_years(
        candidate_experience
    )

    required_years = extract_years(
        job_description
    )

    if required_years <= 0:

        if candidate_years >= 5:
            return 100.0, candidate_years, required_years

        if candidate_years >= 3:
            return 90.0, candidate_years, required_years

        if candidate_years >= 1:
            return 75.0, candidate_years, required_years

        return 60.0, candidate_years, required_years

    if candidate_years >= required_years:
        return 100.0, candidate_years, required_years

    ratio = candidate_years / required_years

    score = max(
        0.0,
        min(100.0, ratio * 100)
    )

    return score, candidate_years, required_years



DEGREE_GROUPS = {

    "computer science": [
        "computer science",
        "computer engineering",
        "information technology",
        "information science",
        "software engineering",
    ],

    "information technology": [
        "information technology",
        "information science",
        "computer science",
        "computer engineering",
    ],

    "engineering": [
        "engineering",
        "b.e",
        "be",
        "b.tech",
        "btech",
        "m.e",
        "m.tech",
        "me",
        "mtech",
    ],

    "business": [
        "business",
        "management",
        "mba",
        "bba",
    ],
}


def degree_match(
    candidate_degrees: Any,
    job_description: str
) -> float:

    candidate_text = normalize_text(
        candidate_degrees
    )

    jd_text = normalize_text(
        job_description
    )

    if not candidate_text:
        return 40.0

    # Exact degree keywords
    if (
        "computer science" in jd_text
        and (
            "computer science" in candidate_text
            or "computer engineering" in candidate_text
            or "information technology" in candidate_text
        )
    ):
        return 100.0

    if (
        "information technology" in jd_text
        and (
            "information technology" in candidate_text
            or "information science" in candidate_text
            or "computer science" in candidate_text
        )
    ):
        return 100.0

    if (
        "engineering" in jd_text
        and "engineering" in candidate_text
    ):
        return 90.0

    if "b.tech" in candidate_text or "btech" in candidate_text:
        return 80.0

    if "b.e" in candidate_text:
        return 80.0

    if "bachelor" in candidate_text:
        return 70.0

    if "master" in candidate_text:
        return 85.0

    return 50.0




def calculate_role_score(
    candidate: Dict[str, Any],
    target_role: str
) -> float:

    target = normalize_text(target_role)

    candidate_role = normalize_text(
        candidate.get("Designation")
        or candidate.get("designation")
        or candidate.get("Role")
        or candidate.get("role")
    )

    if not candidate_role:
        return 50.0

    if candidate_role == target:
        return 100.0

    target_words = set(target.split())
    candidate_words = set(candidate_role.split())

    if not target_words:
        return 50.0

    overlap = len(
        target_words.intersection(candidate_words)
    )

    score = (
        overlap / len(target_words)
    ) * 100

    return max(
        30.0,
        min(100.0, score)
    )




def calculate_text_similarity(
    candidate: Dict[str, Any],
    job_description: str
) -> float:

    candidate_text = normalize_text(
        candidate.get("raw_text")
        or candidate.get("text")
        or candidate.get("content")
        or ""
    )

    jd_text = normalize_text(
        job_description
    )

    if not candidate_text or not jd_text:
        return 0.0

    try:

        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=5000
        )

        matrix = vectorizer.fit_transform([
            candidate_text,
            jd_text
        ])

        similarity = cosine_similarity(
            matrix[0:1],
            matrix[1:2]
        )[0][0]

        return float(similarity * 100)

    except Exception:
        return 0.0




COMMON_SKILLS = [
    "python",
    "java",
    "javascript",
    "typescript",
    "c",
    "c++",
    "c#",
    "sql",
    "mysql",
    "postgresql",
    "mongodb",
    "redis",
    "html",
    "css",
    "react",
    "react.js",
    "angular",
    "vue",
    "node",
    "node.js",
    "express",
    "django",
    "flask",
    "fastapi",
    "spring",
    "spring boot",
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "gcp",
    "git",
    "github",
    "linux",
    "tensorflow",
    "pytorch",
    "machine learning",
    "deep learning",
    "data analysis",
    "data science",
    "pandas",
    "numpy",
    "scikit-learn",
    "power bi",
    "tableau",
    "excel",
    "rest api",
    "api",
    "graphql",
    "firebase",
    "figma",
    "communication",
    "leadership",
    "problem solving",
]


def extract_required_skills(job_description: str) -> List[str]:

    text = normalize_text(
        job_description
    )

    found = []

    for skill in COMMON_SKILLS:

        skill_normalized = normalize_text(skill)

        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(skill_normalized)
            + r"(?![a-z0-9])"
        )

        if re.search(pattern, text):
            found.append(skill)

    return found




def generate_why_score(
    skill_score,
    matched_skills,
    missing_skills,
    experience_score,
    candidate_years,
    required_years,
    degree_score,
    role_score,
    target_role
):

    if matched_skills:

        skills_text = (
            f"Matched {len(matched_skills)} required "
            f"skill(s): "
            f"{', '.join(matched_skills[:8])} "
            f"({skill_score:.0f}% skill match)."
        )

    else:

        skills_text = (
            "No required skills were confidently matched."
        )

    if required_years > 0:

        if candidate_years >= required_years:

            experience_text = (
                f"Has approximately {candidate_years:g} "
                f"year(s) of experience, meeting the "
                f"required {required_years:g} year(s)."
            )

        else:

            experience_text = (
                f"Has approximately {candidate_years:g} "
                f"year(s) compared with {required_years:g} "
                f"required year(s)."
            )

    else:

        experience_text = (
            f"Approximately {candidate_years:g} "
            f"year(s) of experience detected."
        )

    if degree_score >= 85:

        degree_text = (
            "Education appears strongly aligned with "
            "the job requirements."
        )

    elif degree_score >= 65:

        degree_text = (
            "Education has a reasonable match with "
            "the job requirements."
        )

    else:

        degree_text = (
            "Education has limited evidence of a "
            "direct match."
        )

    if role_score >= 85:

        role_text = (
            f"Previous role/designation is strongly "
            f"aligned with {target_role}."
        )

    elif role_score >= 60:

        role_text = (
            f"Previous role has partial alignment "
            f"with {target_role}."
        )

    else:

        role_text = (
            f"Previous role has limited direct "
            f"alignment with {target_role}."
        )

    return {
        "skills": skills_text,
        "experience": experience_text,
        "degree": degree_text,
        "role": role_text,
        "missing_skills": missing_skills,
    }




def score_candidate(
    candidate: Dict[str, Any],
    job_description: str,
    target_role: str,
    required_skills: List[str]
):

    parsed = candidate.get(
        "parsed_data",
        candidate
    )

    candidate_skills = normalize_list(
        parsed.get("Skills")
        or parsed.get("skills")
        or []
    )

    candidate_degree = (
        parsed.get("Degree")
        or parsed.get("degree")
        or []
    )

    candidate_experience = (
        parsed.get("Work Experience")
        or parsed.get("work_experience")
        or parsed.get("experience")
        or []
    )

   

    skill_score, matched_skills, missing_skills = (
        calculate_skill_score(
            candidate_skills,
            required_skills
        )
    )

   

    (
        experience_score,
        candidate_years,
        required_years
    ) = calculate_experience_score(
        candidate_experience,
        job_description
    )

    
    degree_score = degree_match(
        candidate_degree,
        job_description
    )

    
    role_score = calculate_role_score(
        parsed,
        target_role
    )


    final_score = (
        skill_score * WEIGHTS["skills"]
        + experience_score * WEIGHTS["experience"]
        + degree_score * WEIGHTS["degree"]
        + role_score * WEIGHTS["role"]
    )

    final_score = round(
        max(0.0, min(100.0, final_score)),
        2
    )

  

    why_score = generate_why_score(
        skill_score=skill_score,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        experience_score=experience_score,
        candidate_years=candidate_years,
        required_years=required_years,
        degree_score=degree_score,
        role_score=role_score,
        target_role=target_role
    )

    name = (
        parsed.get("Name")
        or parsed.get("name")
        or candidate.get("filename")
        or "Unknown Candidate"
    )

    return {
        "name": name,
        "score": final_score,
        "years": candidate_years,
        "why_score": why_score,
        "score_breakdown": {
            "skills": round(skill_score, 2),
            "experience": round(experience_score, 2),
            "degree": round(degree_score, 2),
            "role": round(role_score, 2),
        },
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        # PRESERVE PARSED DATA
        "parsed_data": parsed,
        "filename": candidate.get("filename")
    }




def rank_candidates(
    candidates: List[Dict[str, Any]],
    job_description: str,
    role: str
) -> List[Dict[str, Any]]:

    if not candidates:
        return []


    required_skills = extract_required_skills(
        job_description
    )


    ranked_candidates = []

    for candidate in candidates:

        result = score_candidate(
            candidate=candidate,
            job_description=job_description,
            target_role=role,
            required_skills=required_skills
        )

        ranked_candidates.append(result)

    

    ranked_candidates.sort(
        key=lambda x: x.get("score", 0),
        reverse=True
    )

    

    for index, candidate in enumerate(
        ranked_candidates,
        start=1
    ):

        candidate["rank"] = index

    return ranked_candidates




def rank_candidates_with_explanation(
    candidates,
    job_description,
    role
):

    return rank_candidates(
        candidates=candidates,
        job_description=job_description,
        role=role
    )