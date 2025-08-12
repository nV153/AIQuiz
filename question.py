import re
import string

from typing import List, Set

class Question:
    """
    Represents a multiple-choice question with options, correct answers, and an optional source.
    """
    def __init__(self, text: str, options: List[str], correct_answers: Set[str], source: str = ""):
        """
        Initialize a Question object.

        Args:
            text (str): The question text.
            options (List[str]): List of answer options.
            correct_answers (Set[str]): Set of correct answer letters (e.g., {'a', 'c'}).
            source (str, optional): Source URL or reference. Defaults to "".
        """
        self.text = text
        self.options = options
        self.correct_answers = correct_answers
        self.source = source  

    def to_dict(self):
        """
        Convert the Question object to a dictionary.

        Returns:
            dict: Dictionary representation of the question.
        """
        return {
            "text": self.text,
            "options": self.options,
            "correct_answers": list(self.correct_answers),
            "source": self.source
        }

    @classmethod
    def from_dict(cls, data):
        """
        Create a Question object from a dictionary.

        Args:
            data (dict): Dictionary with keys 'text', 'options', 'correct_answers', and optionally 'source'.

        Returns:
            Question: The constructed Question object.
        """
        return cls(
            text=data["text"],
            options=data["options"],
            correct_answers=set(data["correct_answers"]),
            source=data.get("source", "")
        )


def parse_question(ai_text: str, source_url: str) -> Question:
    """
    Parse a question from a formatted string and create a Question object.

    Args:
        ai_text (str): The raw text containing the question, options, and correct answers.
        source_url (str): The source URL or reference for the question.

    Returns:
        Question: The parsed Question object.
    """
    # Extract the question text
    question_match = re.search(r"Question:\s*(.+)", ai_text, re.DOTALL)
    question_text = question_match.group(1).strip() if question_match else "No question found"

    # Extract all options (e.g., "1) Option text")
    option_matches = re.findall(r"\d\)\s*(.+)", ai_text)
    options = [opt.strip() for opt in option_matches]

    # Extract correct answer numbers (e.g., "Correct answers: 1 3")
    correct_match = re.search(r"(Correct answers|Answer keys|At the end):?\s*([\d\s]+)", ai_text)
    correct_numbers = correct_match.group(2).split() if correct_match else []

    # Convert answer numbers to letters (e.g., 1 -> 'a')
    correct_letters = set()
    for num in correct_numbers:
        idx = int(num) - 1
        if 0 <= idx < len(options):
            correct_letters.add(string.ascii_lowercase[idx])

    return Question(question_text, options, correct_letters, source_url)
