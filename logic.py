import requests
from question import Question, parse_question
from topic import Topic, Source
import re
import os
import json
import random

API_KEY = None
MODEL = "llama3-70b-8192"
API_URL = "https://api.groq.com/openai/v1/chat/completions"
TOPICS_SOURCES_DIR = "AIQUIZ/topics_sources"

def configure_api(api_key: str, model: str = None):
    """
    Configure the API key and optionally the model for the AI API.

    Args:
        api_key (str): The API key to use for authentication.
        model (str, optional): The model name to use. Defaults to None.
    """
    global API_KEY, MODEL
    API_KEY = api_key
    if model:
        MODEL = model

def call_ai_api(topic_instance: Topic, prompt_text: str) -> str:
    """
    Call the AI API to generate a multiple-choice question.

    Args:
        topic_instance (Topic): The topic for which to generate the question.
        prompt_text (str): The prompt to send to the AI.

    Returns:
        str: The AI's response containing the question and options.

    Raises:
        Exception: If the API request fails.
    """
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": (
                "You are a multiple-choice question generator. "
                "Create one question based on the prompt. Respond in the following format:\n"
                "Question: <question text>\n"
                "Options:\n"
                "1) ...\n"
                "2) ...\n"
                "3) ...\n"
                "4) ...\n"
                "(optional 5) ...\n"
                "(optional 6) ...\n"
                "Correct answers: <numbers separated by spaces>"
            )},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.7
    }

    response = requests.post(API_URL, headers=headers, json=data)
    if response.status_code != 200:
        raise Exception(f"API request error: {response.status_code} {response.text}")

    return response.json()["choices"][0]["message"]["content"]

def build_prompt(topic: Topic, source: Source) -> str:
    """
    Build a prompt for the AI to generate a multiple-choice question.

    Args:
        topic (Topic): The topic for the question.
        source (Source): The source material for reference.

    Returns:
        str: The formatted prompt string.
    """
    return (
        f"Use this source as reference: {source.name} ({source.link})\n"
        #f"Importance: {source.importance}/10\n"
        #f"{'Comment: ' + source.comment if source.comment else ''}\n\n"
        f"Create a multiple-choice question about the topic '{topic.name}'.\n"
        "Answer in the following format:\n"
        "Question: <question text>\n"
        "Options:\n"
        "1) ...\n"
        "2) ...\n"
        "3) ...\n"
        "4) ...\n"
        "(optional 5) ...\n"
        "(optional 6) ...\n"
        "Correct answers: <numbers separated by spaces>"
    )

def load_questions_for_topic(topic: Topic, num_questions: int, reuse_percent: int, use_priorities: bool) -> list[Question]:
    """
    Load a specified number of questions for a topic, reusing a percentage from old questions
    and generating new ones as needed.

    Args:
        topic (Topic): The topic for which to load questions.
        num_questions (int): Number of questions to load.
        reuse_percent (int): Percentage chance to reuse an old question.
        use_priorities (bool): Whether to use source priorities when selecting sources.

    Returns:
        list[Question]: List of loaded Question objects.
    """
    questions = []

    # Load old questions from JSON if file exists
    old_questions_file = topic.file_path
    if os.path.exists(old_questions_file):
        try:
            with open(old_questions_file, "r", encoding="utf-8") as f:
                old_questions_data = json.load(f)
        except json.JSONDecodeError:
            old_questions_data = []
    else:
        old_questions_data = []

    for _ in range(num_questions):
        # Decide whether to use an old question
        use_old = (random.randint(1, 100) <= reuse_percent) and bool(old_questions_data)

        if use_old:
            # Take the first old question and remove it from the list
            old_q_dict = old_questions_data.pop(0)
            question = Question.from_dict(old_q_dict)
            questions.append(question)

            # Save updated old questions list back to file
            with open(old_questions_file, "w", encoding="utf-8") as f:
                json.dump(old_questions_data, f, indent=2)

        else:
            # Generate a new question using the AI API
            source = topic.get_random_source(use_priorities)
            prompt = build_prompt(topic, source)
            ai_output = call_ai_api(topic, prompt)

            # Parse AI output into a Question object
            question = parse_question(ai_output, source.link)

            # Clean text for display
            display_text = clean_ai_text(ai_output)
            question.text = display_text

            questions.append(question)
            topic.add_question(question)

    return questions

def clean_ai_text(ai_text: str) -> str:
    """
    Clean the AI-generated text by:
    - Removing everything before and including 'Question:'
    - Removing the 'Correct answers:' line and everything after it.

    Args:
        ai_text (str): The raw AI output.

    Returns:
        str: The cleaned text for display, starting right after 'Question:'.
    """
    # Extract everything after 'Question:' (excluding 'Question:' itself)
    match = re.search(r"Question:\s*(.*)", ai_text, flags=re.DOTALL)
    if match:
        ai_text = match.group(1)
    else:
        # If no 'Question:' found, just keep original text
        ai_text = ai_text

    # Remove 'Correct answers:' and everything after it
    cleaned_text = re.sub(r"\nCorrect answers:.*", "", ai_text, flags=re.DOTALL).strip()

    return cleaned_text


def load_api_key(path="API_key.json") -> str:
    """
    Loads the API key from a JSON configuration file.

    Args:
        path (str): Relative path to the API key JSON file.

    Returns:
        str: The API key as a string, or an empty string if not found.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, path)
    with open(full_path) as f:
        config = json.load(f)
    return config.get("api_key", "")

def load_topics_from_disk():
    """
    Loads available topics from the topics sources directory.

    Returns:
        list[Topic]: List of Topic objects, one for each topic file found.
    """
    topics = []
    if not os.path.exists(TOPICS_SOURCES_DIR):
        os.makedirs(TOPICS_SOURCES_DIR)

    for filename in os.listdir(TOPICS_SOURCES_DIR):
        if filename.endswith(".json"):
            topic_name = os.path.splitext(filename)[0].capitalize()
            topic = Topic(topic_name)  # only name, not sources
            topics.append(topic)
    return topics