import spacy
import duckdb
import re
from collections import defaultdict
from flashtext import KeywordProcessor


MODEL_NAMES = [
    "resume_ner_best",
    "resume_ner",
    "resume_ner_v2",
    "resume_ner_v3"
]

DB_FILE = "skills.duckdb"


models = []

for name in MODEL_NAMES:
    try:
        models.append(spacy.load(name))
        break  # stop after the first model that loads successfully
    except Exception:
        pass

if not models:
    models = [spacy.load("en_core_web_sm")]


LABEL_MAP = {
    "Location": "Location",
    "Skills": "Skills",
    "Designation": "Previous Designation",
    "Degree": "Degree",
    "College Name": "University",
    "Work Experience": "Work Experience",
    "Companies worked at": "Companies"
}


EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
)

PHONE_PATTERN = re.compile(
    r'(?<!\d)(?:\+?\d{1,3}[\s.-]?)?'
    r'(?:\(?\d{3}\)?[\s.-]?)'
    r'\d{3}[\s.-]?\d{4}(?!\d)'
)


JOB_WORDS = {
    "engineer",
    "developer",
    "manager",
    "analyst",
    "designer",
    "consultant",
    "intern",
    "architect",
    "programmer",
    "administrator",
    "specialist",
    "director",
    "lead",
    "officer",
    "executive",
    "technician"
}


NAME_NOISE = {
    "resume",
    "curriculum vitae",
    "curriculum",
    "vitae",
    "cv",
    "profile",
    "professional profile",
    "personal details",
    "contact",
    "contact details",
    "objective",
    "summary",
    "professional summary",
    "about me",
    "experience",
    "education",
    "skills",
    "projects",
    "certifications",
    "achievements",
    "references",
    "work experience"
}


SKILL_NOISE = {
    "hindi",
    "english",
    "availability",
    "immediate",
    "developing",
    "developing apis",
    "reviews",
    "changes",
    "code",
    "extracting",
    "dashboard",
    "profiles",
    "ranking",
    "digital",
    "operational data",
    "performance metrics",
    "nextgen software",
    "collaborative",
    "developers",
    "deployment"
}


DEGREE_PATTERNS = [
    r"\bb\.?\s*e\.?\b",
    r"\bb\.?\s*tech\.?\b",
    r"\bb\.?\s*sc\.?\b",
    r"\bb\.?\s*ca\.?\b",
    r"\bb\.?\s*ba\.?\b",
    r"\bb\.?\s*com\.?\b",
    r"\bm\.?\s*e\.?\b",
    r"\bm\.?\s*tech\.?\b",
    r"\bm\.?\s*sc\.?\b",
    r"\bm\.?\s*ca\.?\b",
    r"\bm\.?\s*ba\.?\b",
    r"\bm\.?\s*com\.?\b",
    r"\bph\.?\s*d\.?\b",
    r"\bdiploma\b",
    r"\bbachelor of\b",
    r"\bmaster of\b",
    r"\bdoctor of philosophy\b"
]


DEGREE_NOISE = {
    "immediate",
    "availability",
    "full stack developer",
    "software engineer",
    "software developer",
    "senior software engineer",
    "junior software engineer",
    "developer",
    "engineer",
    "programmer",
    "intern",
    "manager",
    "analyst",
    "designer"
}


def clean(text):

    text = str(text).strip()

    text = re.sub(
        r'^(location|skills|availability|language|languages)\s*:\s*',
        '',
        text,
        flags=re.I
    )

    text = re.sub(
        r'^[*•|–—:\-\s]+',
        '',
        text
    )

    text = re.sub(
        r'[*•|–—:\-\s]+$',
        '',
        text
    )

    text = re.sub(
        r'\s+',
        ' ',
        text
    )

    return text.strip()


def norm(text):
    return clean(text).lower()


def unique(items):

    result = []
    seen = set()

    for item in items:

        item = clean(item)

        if not item:
            continue

        key = norm(item)

        if key not in seen:
            seen.add(key)
            result.append(item)

    return result


def load_skills():

    con = duckdb.connect(
        DB_FILE,
        read_only=True
    )

    columns = [
        x[0]
        for x in con.execute(
            "DESCRIBE skills"
        ).fetchall()
    ]

    rows = con.execute(
        "SELECT * FROM skills"
    ).fetchall()

    con.close()

    skill_column = None

    for column in columns:

        if column.lower() in {
            "skill",
            "skills",
            "skill name",
            "skill_name"
        }:
            skill_column = column
            break

    if skill_column is None:
        raise ValueError(
            "No skill column found in skills.duckdb"
        )

    index = columns.index(skill_column)

    return {
        norm(row[index]): clean(row[index])
        for row in rows
        if row[index]
    }


SKILLS = load_skills()

SKILL_KEYWORDS = KeywordProcessor(
    case_sensitive=False
)

for key, value in SKILLS.items():

    if key:
        SKILL_KEYWORDS.add_keyword(
            key,
            value
        )


def find_skills(text):

    text = clean(text)

    if not text:
        return []

    found = SKILL_KEYWORDS.extract_keywords(text)

    return unique([
        x for x in found
        if norm(x) not in SKILL_NOISE
    ])


def extract_name(text):

    lines = [
        clean(x)
        for x in text.splitlines()
        if clean(x)
    ]

    headings = {
        "resume",
        "cv",
        "curriculum vitae",
        "contact",
        "contact details",
        "personal details",
        "personal statement",
        "personal profile",
        "profile",
        "professional profile",
        "professional summary",
        "summary",
        "about me",
        "objective",
        "career objective",
        "skills",
        "technical skills",
        "soft skills",
        "languages",
        "education",
        "educational background",
        "experience",
        "work experience",
        "employment history",
        "projects",
        "my projects",
        "personal projects",
        "certifications",
        "achievements",
        "interests",
        "references",
        "declaration",
        "hobbies"
    }

    bad_phrases = {
        "personal statement",
        "personal profile",
        "professional profile",
        "professional summary",
        "career objective",
        "work experience",
        "educational background",
        "technical skills",
        "soft skills",
        "contact details",
        "personal details",
        "my projects",
        "personal projects",
        "computer science",
        "information technology",
        "software engineering",
        "game development",
        "web development",
        "data science",
        "machine learning"
    }

    candidates = []

    for index, line in enumerate(lines[:50]):

        value = line.strip()
        lower = value.lower()

        if not value:
            continue

        if lower in headings:
            continue

        if lower in bad_phrases:
            continue

        if any(
            phrase in lower
            for phrase in bad_phrases
        ):
            continue

        if EMAIL_PATTERN.search(value):
            continue

        if PHONE_PATTERN.search(value):
            continue

        if re.search(
            r'linkedin|github|https?://|www\.|@',
            value,
            re.I
        ):
            continue

        if any(char.isdigit() for char in value):
            continue

        words = value.split()

        if not 2 <= len(words) <= 4:
            continue

        if not re.fullmatch(
            r"[A-Za-z]+(?:[ .'-][A-Za-z]+)*",
            value
        ):
            continue

        if any(
            word.lower().strip(".,")
            in JOB_WORDS
            for word in words
        ):
            continue

        score = 0

        if len(words) == 2:
            score += 12

        elif len(words) == 3:
            score += 6

        if value.isupper():
            score += 15

        elif value.istitle():
            score += 8

        if all(
            word[0].isupper()
            for word in words
        ):
            score += 5

        if index < 8:
            score += 5

        if index < 20:
            score += 2

        candidates.append(
            (score, index, value)
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: (
            x[0],
            -x[1]
        ),
        reverse=True
    )

    return " ".join(
        candidates[0][2].split()[:2]
    ).title()

def get_entities(text):

    grouped = defaultdict(set)

    for i, model in enumerate(models):

        try:
            doc = model(text)
        except:
            continue

        for ent in doc.ents:

            if ent.label_ not in LABEL_MAP:
                continue

            value = clean(ent.text)

            if value:
                grouped[
                    (norm(value), ent.label_)
                ].add(i)

    entities = []

    for (value, label), votes in grouped.items():

        entities.append({
            "text": value,
            "label": label,
            "votes": len(votes)
        })

    entities.sort(
        key=lambda x: (
            x["votes"],
            len(x["text"])
        ),
        reverse=True
    )

    return entities


def clean_location(value):

    value = clean(value)

    if not value:
        return None

    parts = []

    for part in value.split(","):

        part = clean(part)

        if part and norm(part) not in [
            norm(x)
            for x in parts
        ]:
            parts.append(part)

    return ", ".join(parts[:2])


def clean_company(value):

    value = clean(value)

    if not value:
        return None

    value = re.sub(
        r'\s*\|?\s*'
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)'
        r'\.?\s+\d{4}.*$',
        '',
        value,
        flags=re.I
    )

    value = value.strip(
        " -–—|:;,. "
    )

    if norm(value) in {
        "company",
        "companies",
        "company name",
        "present",
        "current",
        "immediate",
        "availability"
    }:
        return None

    return value


def clean_degree(value):

    value = clean(value)

    if not value:
        return None

    if norm(value) in DEGREE_NOISE:
        return None

    for pattern in DEGREE_PATTERNS:

        if re.search(
            pattern,
            value,
            re.I
        ):
            return value

    return None


def parse_resume(text):

    email = EMAIL_PATTERN.search(text)
    phone = PHONE_PATTERN.search(text)

    result = {
        "Name": extract_name(text),
        "Email": email.group(0) if email else None,
        "Phone": phone.group(0) if phone else None,
        "Location": [],
        "Skills": [],
        "Work Experience": [],
        "Previous Designation": [],
        "Degree": [],
        "University": [],
        "Companies": []
    }

    entities = get_entities(text)

    for entity in entities:

        label = entity["label"]
        value = entity["text"]
        key = LABEL_MAP[label]

        if key == "Skills":

            result["Skills"].extend(
                find_skills(value)
            )

        elif key == "Location":

            value = clean_location(value)

            if value:
                result["Location"].append(value)

        elif key == "Companies":

            value = clean_company(value)

            if value:
                result["Companies"].append(value)

        elif key == "Degree":

            value = clean_degree(value)

            if value:
                result["Degree"].append(value)

        elif key == "University":

            value = clean(value)

            if value:
                result["University"].append(value)

        elif key == "Previous Designation":

            value = clean(value)

            if value:
                result["Previous Designation"].append(value)

        elif key == "Work Experience":

            value = clean(value)

            if value:
                result["Work Experience"].append(value)

    for key in result:

        if isinstance(result[key], list):
            result[key] = unique(
                result[key]
            )

    result["Location"] = result["Location"][:1]

    return result
