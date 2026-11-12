"""Generate a realistic, deliberately messy synthetic student survey.

Run from the project root::

    python sample_data/generate_sample.py

Output: ``sample_data/student_wellbeing_survey.csv`` (300 rows, UTF-8 with BOM so
Excel shows Arabic correctly).

Everything here is FAKE. Names come from short lists, emails use the reserved
``example.com`` / ``example.edu`` domains, and phone numbers use a
``0100000xxxx`` pattern. No real person is described.

How it works
------------
Each simulated student has hidden "true" traits (a stress level and a study
discipline level). Their answers are generated *from* those traits plus random
noise. That gives the dataset real patterns for the analysis to discover:

* Engineering students and students in later years report more stress.
* Students who sleep less report more stress.
* Students who use study groups score higher on the study-habits scale.
* Stressed students are less satisfied with their wellbeing.
* Open-ended answers follow the same story: students living with family
  complain about the commute, students in shared apartments about money, etc.

Then we inject the kinds of problems real survey exports have, so the cleaning
step has something to find (counts are printed when you run the script):

* duplicate submissions (re-submitted forms and copy-pasted rows)
* incomplete responses (people who dropped out half-way)
* straight-liners (same answer for every grid item)
* speeders (finished far faster than anyone could read the questions)
* numeric typos / outliers (age 199, 24 hours of sleep)
* inconsistent capitalisation and stray spaces in choice answers
* personal data typed into free-text answers

Column layout mixes the two common exporters on purpose: Microsoft Forms style
``Start time`` / ``Completion time`` (needed to detect speeders; Google Forms
only exports one timestamp) and Google Forms style grid headers
``Question [item]`` (used to group Likert items into scales).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_BASE = 292  # + 8 duplicates = 300 rows
OUTPUT = Path(__file__).with_name("student_wellbeing_survey.csv")

# --------------------------------------------------------------------------- #
# Column names
# --------------------------------------------------------------------------- #
STRESS_Q = "Over the past month, how much do you agree?"
STRESS_ITEMS = [
    "I feel overwhelmed by my coursework",
    "I find it hard to relax after studying",
    "I worry about my grades",
    "I feel nervous before exams",
    "I have trouble sleeping because of university stress",
]
HABITS_Q = "Study habits (1 = Strongly disagree, 5 = Strongly agree)"
HABIT_ITEMS = [
    "I plan my study time in advance",
    "I start assignments well before the deadline",
    "I review lecture material every week",
    "I keep a fixed place and time for studying",
]
LIKERT_LABELS = ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"]

COL_METHODS = "Which study methods do you use? (select all that apply)"
COL_SATISFACTION = "Overall, how satisfied are you with your wellbeing this semester? (1-5)"
COL_CHALLENGE = "What is the biggest challenge you face in your studies?"
COL_HELP = "What would help you manage stress better?"

# --------------------------------------------------------------------------- #
# Fake identity pools
# --------------------------------------------------------------------------- #
FIRST = ["Ahmed", "Mohamed", "Omar", "Youssef", "Mariam", "Nour", "Salma", "Hana", "Karim",
         "Ali", "Laila", "Farida", "Mostafa", "Habiba", "Ziad", "Malak", "Seif", "Jana",
         "Adham", "Rana", "Hassan", "Yasmin", "Tarek", "Dina"]
LAST = ["Hassan", "Ibrahim", "Mahmoud", "Abdelrahman", "Saleh", "Farouk", "Kamal", "Mansour",
        "ElSayed", "Nabil", "Fawzy", "Gamal", "Shawky", "Ashraf", "Ezzat", "Rashad"]
ARABIC_NAMES = ["أحمد حسن", "مريم إبراهيم", "عمر محمود", "نور كمال", "يوسف صالح",
                "سلمى فاروق", "كريم منصور", "هنا جمال"]

STUDY_METHODS = {  # option -> probability a student ticks it
    "Lecture notes": 0.80,
    "Past exams": 0.60,
    "YouTube videos": 0.65,
    "Study groups": 0.35,
    "Textbook": 0.30,
    "AI tools": 0.50,
}

# --------------------------------------------------------------------------- #
# Open-ended answer banks: theme -> (English variants, Arabic variants)
# --------------------------------------------------------------------------- #
CHALLENGES: dict[str, tuple[list[str], list[str]]] = {
    "time": (
        ["Managing my time between lectures, assignments and labs",
         "I can never find enough time to finish everything before the deadline",
         "Balancing study time with everything else in my life",
         "Too many deadlines in the same week and no time to plan",
         "Organizing my schedule, I always feel behind",
         "Time management, especially during midterms"],
        ["تنظيم الوقت بين المحاضرات والتاسكات",
         "مش بلاقي وقت كفاية أخلص كل حاجة قبل الديدلاين",
         "صعوبة إدارة الوقت خصوصا وقت الميدترم",
         "كتر الديدلاينز في نفس الأسبوع",
         "إدارة الوقت والتوفيق بين الدراسة وحياتي"],
    ),
    "workload": (
        ["The workload is too heavy, especially in engineering courses",
         "Too many assignments and projects at the same time",
         "The amount of material we have to cover every week is huge",
         "Heavy course load and long lab reports",
         "Projects and quizzes every single week",
         "The courses are very demanding and the content is a lot"],
        ["ضغط المذاكرة كبير جدا والمواد كتير",
         "كمية الأسايمنتس والبروجكتس كبيرة جدا",
         "المنهج طويل والوقت قليل",
         "الشغل المطلوب كل أسبوع كتير أوي",
         "ضغط الدراسة والكويزات كل أسبوع"],
    ),
    "exams": (
        ["I get very anxious before exams and forget what I studied",
         "Exam stress, I panic during finals",
         "Fear of failing and getting a low GPA",
         "Pressure to keep my GPA high for the scholarship",
         "I overthink about my grades all the time"],
        ["بتوتر جدا قبل الامتحانات وبنسى اللي ذاكرته",
         "الخوف من إني أسقط أو المعدل يقل",
         "قلق الامتحانات بيأثر عليا جدا",
         "ضغط إني أحافظ على المعدل عشان المنحة"],
    ),
    "commute": (
        ["The commute to Sheikh Zayed takes almost two hours every day",
         "Long travel time to campus leaves me exhausted",
         "Transportation is expensive and takes too long",
         "I spend too much time on the university bus",
         "Traffic on the way to university wastes my day"],
        ["المواصلات للجامعة بتاخد ساعتين كل يوم",
         "الطريق طويل وبوصل البيت تعبان",
         "المشوار للشيخ زايد مرهق جدا",
         "باص الجامعة بياخد وقت كبير"],
    ),
    "motivation": (
        ["Procrastination, I keep delaying studying until the last minute",
         "Staying motivated, especially in courses I don't like",
         "Distraction from my phone and social media",
         "I lose focus easily and can't concentrate for long",
         "Lack of motivation after a long day"],
        ["التأجيل، بفضل أأجل المذاكرة لآخر لحظة",
         "مفيش حافز أذاكر المواد اللي مش بحبها",
         "الموبايل والسوشيال ميديا بيشتتوني",
         "مش بقدر أركز فترة طويلة"],
    ),
    "money": (
        ["Tuition fees and living costs are a constant worry",
         "Working part-time to pay rent leaves little time to study",
         "Rent and expenses in the shared apartment are stressful",
         "Financial pressure on my family because of the fees"],
        ["مصاريف الجامعة والسكن عاملة ضغط عليا",
         "بشتغل بارت تايم عشان أدفع الإيجار ومفيش وقت أذاكر",
         "الضغط المادي على أهلي بسبب المصاريف"],
    ),
}

HELPERS: dict[str, tuple[list[str], list[str]]] = {
    "rest": (
        ["Getting more sleep and taking proper breaks",
         "Having actual days off without assignments",
         "A better sleep schedule",
         "Short breaks between lectures to rest",
         "Sleeping at least 7 hours before exams"],
        ["إني أنام كويس وآخد بريكات",
         "يوم أجازة من غير أسايمنتس",
         "تنظيم مواعيد النوم",
         "راحة بين المحاضرات"],
    ),
    "exercise": (
        ["Going to the gym regularly",
         "Playing football with friends after class",
         "More sports activities on campus",
         "Walking or running in the morning clears my head",
         "Swimming or any physical activity"],
        ["إني أروح الجيم بانتظام",
         "ألعب كورة مع صحابي",
         "أنشطة رياضية أكتر في الجامعة",
         "المشي الصبح بيريحني"],
    ),
    "scheduling": (
        ["Professors coordinating deadlines so they are not all in one week",
         "Fewer quizzes and a more realistic workload",
         "Recorded lectures so I can review at my own pace",
         "Clearer course expectations and earlier announcements",
         "Spreading exams out over a longer period"],
        ["إن الدكاترة ينسقوا الديدلاينز مع بعض",
         "كويزات أقل وضغط أقل",
         "تسجيل المحاضرات عشان أراجع براحتي",
         "توزيع الامتحانات على فترة أطول"],
    ),
    "counseling": (
        ["Free counseling sessions at the university",
         "Someone professional to talk to about stress",
         "Mental health awareness and support from the university",
         "Easier access to the student counseling office"],
        ["جلسات دعم نفسي في الجامعة",
         "حد متخصص أتكلم معاه عن الضغط",
         "اهتمام أكتر بالصحة النفسية للطلبة"],
    ),
    "social": (
        ["Spending more time with friends and family",
         "Studying with friends instead of alone",
         "Talking to my family when I feel stressed",
         "Having a study group that supports each other"],
        ["أقضي وقت أكتر مع صحابي وأهلي",
         "أذاكر مع صحابي بدل ما أذاكر لوحدي",
         "الكلام مع أهلي لما أكون مضغوط"],
    ),
    "planning": (
        ["Learning how to plan my week properly",
         "Using a planner or a to-do list app",
         "Workshops on time management and study skills",
         "Starting assignments earlier instead of last minute"],
        ["أتعلم أنظم أسبوعي كويس",
         "أستخدم أجندة أو أبلكيشن للمهام",
         "ورش عن تنظيم الوقت ومهارات المذاكرة"],
    ),
}

EN_PREFIX = ["", "", "", "", "Honestly, ", "I think ", "Mainly ", "For me, "]
EN_SUFFIX = ["", "", "", ".", ".", "!", " to be honest"]
AR_PREFIX = ["", "", "", "بصراحة ", "أكتر حاجة "]
JUNK_ANSWERS = ["N/A", "nothing", "-", "no", "idk", "لا يوجد", "."]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _weighted_choice(rng: np.random.Generator, weights: dict[str, float]) -> str:
    keys = list(weights)
    w = np.array([weights[k] for k in keys], dtype=float)
    return str(rng.choice(keys, p=w / w.sum()))


def _likert_index(value: float) -> int:
    """Map a continuous latent value to a 0..4 Likert position."""
    return int(np.digitize(value, [-1.3, -0.45, 0.35, 1.2]))


def _phrase(rng: np.random.Generator, bank: dict[str, tuple[list[str], list[str]]],
            weights: dict[str, float], arabic: bool) -> str:
    """Build one open-ended answer, sometimes combining two themes."""
    theme = _weighted_choice(rng, weights)
    en, ar = bank[theme]
    text = str(rng.choice(ar if arabic else en))
    if rng.random() < 0.15:  # people often mention two things
        other = _weighted_choice(rng, {k: v for k, v in weights.items() if k != theme})
        en2, ar2 = bank[other]
        second = str(rng.choice(ar2 if arabic else en2))
        if arabic:
            text = f"{text} و كمان {second}"
        else:
            text = f"{text} and also {second[0].lower()}{second[1:]}"
    if arabic:
        return str(rng.choice(AR_PREFIX)) + text
    prefix = str(rng.choice(EN_PREFIX))
    if prefix:
        text = text[0].lower() + text[1:]
    return prefix + text + str(rng.choice(EN_SUFFIX))


def _fake_phone(rng: np.random.Generator) -> str:
    digits = f"0100000{rng.integers(0, 10_000):04d}"
    style = rng.integers(0, 3)
    if style == 0:
        return digits
    if style == 1:
        return f"+20 {digits[1:4]} {digits[4:7]} {digits[7:]}"
    return f"{digits[:4]}-{digits[4:7]}-{digits[7:]}"


def _ms_forms_time(t: datetime) -> str:
    """Microsoft Forms exports times like ``3/5/2026 14:32:10`` (month first)."""
    return f"{t.month}/{t.day}/{t.year} {t.hour}:{t.minute:02d}:{t.second:02d}"


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def _respondent(rng: np.random.Generator) -> dict[str, object]:
    """Simulate one honest, complete respondent."""
    faculty = _weighted_choice(rng, {"Engineering": 0.35, "Computer Science": 0.25,
                                     "Business": 0.25, "Biotechnology": 0.15})
    eng = faculty == "Engineering"
    max_year = 5 if eng else 4
    year = int(rng.integers(1, max_year + 1))
    gender = _weighted_choice(rng, {"Male": 0.48, "Female": 0.48, "Prefer not to say": 0.04})
    living = _weighted_choice(rng, {"With family": 0.6, "University housing": 0.15,
                                    "Shared apartment": 0.25})

    methods = [m for m, p in STUDY_METHODS.items() if rng.random() < p] or ["Lecture notes"]
    groups = "Study groups" in methods

    # Hidden traits that drive the answers.
    discipline = 0.6 * groups + 0.25 * (living == "With family") + rng.normal(0, 0.9)
    sleep = float(np.clip(7.0 - 0.2 * (year - 1) - 0.3 * eng + rng.normal(0, 0.9), 3.5, 10))
    sleep = round(sleep * 2) / 2
    stress = (0.55 * eng + 0.18 * (year - 2.5) - 0.40 * (sleep - 6.5)
              - 0.2 * discipline + rng.normal(0, 0.75))

    study_hours = float(np.clip(2.8 + 0.7 * eng + 0.4 * discipline + rng.normal(0, 1.1), 0.5, 10))
    satisfaction = int(np.clip(round(3.2 - 0.55 * stress + 0.25 * discipline
                                     + rng.normal(0, 0.7)), 1, 5))

    first, last = str(rng.choice(FIRST)), str(rng.choice(LAST))
    name = str(rng.choice(ARABIC_NAMES)) if rng.random() < 0.1 else f"{first} {last}"
    domain = "example.edu" if rng.random() < 0.7 else "example.com"
    email = f"{first.lower()}.{last.lower()}{rng.integers(1, 99)}@{domain}"
    if rng.random() < 0.08:
        email = "anonymous"
    entry_year = 2026 - year
    student_id = f"{entry_year % 100}{rng.integers(0, 10_000_000):07d}"

    row: dict[str, object] = {
        "Email": email,
        "Name": name,
        "Student ID": student_id,
        "WhatsApp number (optional)": _fake_phone(rng) if rng.random() < 0.4 else "",
        "Age": int(17 + year + rng.integers(0, 3)),
        "Gender": gender,
        "Year of study": ["1st year", "2nd year", "3rd year", "4th year", "5th year"][year - 1],
        "Faculty": faculty,
        "Living situation": living,
        "Average daily study hours": round(study_hours * 2) / 2,
        "Average hours of sleep per night": sleep,
        COL_METHODS: ", ".join(methods),
    }

    stress_offsets = [0.2, 0.0, 0.35, 0.3, -0.25]
    for item, offset in zip(STRESS_ITEMS, stress_offsets, strict=True):
        row[f"{STRESS_Q} [{item}]"] = LIKERT_LABELS[_likert_index(stress + offset
                                                                  + rng.normal(0, 0.9))]
    habit_offsets = [0.0, -0.3, -0.1, 0.1]
    for item, offset in zip(HABIT_ITEMS, habit_offsets, strict=True):
        row[f"{HABITS_Q} [{item}]"] = _likert_index(discipline + offset
                                                    + rng.normal(0, 0.85)) + 1
    row[COL_SATISFACTION] = satisfaction

    arabic = rng.random() < 0.3
    hi_stress, lo_disc = max(stress, 0.0), max(-discipline, 0.0)
    challenge_w = {
        "time": 1.0,
        "workload": 1.0 + 0.8 * eng + 0.3 * hi_stress,
        "exams": 0.6 + 0.6 * hi_stress,
        "commute": 1.2 if living == "With family" else 0.2,
        "motivation": 0.6 + 0.6 * lo_disc,
        "money": 1.0 if living == "Shared apartment" else 0.15,
    }
    help_w = {
        "rest": 0.8 + 0.5 * (sleep < 6),
        "exercise": 0.8,
        "scheduling": 0.7 + 0.5 * eng,
        "counseling": 0.4 + 0.5 * hi_stress,
        "social": 0.7,
        "planning": 0.5 + 0.5 * lo_disc,
    }
    for col, bank, weights in ((COL_CHALLENGE, CHALLENGES, challenge_w),
                               (COL_HELP, HELPERS, help_w)):
        roll = rng.random()
        if roll < 0.08:
            row[col] = ""
        elif roll < 0.11:
            row[col] = str(rng.choice(JUNK_ANSWERS))
        else:
            row[col] = _phrase(rng, bank, weights, arabic)
    return row


def generate(seed: int = SEED) -> pd.DataFrame:
    """Return the full messy survey as a DataFrame (same seed -> same data)."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame([_respondent(rng) for _ in range(N_BASE)])

    # Timing: most people take 4-12 minutes.
    survey_open = datetime(2026, 3, 1, 9, 0, 0)
    starts = [survey_open + timedelta(minutes=float(m))
              for m in rng.uniform(0, 14 * 24 * 60, N_BASE)]
    durations = rng.lognormal(mean=np.log(6.5 * 60), sigma=0.35, size=N_BASE)

    stress_cols = [f"{STRESS_Q} [{i}]" for i in STRESS_ITEMS]
    habit_cols = [f"{HABITS_Q} [{i}]" for i in HABIT_ITEMS]
    question_cols = [c for c in df.columns if c not in ("Email", "Name", "Student ID")]
    idx = rng.permutation(N_BASE)
    log: dict[str, int] = {}

    # Straight-liners: same position for every grid item, minimal text.
    straight = idx[:10]
    for i in straight:
        pos = int(rng.choice([2, 3, 4]))
        df.loc[i, stress_cols] = LIKERT_LABELS[pos]
        df.loc[i, habit_cols] = pos + 1
        df.loc[i, [COL_CHALLENGE, COL_HELP]] = str(rng.choice(JUNK_ANSWERS))
    log["straight-liners"] = len(straight)

    # Speeders: 40-80 seconds (4 of them are also straight-liners, as in real data).
    speeders = np.concatenate([straight[:4], idx[10:16]])
    durations[speeders] = rng.uniform(40, 80, len(speeders))
    log["speeders"] = len(speeders)

    # Incomplete: dropped out part-way through the questions.
    incomplete = idx[16:28]
    for i in incomplete:
        cut = int(rng.integers(3, len(question_cols) - 4))
        df.loc[i, question_cols[cut:]] = np.nan
    log["incomplete"] = len(incomplete)

    # Numeric typos / outliers.
    df.loc[idx[28], "Age"] = 199
    df.loc[idx[29], "Age"] = 2
    df.loc[idx[30], "Average hours of sleep per night"] = 24
    df.loc[idx[31], "Average daily study hours"] = 30
    log["numeric outliers"] = 4

    # Inconsistent capitalisation / whitespace in choice answers.
    for i in idx[32:47]:
        col = str(rng.choice(["Faculty", "Gender", "Living situation"]))
        value = str(df.loc[i, col])
        df.loc[i, col] = str(rng.choice([value.lower(), value.upper(), f" {value} ", f"{value} "]))
    log["messy capitalisation"] = 15

    # Personal data typed into free text (must be caught by the privacy step).
    pii_rows = idx[47:52]
    df.loc[pii_rows[0], COL_HELP] = "Talking to someone, you can email me at nour.k@example.com"
    df.loc[pii_rows[1], COL_HELP] = f"Counseling. Call me on {_fake_phone(rng)} if you want details"
    df.loc[pii_rows[2], COL_CHALLENGE] = f"المواصلات، ممكن تكلمني على {_fake_phone(rng)}"
    df.loc[pii_rows[3], COL_CHALLENGE] = "Workload. My ID is 231004567 if you need to follow up"
    df.loc[pii_rows[4], COL_HELP] = "Less deadlines - Omar Mahmoud, Engineering"
    log["PII inside free text"] = len(pii_rows)

    # Scattered skipped grid items (1.5% of Likert cells).
    for col in stress_cols + habit_cols:
        mask = rng.random(N_BASE) < 0.015
        df.loc[mask, col] = np.nan

    df.insert(0, "Start time", starts)
    df.insert(1, "Completion time", [s + timedelta(seconds=float(d))
                                     for s, d in zip(starts, durations, strict=True)])

    # Duplicates: 5 re-submissions (new times) + 3 copy-pasted rows (identical).
    resub = df.iloc[idx[52:57]].copy()
    resub["Start time"] = resub["Completion time"] + pd.to_timedelta(rng.uniform(20, 120, 5),
                                                                     unit="s")
    resub["Completion time"] = resub["Start time"] + pd.to_timedelta(rng.uniform(90, 200, 5),
                                                                     unit="s")
    df = pd.concat([df, resub], ignore_index=True)
    df = df.sort_values("Completion time", ignore_index=True)
    df.insert(0, "ID", range(1, len(df) + 1))
    pasted = df.iloc[rng.choice(len(df), 3, replace=False)]
    df = pd.concat([df, pasted], ignore_index=True)
    log["duplicates"] = 8

    for col in ("Start time", "Completion time"):
        df[col] = [_ms_forms_time(t) for t in df[col]]
    # Blank cells turned whole-number columns into floats (4 -> 4.0); undo that.
    for col in [*habit_cols, COL_SATISFACTION, "Age"]:
        df[col] = df[col].astype("Int64")
    df.attrs["injected"] = log
    return df


def main() -> None:
    """Generate the CSV and print a summary of what was injected."""
    df = generate()
    df.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    print(f"Wrote {len(df)} rows x {df.shape[1]} columns to {OUTPUT}")
    for problem, count in df.attrs["injected"].items():
        print(f"  injected {count:>3} {problem}")


if __name__ == "__main__":
    main()
