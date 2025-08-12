# main.py
#
# Entry point for the AIQuiz application.
# Handles loading API keys, topics, and starting the GUI.

from gui import QuizApp
import logic

def main():
    """
    Main entry point for the application.
    Loads the API key, configures the API, loads topics, and starts the GUI.
    """
    api_key = logic.load_api_key()
    logic.configure_api(api_key)

    topics = logic.load_topics_from_disk()

    app = QuizApp(topics)
    app.mainloop()


if __name__ == "__main__":
    main()
