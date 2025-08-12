import os
import json
import random
from question import Question
from typing import List, Optional

class Topic:
    """
    Represents a quiz topic, managing its questions and sources.

    Attributes:
        DATA_DIR (str): Directory path for storing topic questions data.
        SOURCES_DIR (str): Directory path for storing topic sources data.
        name (str): Name of the topic.
        old_questions (List[Question]): List of previously stored questions for the topic.
        file_path (str): File path for the topic's questions JSON file.
        sources_file (str): File path for the topic's sources JSON file.
        sources (List[Source]): List of sources associated with the topic.

    Methods:
        __init__(name: str):
            Initializes a Topic instance, creates necessary directories, and loads sources and questions.
        load_sources():
            Loads the list of sources for the topic from the sources JSON file. If the file does not exist, initializes an empty list.
        load_questions():
            Loads the list of old questions for the topic from the questions JSON file. If the file does not exist, initializes an empty list.
        save_questions():
            Saves the current list of old questions to the questions JSON file.
        add_question(question: Question):
            Adds a new question to the topic and saves the updated list to the file.
        get_random_source(use_priorities: bool = False):
            Returns a random source from the topic's sources. If use_priorities is True, selects based on source priority; otherwise, selects randomly.
    """
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "topics_data")
    SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "topics_sources")

    def __init__(self, name: str):
        """
        Initialize a Topic instance.

        Args:
            name (str): The name of the topic.
        """
        self.name = name
        self.old_questions: List["Question"] = []
        self.file_path = os.path.join(self.DATA_DIR, f"{self.name.lower()}.json")
        self.sources_file = os.path.join(self.SOURCES_DIR, f"{self.name.lower()}.json")
        self.sources: List[Source] = []

        # Ensure data directories exist
        os.makedirs(self.DATA_DIR, exist_ok=True)
        os.makedirs(self.SOURCES_DIR, exist_ok=True)

        self.load_sources()
        self.load_questions()

    def load_sources(self):
        """
        Load the list of sources for the topic from the sources JSON file.
        If the file does not exist, initializes an empty list.
        """
        filepath = os.path.join(os.path.dirname(__file__), "topics_sources", f"{self.name.lower()}.json")
        if os.path.isfile(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                # Load sources as list of dicts
                self.sources = json.load(f)
        else:
            self.sources = []

    def load_questions(self):
        """
        Load the list of old questions for the topic from the questions JSON file.
        If the file does not exist, initializes an empty list.
        """
        if not os.path.isfile(self.file_path):
            self.old_questions = []
            return
        with open(self.file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.old_questions = [Question.from_dict(q) for q in data]

    def save_questions(self):
        """
        Save the current list of old questions to the questions JSON file.
        """
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump([q.to_dict() for q in self.old_questions], f, indent=2)

    def add_question(self, question: Question):
        """
        Add a new question to the topic and save the updated list to the file.

        Args:
            question (Question): The question to add.
        """
        self.old_questions.append(question)
        self.save_questions()

    def get_random_source(self, use_priorities: bool = False):
        """
        Returns a random source from the topic's sources.

        Args:
            use_priorities (bool): If True, select based on source priority; otherwise, select randomly.

        Returns:
            Source or None: The selected source, or None if no sources exist.
        """
        if not self.sources:
            return None

        if not use_priorities:
            # Randomly select a source (old behavior)
            source_dict = random.choice(self.sources)
            return Source.from_dict(source_dict)

        # Priority-based selection
        # Priority can be 0–10; if all are 0, fall back to random
        weights = [max(0, s.get("priority", 0)) for s in self.sources]
        if sum(weights) == 0:
            source_dict = random.choice(self.sources)
        else:
            source_dict = random.choices(self.sources, weights=weights, k=1)[0]

        return Source.from_dict(source_dict)


class Source:
    """
    Represents a source for a topic.

    Attributes:
        name (str): Name of the source.
        link (str): URL or reference link for the source.
        importance (int): Importance rating (0-10).
        comment (str): Optional comment about the source.

    Methods:
        to_dict(): Returns a dictionary representation of the source.
        from_dict(data: dict): Creates a Source instance from a dictionary.
    """
    def __init__(self, name: str, link: str, importance: int, comment: Optional[str] = None):
        """
        Initialize a Source instance.

        Args:
            name (str): Name of the source.
            link (str): URL or reference link for the source.
            importance (int): Importance rating (0-10).
            comment (Optional[str]): Optional comment about the source.
        """
        self.name = name
        self.link = link
        self.importance = max(0, min(10, importance))  # clamp to 0-10
        self.comment = comment or ""

    def to_dict(self):
        """
        Returns a dictionary representation of the source.

        Returns:
            dict: Dictionary with source attributes.
        """
        return {
            "name": self.name,
            "link": self.link,
            "importance": self.importance,
            "comment": self.comment
        }

    @staticmethod
    def from_dict(data: dict) -> "Source":
        """
        Create a Source instance from a dictionary.

        Args:
            data (dict): Dictionary containing source data.

        Returns:
            Source: The created Source instance.
        """
        return Source(
            name=data.get("name", "Unnamed Source"),
            link=data.get("link", ""),
            importance=data.get("importance", 5),
            comment=data.get("comment", "")
        )