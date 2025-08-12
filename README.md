AI Quiz Generator

A Python application that generates multiple-choice quiz questions using an AI language model. The project manages topics and sources, generates questions based on curated sources, and includes API key handling with a user-provided key.

The project uses the Groq API for AI calls by default, but this can be easily changed. To use the API, you need a user key which can be generated at:
https://console.groq.com/home

Features:
- Topic and Source Management: Add, edit, and delete quiz topics and their sources.
- AI-Powered Question Generation: Dynamically generate multiple-choice questions based on prompts.
- Question Reuse & Generation: Reuse existing questions or create new ones via AI.
- Clean AI Output Parsing: Automatically cleans and formats AI responses for display.
- Tkinter GUI: User-friendly interface with tabs to manage topics, sources, and API key.

Relevant Python Skills Demonstrated:
- GUI development using Tkinter, including notebook tabs, dialogs, and widget management.
- File handling with JSON for persistent storage of topics, sources, questions, and API keys.
- Multithreading to perform API key validation without freezing the GUI.
- Network requests using the requests library to communicate with the AI API.
- Regular expressions for text parsing and cleaning of AI-generated content.
- Object-oriented programming with classes modeling topics, sources, and questions.
- Exception handling for robust API interaction and file operations.

Installation:
1. Clone the repository.
2. Install dependencies via pip (e.g. requests).
3. Run the main.py script to launch the application.

Usage:
- Add and manage quiz topics and their sources.
- Enter your API key (from Groq) in the Manage API Key tab.
- Generate quiz questions powered by AI based on your selected topics.
- Questions are cleaned and parsed for easy display in the app.
