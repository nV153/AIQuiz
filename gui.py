import tkinter as tk
from tkinter import ttk, messagebox
import threading
import string
import os
import json

from topic import Topic
from question import Question
from logic import load_questions_for_topic, configure_api
import requests

TOPICS_SOURCES_DIR = os.path.join(os.path.dirname(__file__), "topics_sources")
API_KEY_FILE = os.path.join(os.path.dirname(__file__), "API_key.json")

class QuizApp(tk.Tk):
    """
    A Tkinter-based GUI application for conducting AI quizzes with topic selection,
    question reuse, and answer saving options.

    Args:
        topics (list[Topic]): List of available quiz topics.

    Attributes:
        topics (list[Topic]): List of available quiz topics.
        questions_list (list[Question]): List of questions for the current quiz session.
        user_answers (list[set[str]]): List of user-selected answers for each question.
        score (int): User's current score.
        current_question_index (int): Index of the current question being displayed.
    """

    def __init__(self, topics: list[Topic]):
        super().__init__()
        self.title("AI Quiz")
        self.geometry("1200x800")

        # List of topics provided at initialization
        self.topics = topics

        # Initialize quiz state variables
        self.questions_list: list[Question] = []
        self.user_answers: list[set[str]] = []
        self.score = 0
        self.current_question_index = 0

        # Create the initial start screen UI
        self.create_start_screen()

    def create_start_screen(self):
        """
        Sets up the start screen where the user can select a topic,
        specify number of questions, choose saving options, reuse options,
        and start the quiz.
        """
        # Clear any existing widgets before creating new ones
        for widget in self.winfo_children():
            widget.destroy()

        # Label for topic selection
        label = tk.Label(self, text="Select a Topic:", font=("Arial", 14))
        label.pack(pady=10)

        # Combobox for selecting a quiz topic from self.topics
        self.topic_var = tk.StringVar()
        self.topic_combo = ttk.Combobox(
            self, textvariable=self.topic_var,
            values=[t.name for t in self.topics],
            state="readonly"
        )
        if self.topics:
            self.topic_combo.current(0)
        self.topic_combo.pack(pady=5)

        # Label and entry for number of questions input
        label_num = tk.Label(self, text="Number of Questions:", font=("Arial", 14))
        label_num.pack(pady=10)

        self.num_questions_var = tk.StringVar(value="5")  # default 5 questions
        self.num_questions_entry = ttk.Entry(self, textvariable=self.num_questions_var)
        self.num_questions_entry.pack(pady=5)

        # Frame for save options with radio button behavior using two checkboxes
        save_frame = tk.LabelFrame(self, text="Save Options", font=("Arial", 12))
        save_frame.pack(pady=10, padx=10, fill="x")

        # Defaults: save_wrong_questions = True, save_all_questions = False
        self.save_all_var = tk.IntVar(value=0)
        self.save_wrong_var = tk.IntVar(value=1)

        def update_save_options(*args):
            """
            Ensure only one save option checkbox is active at a time.
            """
            if self.save_all_var.get() == 1:
                self.save_wrong_var.set(0)
            elif self.save_wrong_var.get() == 1:
                self.save_all_var.set(0)

        self.save_all_var.trace_add("write", update_save_options)
        self.save_wrong_var.trace_add("write", update_save_options)

        # Checkbuttons for save options
        cb_save_all = tk.Checkbutton(save_frame, text="Save all questions", variable=self.save_all_var)
        cb_save_all.pack(anchor="w", padx=5, pady=2)

        cb_save_wrong = tk.Checkbutton(save_frame, text="Save wrong questions", variable=self.save_wrong_var)
        cb_save_wrong.pack(anchor="w", padx=5, pady=2)

        # Frame for reuse old questions option with percentage input
        reuse_frame = tk.LabelFrame(self, text="Reuse Old Questions", font=("Arial", 12))
        reuse_frame.pack(pady=10, padx=10, fill="x")

        self.reuse_percent_var = tk.StringVar(value="50")  # default 50% reuse
        reuse_label = tk.Label(reuse_frame, text="Percentage (0–100):", font=("Arial", 10))
        reuse_label.pack(side="left", padx=5, pady=2)

        self.reuse_entry = ttk.Entry(reuse_frame, textvariable=self.reuse_percent_var, width=5)
        self.reuse_entry.pack(side="left", padx=5)

        # Checkbox for using source priorities when loading questions
        self.use_priorities_var = tk.IntVar(value=0)  # default unchecked
        cb_priorities = tk.Checkbutton(self, text="Use source priorities", variable=self.use_priorities_var)
        cb_priorities.pack(pady=5)

        # Button to start the quiz, triggers start_quiz method
        self.ok_button = ttk.Button(self, text="Start Quiz", command=self.start_quiz)
        self.ok_button.pack(pady=20)

        # Button to open topic/source editing window
        self.edit_topics_button = ttk.Button(self, text="Edit Topics / Options", command=self.open_edit_topics)
        self.edit_topics_button.pack(pady=10)

        # Label for status messages (errors, loading info, etc.)
        self.status_label = tk.Label(self, text="", fg="red")
        self.status_label.pack()

    def start_quiz(self):
        """
        Triggered when user clicks "Start Quiz".
        Validates inputs and disables inputs during question loading.
        Starts background thread to load questions.
        """
        topic_name = self.topic_var.get()

        # Validate number of questions input
        try:
            num_questions = int(self.num_questions_var.get())
            if num_questions <= 0:
                raise ValueError
        except ValueError:
            self.status_label.config(text="Please enter a valid positive number for questions!")
            return

        # Find the selected topic object by name
        self.current_topic = next((t for t in self.topics if t.name == topic_name), None)

        # Disable UI elements and show loading status
        self.status_label.config(text="Loading questions... Please wait.")
        self.ok_button.config(state="disabled")
        self.topic_combo.config(state="disabled")
        self.num_questions_entry.config(state="disabled")

        # Start a background thread to load questions (avoid freezing GUI)
        threading.Thread(target=self.load_questions_thread, args=(topic_name, num_questions), daemon=True).start()

    def load_questions_thread(self, topic_name: str, num_questions: int):
        """
        Loads questions from the selected topic in a background thread.
        Uses reuse percentage and source priority options.
        On success, triggers showing the first question.
        On failure, restores UI and shows error.
        """
        try:
            topic = next((t for t in self.topics if t.name == topic_name), None)
            if not topic:
                raise Exception("Selected topic not found!")

            # Parse options from UI vars
            reuse_percent = int(self.reuse_percent_var.get())
            use_priorities = bool(self.use_priorities_var.get())

            # Load questions with given parameters
            self.questions_list = load_questions_for_topic(topic, num_questions, reuse_percent, use_priorities)
            self.user_answers = []
            self.score = 0
            self.current_question_index = 0

            # Switch back to main thread to update UI
            self.after(0, self.show_question)
        except Exception as e:
            # Show error message and re-enable UI controls on failure
            self.after(0, lambda: self.status_label.config(text=f"Error loading questions: {e}"))
            self.after(0, lambda: self.ok_button.config(state="normal"))
            self.after(0, lambda: self.topic_combo.config(state="readonly"))
            self.after(0, lambda: self.num_questions_entry.config(state="normal"))

    def show_question(self):
        """
        Displays the current question with answer options as checkboxes.
        Enables 'Next' button only if user selects the correct number of answers.
        """
        # Clear previous widgets
        for widget in self.winfo_children():
            widget.destroy()

        # If no more questions, show results screen
        if self.current_question_index >= len(self.questions_list):
            self.show_results()
            return

        question = self.questions_list[self.current_question_index]

        # Display question text
        question_label = tk.Label(self, text=f"Question {self.current_question_index + 1}: {question.text}",
                                  wraplength=580, font=("Arial", 14))
        question_label.pack(pady=10)

        self.checked_vars = []
        self.num_correct = len(question.correct_answers)

        # Create checkbox for each option, bind variable changes to check handler
        for idx, option in enumerate(question.options):
            letter = string.ascii_lowercase[idx]
            var = tk.IntVar()
            var.trace_add('write', self.on_check_changed)
            cb = tk.Checkbutton(self, text=f"{letter}) {option}", variable=var, font=("Arial", 12))
            cb.pack(anchor="w")
            self.checked_vars.append((letter, var))

        # Label showing how many options should be selected
        select_label = tk.Label(self, text=f"Select: {self.num_correct}", font=("Arial", 10, "italic"))
        select_label.pack(pady=5)

        # Next button to submit current answer and proceed
        self.next_button = ttk.Button(self, text="Next", command=self.next_question)
        self.next_button.pack(pady=20)
        self.next_button.config(state="disabled")  # disabled until correct number selected

    def next_question(self):
        """
        Handles clicking "Next":
        Records the user's selected answers,
        advances the question index, and shows the next question.
        """
        # Gather all selected answer letters
        user_answer = {letter for letter, var in self.checked_vars if var.get() == 1}
        self.user_answers.append(user_answer)

        self.current_question_index += 1
        self.show_question()

    def show_results(self):
        """
        Displays quiz results with score and per-question answer summary.
        Saves questions based on user's save option choice.
        Provides a restart button to go back to start screen.
        """
        for widget in self.winfo_children():
            widget.destroy()

        score = 0
        result_text = "Quiz finished! Overview:\n\n"

        questions_to_save = []

        # Iterate over questions and user answers, determine correctness
        for i, question in enumerate(self.questions_list):
            user = self.user_answers[i] if i < len(self.user_answers) else set()
            correct = question.correct_answers
            is_correct = user == correct

            if is_correct:
                score += 1

            user_str = ", ".join(sorted(user)) if user else "No answer"
            correct_str = ", ".join(sorted(correct))
            result_text += f"Question {i + 1}: {question.text}\n"
            result_text += f"Your answer(s): {user_str}\n"
            result_text += f"Correct answer(s): {correct_str}\n"
            result_text += f"{'✅ Correct' if is_correct else '❌ Incorrect'}\n\n"

            # Decide which questions to save depending on user's save option
            if self.save_all_var.get() == 1:
                questions_to_save.append(question)
            elif self.save_wrong_var.get() == 1 and not is_correct:
                questions_to_save.append(question)

        # Show total score label
        score_label = tk.Label(self, text=f"Your score: {score} of {len(self.questions_list)}", font=("Arial", 16))
        score_label.pack(pady=10)

        # Text widget for detailed results
        result_box = tk.Text(self, wrap="word", width=70, height=15)
        result_box.pack(padx=10, pady=10)
        result_box.insert("1.0", result_text)
        result_box.config(state="disabled")

        # Button to restart quiz, returns user to start screen
        restart_button = ttk.Button(self, text="Restart", command=self.create_start_screen)
        restart_button.pack(pady=10)

        # Append questions to topic's old_questions and save if any to save
        if questions_to_save and hasattr(self, "current_topic"):
            self.current_topic.old_questions.extend(questions_to_save)
            self.current_topic.save_questions()

    def refresh_topics(self):
        """
        Reloads the sources for all topics and updates the topic selection combobox.
        """
        for topic in self.topics:
            topic.load_sources()

        if hasattr(self, 'topic_combo'):
            self.topic_combo['values'] = [t.name for t in self.topics]

    def open_edit_topics(self):
        """
        Opens the EditTopicsWindow, allowing user to add topics or manage sources.
        """
        EditTopicsWindow(self, self.topics, self.refresh_topics)

    def on_check_changed(self, *args):
        """
        Callback triggered when a checkbox changes state.
        Enables the 'Next' button only if the number of selected checkboxes
        matches the expected number of correct answers.
        """
        selected_count = sum(var.get() for _, var in self.checked_vars)
        if selected_count == self.num_correct:
            self.next_button.config(state="normal")
        else:
            self.next_button.config(state="disabled")

class EditTopicsWindow(tk.Toplevel):
    """
    A window to add new topics and manage existing sources for each topic.
    Allows adding, editing, and deleting sources per topic.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None or not cls._instance.winfo_exists():
            cls._instance = super(EditTopicsWindow, cls).__new__(cls)
        else:
            cls._instance.lift()
            cls._instance.focus_force()
            return None
        return cls._instance

    def __init__(self, master, topics, refresh_callback):
        if getattr(self, '_initialized', False):
            return  # Avoid running __init__ multiple times
        super().__init__(master)
        self._initialized = True

        # Your existing __init__ code here
        self.title("Edit Topics")
        self.geometry("900x600")

        self.topics = topics
        self.refresh_callback = refresh_callback

        self.create_widgets()

    def create_widgets(self):
        """
        Creates UI elements, including a notebook with three tabs:
        - Add New Topic
        - Manage Sources
        - Manage API Key
        """
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        # --- Tab 1: Add New Topic ---
        frame_add_topic = ttk.Frame(notebook)
        notebook.add(frame_add_topic, text="Add New Topic")

        ttk.Label(frame_add_topic, text="New topic name:").pack(pady=5)
        self.new_topic_entry = ttk.Entry(frame_add_topic)
        self.new_topic_entry.pack(pady=5)

        add_topic_btn = ttk.Button(frame_add_topic, text="Add Topic", command=self.add_topic)
        add_topic_btn.pack(pady=10)

        # --- Tab 2: Manage Sources ---
        frame_manage_sources = ttk.Frame(notebook)
        notebook.add(frame_manage_sources, text="Manage Sources")

        ttk.Label(frame_manage_sources, text="Select topic:").pack(pady=5)
        self.topic_combo = ttk.Combobox(frame_manage_sources, state="readonly")
        self.topic_combo.pack(pady=5)
        self.topic_combo.bind("<<ComboboxSelected>>", self.load_sources)

        self.sources_listbox = tk.Listbox(frame_manage_sources, height=12)
        self.sources_listbox.pack(pady=5, fill="both", expand=True)

        # Buttons for source actions
        btn_frame = ttk.Frame(frame_manage_sources)
        btn_frame.pack(pady=5)

        ttk.Button(btn_frame, text="Edit Source", command=self.edit_source).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Delete Source", command=self.delete_source).grid(row=0, column=1, padx=5)
        self.add_source_btn = ttk.Button(btn_frame, text="Add New Source", command=self.add_source)
        self.add_source_btn.grid(row=0, column=2, padx=5)

        # Initialize topic list
        self.update_topic_list()

        # --- Tab 3: Manage API Key ---
        frame_manage_api = ttk.Frame(notebook)
        notebook.add(frame_manage_api, text="Manage API Key")

        ttk.Label(frame_manage_api, text="Current API Key (readonly):").pack(pady=(10, 2))
        self.old_api_key_var = tk.StringVar()
        # Use Label instead of Entry for non-selectable display
        old_key_label = ttk.Label(frame_manage_api, textvariable=self.old_api_key_var, relief="sunken", width=50, anchor="w")
        old_key_label.pack(pady=(0, 10), fill='x')

        ttk.Label(frame_manage_api, text="Enter New API Key:").pack(pady=(10, 2))
        self.new_api_key_var = tk.StringVar()
        self.new_api_key_entry = ttk.Entry(frame_manage_api, textvariable=self.new_api_key_var, width=50)
        self.new_api_key_entry.pack(pady=(0, 10))

        self.api_status_label = ttk.Label(frame_manage_api, text="", foreground="red")
        self.api_status_label.pack(pady=5)

        save_btn = ttk.Button(frame_manage_api, text="Save API Key", command=self.save_api_key)
        save_btn.pack(pady=10)

        # Load the current API key when the tab is created
        self.load_api_key()

    def load_api_key(self):
        """
        Load the API key from the API_KEY_FILE and update the GUI variables.

        If the API key file exists, attempts to read and parse the JSON content to retrieve
        the stored API key. Sets the old_api_key_var to display the current API key in a
        read-only field and clears the new_api_key_var for new input. If an error occurs
        during file reading or JSON parsing, displays an error message to the user.

        Raises:
            Displays a messagebox with an error if loading or parsing the API key fails.
        """
        if os.path.exists(API_KEY_FILE):
            try:
                with open(API_KEY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    old_key = data.get("api_key", "")
                    self.old_api_key_var.set(old_key)      # readonly display
                    self.new_api_key_var.set("")            # clear new input
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load API key: {e}")

    def test_api_key(self, key: str) -> bool:
        """
        Test if the provided API key is valid by making a minimal request to the AI API.

        Returns True if valid, False otherwise.
        """
        test_api_url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "llama3-70b-8192",  # or your default model
            "messages": [
                {"role": "system", "content": "You are a test. Reply 'ok'."},
                {"role": "user", "content": "Say 'ok'."}
            ],
            "temperature": 0
        }

        try:
            response = requests.post(test_api_url, headers=headers, json=data, timeout=5)
            if response.status_code == 200:
                # Optionally check if response content looks valid
                resp_json = response.json()
                if "choices" in resp_json and len(resp_json["choices"]) > 0:
                    return True
            return False
        except requests.RequestException:
            return False

    def save_api_key(self):
        """
        Handles saving a new API key entered by the user.

        - Validates that the new API key is not empty.
        - Disables the input field and shows a status message while testing the key.
        - Tests the API key in a background thread using test_api_key().
        - If valid, saves the key to API_KEY_FILE and updates the display.
        - If invalid, shows an error and clears the input.
        - All UI updates are performed on the main thread.
        """
        new_key = self.new_api_key_var.get().strip()
        if not new_key:
            messagebox.showwarning("Validation", "API key cannot be empty.")
            return

        # Disable input and show testing status
        self.new_api_key_entry.config(state="disabled")
        self.api_status_label.config(text="Testing API key...", foreground="blue")

        def test_and_save():
            # Test the API key (network call, may take time)
            valid = self.test_api_key(new_key)

            def on_complete():
                # Re-enable input field
                self.new_api_key_entry.config(state="normal")
                if valid:
                    try:
                        # Save the valid API key to file
                        with open(API_KEY_FILE, "w", encoding="utf-8") as f:
                            json.dump({"api_key": new_key}, f, indent=2)
                        # Update the readonly display and clear input
                        self.old_api_key_var.set(new_key)
                        self.new_api_key_var.set("")
                        self.api_status_label.config(text="API key saved successfully.", foreground="green")
                    except Exception as e:
                        # Show error if saving fails
                        messagebox.showerror("Error", f"Failed to save API key: {e}")
                        self.api_status_label.config(text="Failed to save API key.", foreground="red")
                else:
                    # Clear input and show invalid key message
                    self.new_api_key_var.set("")
                    self.api_status_label.config(text="Invalid API key. Please try again.", foreground="red")

            # Schedule UI updates on the main thread
            self.after(0, on_complete)

        # Run the test and save logic in a background thread
        threading.Thread(target=test_and_save, daemon=True).start()






    def update_topic_list(self):
        """
        Refreshes the topic selection combobox with current topics
        and loads sources for the first topic.
        """
        self.topic_combo['values'] = [t.name for t in self.topics]
        if self.topics:
            self.topic_combo.current(0)
            self.load_sources()

    def add_topic(self):
        """
        Adds a new topic if the name is not empty and doesn't already exist.
        Creates a corresponding empty JSON file for the topic sources.
        """
        name = self.new_topic_entry.get().strip()
        if not name:
            messagebox.showwarning("Input error", "Topic name cannot be empty")
            return

        filepath = os.path.join(TOPICS_SOURCES_DIR, f"{name.lower()}.json")
        if os.path.exists(filepath):
            messagebox.showwarning("Duplicate", "Topic already exists")
            return

        os.makedirs(TOPICS_SOURCES_DIR, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump([], f)

        new_topic = Topic(name)
        self.topics.append(new_topic)
        self.update_topic_list()
        self.refresh_callback()
        self.new_topic_entry.delete(0, tk.END)

    def load_sources(self, event=None):
        """
        Loads and displays the sources for the selected topic.
        Clears listbox if no file or no sources.
        """
        topic_name = self.topic_combo.get()
        if not topic_name:
            return

        filepath = os.path.join(TOPICS_SOURCES_DIR, f"{topic_name.lower()}.json")
        if not os.path.isfile(filepath):
            self.sources_listbox.delete(0, tk.END)
            return

        with open(filepath, "r", encoding="utf-8") as f:
            sources = json.load(f)

        self.sources_listbox.delete(0, tk.END)
        for src in sources:
            name = src.get("name") or "Unnamed Source"
            self.sources_listbox.insert(tk.END, name)

    def edit_source(self):
        """
        Opens a dialog to edit the currently selected source.
        """
        selection = self.sources_listbox.curselection()
        if not selection:
            messagebox.showwarning("Select source", "Please select a source to edit")
            return
        idx = selection[0]
        topic_name = self.topic_combo.get()

        filepath = os.path.join(TOPICS_SOURCES_DIR, f"{topic_name.lower()}.json")
        with open(filepath, "r", encoding="utf-8") as f:
            sources = json.load(f)

        source_data = sources[idx]

        # Open AddSourceDialog in edit mode with existing source data
        AddSourceDialog(self, lambda updated: self.save_edited_source(idx, updated), existing_data=source_data)

    def save_edited_source(self, idx, updated_source):
        """
        Saves changes made to an edited source back to the topic's JSON file.
        """
        topic_name = self.topic_combo.get()
        filepath = os.path.join(TOPICS_SOURCES_DIR, f"{topic_name.lower()}.json")
        with open(filepath, "r", encoding="utf-8") as f:
            sources = json.load(f)

        sources[idx] = updated_source

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(sources, f, indent=2)

        self.load_sources()
        self.refresh_callback()

    def delete_source(self):
        """
        Deletes the selected source after confirmation,
        then reloads sources and updates topics.
        """
        selection = self.sources_listbox.curselection()
        if not selection:
            messagebox.showwarning("Select source", "Please select a source to delete")
            return
        idx = selection[0]
        topic_name = self.topic_combo.get()

        if not messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this source?"):
            return

        filepath = os.path.join(TOPICS_SOURCES_DIR, f"{topic_name.lower()}.json")
        with open(filepath, "r", encoding="utf-8") as f:
            sources = json.load(f)

        sources.pop(idx)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(sources, f, indent=2)

        self.load_sources()
        self.refresh_callback()

    def add_source(self):
        topic_name = self.topic_combo.get()
        if not topic_name:
            messagebox.showwarning("Select topic", "Please select a topic first")
            return

        # Disable the button
        self.add_source_btn.config(state="disabled")

        # Define a callback to re-enable the button when dialog closes
        def on_dialog_close():
            self.add_source_btn.config(state="normal")

        # Pass on_dialog_close to AddSourceDialog, assuming it accepts a close callback
        dialog = AddSourceDialog(self, lambda src: self.save_new_source(topic_name, src))
        # Bind to the dialog's destroy event to re-enable button when dialog closes
        dialog.protocol("WM_DELETE_WINDOW", lambda: (on_dialog_close(), dialog.destroy()))

        """
        Saves a new source to the selected topic's JSON file,
        then reloads sources and updates the topics.
        """
        filepath = os.path.join(TOPICS_SOURCES_DIR, f"{topic_name.lower()}.json")
        sources = []
        if os.path.isfile(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                sources = json.load(f)

        sources.append(source_data)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(sources, f, indent=2)

        messagebox.showinfo("Success", "Source added")
        self.load_sources()
        self.refresh_callback()

class AddSourceDialog(tk.Toplevel):
    """
    Dialog window for adding or editing a source associated with a quiz topic.

    Args:
        master (tk.Widget): The parent widget.
        callback (Callable): Function to call with the source data on save.
        existing_data (dict, optional): If provided, pre-fills the dialog for editing.

    Attributes:
        link_entry (ttk.Entry): Entry widget for the source link.
        name_entry (ttk.Entry): Entry widget for the source name.
        importance_var (tk.IntVar): Variable tracking importance rating (0-10).
        importance_value_label (ttk.Label): Label showing selected importance value.
        comment_text (tk.Text): Text widget for optional comments.
    """

    def __init__(self, master, callback, existing_data=None):
        super().__init__(master)
        self.title("Add/Edit Source")
        self.callback = callback
        self.geometry("1200x600")
        self.resizable(False, False)

        # Label and entry for source link URL
        ttk.Label(self, text="Source Link:").pack(pady=5)
        self.link_entry = ttk.Entry(self, width=50)
        self.link_entry.pack(pady=5)

        # Label and entry for source name (mandatory)
        ttk.Label(self, text="Source Name:").pack(pady=5)
        self.name_entry = ttk.Entry(self, width=50)
        self.name_entry.pack(pady=5)

        # Label for importance rating
        ttk.Label(self, text="Importance:").pack(pady=5)

        # Frame holding importance radio buttons (0 to 10)
        importance_frame = ttk.Frame(self)
        importance_frame.pack(pady=5)

        # IntVar to hold the selected importance value, default 5
        self.importance_var = tk.IntVar(value=5)

        # Create unlabeled radio buttons for importance values 0 through 10
        for i in range(11):
            rb = ttk.Radiobutton(
                importance_frame,
                text="",  # No label text to save space
                value=i,
                variable=self.importance_var,
                command=self.update_importance_label  # Update label on change
            )
            # Pack horizontally with spacing to avoid overlap
            rb.pack(side="left", padx=8)

        # Label below the radio buttons showing currently selected importance
        self.importance_value_label = ttk.Label(self, text=str(self.importance_var.get()), font=("Arial", 12, "bold"))
        self.importance_value_label.pack(pady=5)

        # Label and text box for optional comments about the source
        ttk.Label(self, text="Comment:").pack(pady=5)
        self.comment_text = tk.Text(self, height=4, width=50)
        self.comment_text.pack(pady=5)

        # Frame containing Save and Cancel buttons
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Save", command=self.on_save).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

        # If editing an existing source, pre-fill fields with existing data
        if existing_data:
            self.link_entry.insert(0, existing_data.get("link", ""))
            self.name_entry.insert(0, existing_data.get("name", ""))
            self.importance_var.set(existing_data.get("importance", 5))
            self.update_importance_label()
            self.comment_text.insert("1.0", existing_data.get("comment", ""))

    def update_importance_label(self):
        """
        Updates the label that displays the currently selected importance value.
        Called whenever a radio button is selected.
        """
        self.importance_value_label.config(text=str(self.importance_var.get()))

    def on_save(self):
        """
        Called when the user clicks the Save button.
        Validates inputs, constructs the source data dictionary,
        calls the callback with this data, and closes the dialog.
        """
        link = self.link_entry.get().strip()
        name = self.name_entry.get().strip()
        importance = self.importance_var.get()
        comment = self.comment_text.get("1.0", "end").strip()

        # Validate that the source name is not empty
        if not name:
            messagebox.showwarning("Validation error", "Source name cannot be empty.")
            return

        # Prepare the source data dictionary to pass back
        source_data = {
            "link": link,
            "name": name,
            "importance": importance,
            "comment": comment
        }

        # Call the callback function with the new/updated source data
        self.callback(source_data)

        # Close the dialog
        self.destroy()

class ManageSourcesTab(ttk.Frame):
    """
    A tab frame for managing sources of a given topic.
    Allows adding, editing, and deleting sources.

    Args:
        master (tk.Widget): Parent widget.
        topic (Topic): The topic object whose sources are managed.

    Attributes:
        source_listbox (tk.Listbox): Displays the list of source names.
    """

    def __init__(self, master, topic: Topic):
        super().__init__(master)
        self.topic = topic

        # Listbox to display sources by name
        self.source_listbox = tk.Listbox(self, height=12, width=40)
        self.source_listbox.pack(pady=10, padx=10, side="left", fill="y")

        # Scrollbar linked to the listbox for vertical scrolling
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.source_listbox.yview)
        scrollbar.pack(side="left", fill="y")
        self.source_listbox.config(yscrollcommand=scrollbar.set)

        # Frame holding the action buttons on the right side
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side="left", fill="y", padx=10)

        # Button to add a new source
        ttk.Button(btn_frame, text="New Source", command=self.add_source).pack(pady=5, fill="x")
        # Button to edit the selected source
        ttk.Button(btn_frame, text="Edit", command=self.edit_source).pack(pady=5, fill="x")
        # Button to delete the selected source
        ttk.Button(btn_frame, text="Delete", command=self.delete_source).pack(pady=5, fill="x")

        # Populate the listbox initially
        self.refresh_sources()

    def refresh_sources(self):
        """
        Refreshes the listbox to display the current list of sources.
        """
        self.source_listbox.delete(0, tk.END)
        for src in self.topic.sources:
            self.source_listbox.insert(tk.END, src["name"])

    def get_selected_index(self):
        """
        Retrieves the currently selected index in the listbox.

        Returns:
            int or None: Selected index or None if nothing is selected.
        """
        try:
            return self.source_listbox.curselection()[0]
        except IndexError:
            messagebox.showwarning("No selection", "Please select a source first.")
            return None

    def add_source(self):
        """
        Opens the AddSourceDialog to add a new source.
        """
        AddSourceDialog(self, self.save_new_source)

    def edit_source(self):
        """
        Opens the AddSourceDialog pre-filled with the selected source data
        for editing. Saves changes upon dialog completion.
        """
        idx = self.get_selected_index()
        if idx is None:
            return
        
        # Get the source data from the topic's sources list
        source_data = self.topic.sources[idx]

        # Open AddSourceDialog in edit mode with existing source data
        AddSourceDialog(
            self,
            callback=lambda updated_source: self.update_source(idx, updated_source),
            existing_data=source_data
        )

    def delete_source(self):
        """
        Deletes the selected source after confirmation and refreshes the list.
        """
        idx = self.get_selected_index()
        if idx is None:
            return
        if messagebox.askyesno("Delete source", "Are you sure?"):
            self.topic.sources.pop(idx)
            self.topic.save_sources()
            self.refresh_sources()

    def save_new_source(self, source_data):
        """
        Saves a newly added source to the topic and refreshes the list.

        Args:
            source_data (dict): The new source data to add.
        """
        self.topic.sources.append(source_data)
        self.topic.save_sources()
        self.refresh_sources()

    def update_source(self, idx, updated_data):
        """
        Updates an existing source with new data, saves changes, and refreshes.

        Args:
            idx (int): Index of the source to update.
            updated_data (dict): Updated source data.
        """
        self.topic.sources[idx] = updated_data
        self.topic.save_sources()
        self.refresh_sources()

class ManageAPIKeyTab(ttk.Frame):
    """
    A tab frame for managing the API key used by the application.
    Allows viewing, editing, testing, and saving the API key.

    Args:
        master (tk.Widget): The parent widget.

    Attributes:
        api_key_var (tk.StringVar): Holds the API key string for the entry widget.
        api_key_entry (ttk.Entry): Entry widget for API key input.
        status_label (ttk.Label): Label for displaying status messages.
    """
    def __init__(self, master):
        super().__init__(master)
        self.api_key_var = tk.StringVar()

        # Label and entry for API key
        ttk.Label(self, text="API Key:").pack(pady=5)
        self.api_key_entry = ttk.Entry(self, textvariable=self.api_key_var, width=50)
        self.api_key_entry.pack(pady=5)

        # Status label for feedback messages
        self.api_status_label = ttk.Label(self, text="")
        self.api_status_label.pack(pady=5)

        # Save button to trigger saving the API key
        save_btn = ttk.Button(self, text="Save API Key", command=self.save_api_key)
        save_btn.pack(pady=10)

        # Load the current API key from file (if exists)
        self.load_api_key()

    def load_api_key(self):
        """
        Loads the API key from the API_KEY_FILE if it exists,
        and sets it in the entry widget.
        """
        if os.path.exists(API_KEY_FILE):
            try:
                with open(API_KEY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.api_key_var.set(data.get("api_key", ""))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load API key: {e}")

