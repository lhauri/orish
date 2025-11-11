"""Initialize the Orish SQLite database with starter data."""

from werkzeug.security import generate_password_hash

from app import app, get_db, init_tables


VOCABULARY_QUESTIONS = [
    ("eloquent", "Fluent or persuasive in speaking", "Relating to horses", "Extremely tired", "Difficult to see"),
    ("meticulous", "Showing great attention to detail", "Quick to anger", "Happy and carefree", "Lacking knowledge"),
    ("succinct", "Briefly and clearly expressed", "Difficult to understand", "Easily bent", "Full of energy"),
    ("resilient", "Able to recover quickly", "Stubborn", "Easily bored", "Fond of arguing"),
    ("novice", "A person new to a field", "A strict teacher", "An expert musician", "A generous host"),
    ("candid", "Truthful and straightforward", "Filled with sugar", "Impossible to solve", "Extremely loud"),
    ("diligent", "Showing care in work", "Unable to sleep", "Fearless", "Very funny"),
    ("ambiguous", "Open to more than one meaning", "Extremely clean", "Full of mistakes", "Easy to predict"),
    ("pragmatic", "Dealing with things sensibly", "Full of fear", "Always late", "Unable to decide"),
    ("vital", "Absolutely necessary", "Related to travel", "Made of glass", "Very quiet"),
]

GRAMMAR_QUESTIONS = [
    ("She ___ tennis every weekend.", "plays", "play", "playing", "played"),
    ("If I ___ more time, I would travel.", "had", "have", "has", "having"),
    ("They have ___ their homework already.", "finished", "finish", "finishes", "finishing"),
    ("The cake was eaten ___ the guests arrived.", "before", "after", "during", "since"),
    ("He is taller ___ his brother.", "than", "then", "that", "this"),
    ("We will go out ___ it stops raining.", "when", "while", "unless", "during"),
    ("Neither of the answers ___ correct.", "is", "are", "were", "be"),
    ("I prefer reading ___ watching television.", "to", "than", "over", "for"),
    ("The letter was written ___ Sarah.", "by", "from", "through", "over"),
    ("She sings better ___ anyone I know.", "than", "then", "that", "as"),
]

READING_QUESTIONS = [
    (
        "Morning Routine",
        "Lena wakes up early each day to go for a short run before school. She believes the quiet streets and cool air help her focus for the rest of the day.",
        "Why does Lena go for a run in the morning?",
        "It helps her focus",
        "She dislikes school",
        "Her friends join her",
        "It is required by her coach",
    ),
    (
        "Library Visit",
        "The town library introduced a new reading corner with soft chairs and gentle lighting. Many students now spend their afternoons there completing assignments.",
        "What attracts students to the new library corner?",
        "Comfortable environment",
        "Free snacks",
        "Online games",
        "Faster internet",
    ),
    (
        "Science Club",
        "GIBB's science club meets every Thursday to work on experiments. Last week they built paper bridges to test how much weight each could hold.",
        "What was last week's experiment about?",
        "Building paper bridges",
        "Studying planets",
        "Learning new languages",
        "Painting posters",
    ),
    (
        "Music Practice",
        "Aaron practices the piano for thirty minutes daily. He tracks his improvement by recording one piece each week.",
        "How does Aaron measure his progress?",
        "By recording pieces",
        "By taking tests",
        "By asking his friends",
        "By buying new music",
    ),
    (
        "Garden Project",
        "Students volunteered to plant herbs in the school garden to support the culinary class.",
        "Why are students planting herbs?",
        "To support culinary class",
        "To win a competition",
        "To earn money",
        "To decorate classrooms",
    ),
    (
        "Drama Club",
        "The drama club is rehearsing a modern play about teamwork and honesty.",
        "What is the theme of the play?",
        "Teamwork and honesty",
        "Science fiction",
        "Historical war",
        "Adventure on the sea",
    ),
    (
        "Field Trip",
        "Next month, the English class will visit a local newspaper to learn about interviewing techniques.",
        "Where is the class going?",
        "A local newspaper",
        "An art museum",
        "A bakery",
        "A sports arena",
    ),
    (
        "Study Group",
        "Five friends meet every Sunday evening to review vocabulary using flashcards they designed together.",
        "How do the friends review vocabulary?",
        "Using flashcards",
        "By watching movies",
        "By playing soccer",
        "By listening to music",
    ),
    (
        "Test Prep",
        "Ms. Rivera suggests that students read short news articles daily to strengthen comprehension.",
        "What does Ms. Rivera recommend?",
        "Reading news articles",
        "Writing poetry",
        "Practicing speeches",
        "Attending concerts",
    ),
    (
        "Debate Team",
        "The debate team practices how to support ideas with clear evidence before each tournament.",
        "What skill are they practicing?",
        "Using clear evidence",
        "Drawing diagrams",
        "Cooking meals",
        "Fixing computers",
    ),
]


def seed_table(db, table, rows, columns):
    placeholders = ", ".join(["?"] * len(columns))
    column_clause = ", ".join(columns)
    db.executemany(
        f"INSERT INTO {table} ({column_clause}) VALUES ({placeholders})",
        rows,
    )


def main():
    with app.app_context():
        init_tables()
        db = get_db()
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            db.execute(
                "INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, 1)",
                (
                    "teacher",
                    "teacher@example.com",
                    generate_password_hash("teach123"),
                ),
            )
            print("Created default admin user: teacher / teach123")

        if db.execute("SELECT COUNT(*) FROM questions_vocabulary").fetchone()[0] == 0:
            seed_table(
                db,
                "questions_vocabulary",
                VOCABULARY_QUESTIONS,
                ["word", "correct_answer", "wrong1", "wrong2", "wrong3"],
            )
            print("Seeded vocabulary questions")

        if db.execute("SELECT COUNT(*) FROM questions_grammar").fetchone()[0] == 0:
            seed_table(
                db,
                "questions_grammar",
                GRAMMAR_QUESTIONS,
                [
                    "sentence_with_placeholder",
                    "correct_answer",
                    "wrong1",
                    "wrong2",
                    "wrong3",
                ],
            )
            print("Seeded grammar questions")

        if db.execute("SELECT COUNT(*) FROM questions_reading").fetchone()[0] == 0:
            seed_table(
                db,
                "questions_reading",
                READING_QUESTIONS,
                [
                    "title",
                    "text",
                    "question",
                    "correct_answer",
                    "wrong1",
                    "wrong2",
                    "wrong3",
                ],
            )
            print("Seeded reading questions")

        db.commit()
        print("Database ready! Run `python app.py` to start Orish.")


if __name__ == "__main__":
    main()
