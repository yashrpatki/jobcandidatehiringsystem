import duckdb
import re

DB_PATH = "skills.duckdb"


def clean(text):
    return re.sub(r"\s+", " ", str(text)).strip()


def load_skills():

    con = duckdb.connect(DB_PATH, read_only=True)

    columns = [
        row[0]
        for row in con.execute(
            "DESCRIBE skills"
        ).fetchall()
    ]

    rows = con.execute(
        "SELECT * FROM skills"
    ).fetchall()

    con.close()

    skill_col = None

    for col in columns:
        if col.lower() in {
            "skill",
            "skills",
            "skill_name",
            "skill name"
        }:
            skill_col = col
            break

    if skill_col is None:
        raise ValueError(
            "Could not find Skill column in DuckDB"
        )

    index = columns.index(skill_col)

    return [
        clean(row[index])
        for row in rows
        if row[index]
    ]


SKILLS = load_skills()


def extract_skills(text):

    text_lower = text.lower()
    found = []
    seen = set()

    for skill in sorted(
        SKILLS,
        key=len,
        reverse=True
    ):

        skill_lower = skill.lower()

        pattern = (
            r"(?<!\w)"
            + re.escape(skill_lower)
            + r"(?!\w)"
        )

        if re.search(
            pattern,
            text_lower
        ):

            key = skill_lower

            if key not in seen:
                seen.add(key)
                found.append(skill)

    return found


def extract_experience(text):

    patterns = [
        r"(\d+)\s*\+?\s*(?:years?|yrs?)\s+of\s+experience",
        r"(\d+)\s*\+?\s*(?:years?|yrs?)\s+experience",
        r"minimum\s+(?:of\s+)?(\d+)\s*(?:years?|yrs?)",
        r"at least\s+(\d+)\s*(?:years?|yrs?)",
        r"(\d+)\s*-\s*(\d+)\s*(?:years?|yrs?)"
    ]

    values = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            re.I
        )

        for match in matches:

            if isinstance(match, tuple):

                for value in match:
                    if value.isdigit():
                        values.append(
                            int(value)
                        )

            elif match.isdigit():
                values.append(
                    int(match)
                )

    if not values:
        return None

    return max(values)


def extract_degree(text):

    patterns = [
        r"\bB\.?\s*E\.?\b",
        r"\bB\.?\s*Tech\.?\b",
        r"\bB\.?\s*Sc\.?\b",
        r"\bB\.?\s*CA\.?\b",
        r"\bB\.?\s*Com\.?\b",
        r"\bM\.?\s*E\.?\b",
        r"\bM\.?\s*Tech\.?\b",
        r"\bM\.?\s*Sc\.?\b",
        r"\bM\.?\s*CA\.?\b",
        r"\bMBA\b",
        r"\bPh\.?\s*D\.?\b",
        r"\bBachelor(?:'s)?\b",
        r"\bMaster(?:'s)?\b",
        r"\bDiploma\b"
    ]

    found = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            re.I
        )

        found.extend(matches)

    result = []

    for degree in found:

        degree = clean(degree)

        if degree.lower() not in [
            x.lower()
            for x in result
        ]:
            result.append(degree)

    return result


def extract_seniority(role, text):

    value = f"{role} {text}".lower()

    levels = [
        ("intern", "intern"),
        ("trainee", "trainee"),
        ("junior", "junior"),
        ("entry level", "entry"),
        ("entry-level", "entry"),
        ("mid level", "mid"),
        ("mid-level", "mid"),
        ("senior", "senior"),
        ("lead", "lead"),
        ("principal", "principal"),
        ("staff", "staff"),
        ("manager", "manager")
    ]

    for keyword, level in levels:

        if keyword in value:
            return level

    return None


def extract_role_keywords(role):

    if not role:
        return []

    role = clean(role)

    words = re.findall(
        r"[A-Za-z]+",
        role.lower()
    )

    stopwords = {
        "the",
        "a",
        "an",
        "of",
        "and",
        "for",
        "in"
    }

    return [
        word
        for word in words
        if word not in stopwords
    ]


def process_job_description(
    role,
    job_description
):

    job_description = clean(
        job_description
    )

    role = clean(role)

    skills = extract_skills(
        job_description
    )

    experience = extract_experience(
        job_description
    )

    degrees = extract_degree(
        job_description
    )

    seniority = extract_seniority(
        role,
        job_description
    )

    role_keywords = extract_role_keywords(
        role
    )

    return {
        "role": role,
        "role_keywords": role_keywords,
        "seniority": seniority,
        "skills": skills,
        "minimum_experience": experience,
        "degrees": degrees,
        "job_description": job_description
    }