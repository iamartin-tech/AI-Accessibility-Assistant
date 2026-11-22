"""JARVIS Document Assistant.

Voice and keyboard accessible document management with persistent JSON storage.
On Windows, a final hard-exit safeguard prevents CPython from crashing when
Eclipse's console leaves a daemon keyboard thread blocked inside input().
"""
from __future__ import annotations

import json
import os
import platform
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import pyttsx3
import speech_recognition as sr

APP_NAME = "JARVIS Document Assistant"
WAKE_WORD = "jarvis"
DOCUMENT_FILE = Path(__file__).with_name("documents.json")
VOICE_LISTEN_TIMEOUT = 2
VOICE_PHRASE_LIMIT = 20
AMBIENT_NOISE_DURATION = 0.7

documents: Dict[str, str] = {}
current_doc: Optional[str] = None
command_queue: queue.Queue[Tuple[str, str]] = queue.Queue()
response_queue: queue.Queue[Tuple[str, str]] = queue.Queue()
tts_queue: queue.Queue[Optional[str]] = queue.Queue()
shutdown_event = threading.Event()
awaiting_response_event = threading.Event()
speaking_event = threading.Event()
microphone_available_event = threading.Event()
tts_ready_event = threading.Event()
keyboard_thread: Optional[threading.Thread] = None


def speak_with_operating_system(message: str) -> None:
    """Use native speech where available, with a pyttsx3 fallback."""
    system_name = platform.system()
    if system_name == "Windows":
        env = os.environ.copy()
        env["JARVIS_TTS_TEXT"] = message
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$voice.Rate = 0; $voice.Volume = 100; "
            "$voice.Speak($env:JARVIS_TTS_TEXT); $voice.Dispose();"
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            env=env, capture_output=True, text=True, timeout=120, check=False
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "PowerShell speech error")
        return
    if system_name == "Darwin" and shutil.which("say"):
        subprocess.run(["say", message], timeout=120, check=True)
        return
    linux_speaker = shutil.which("espeak-ng") or shutil.which("espeak")
    if linux_speaker:
        subprocess.run([linux_speaker, "-s", "150", message], timeout=120, check=True)
        return
    engine = pyttsx3.init()
    try:
        engine.setProperty("rate", 150)
        engine.say(message)
        engine.runAndWait()
    finally:
        engine.stop()


def text_to_speech_worker() -> None:
    tts_ready_event.set()
    while True:
        try:
            message = tts_queue.get(timeout=0.25)
        except queue.Empty:
            if shutdown_event.is_set():
                return
            continue
        try:
            if message is None:
                return
            speaking_event.set()
            try:
                speak_with_operating_system(message)
            except Exception as error:
                print(f"Text-to-speech error: {error}")
            finally:
                time.sleep(0.05)
                speaking_event.clear()
        finally:
            tts_queue.task_done()


def speak(text: str, wait: bool = True) -> None:
    message = str(text)
    print(f"\nJARVIS: {message}", flush=True)
    tts_queue.put(message)
    if wait:
        tts_queue.join()


def read_document_aloud(text: str, chunk_size: int = 850) -> None:
    if not text.strip():
        speak("The selected document is empty.")
        return
    for start in range(0, len(text), chunk_size):
        if shutdown_event.is_set():
            return
        speak(text[start:start + chunk_size])


def load_documents() -> None:
    global documents
    try:
        with DOCUMENT_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("Storage file must contain a JSON object")
        documents = {str(name): str(content) for name, content in data.items()}
    except FileNotFoundError:
        documents = {}
    except (json.JSONDecodeError, ValueError, OSError) as error:
        documents = {}
        print(f"Warning: documents could not be loaded: {error}")


def save_documents() -> bool:
    try:
        # Write to a temporary file first to avoid leaving truncated JSON.
        temporary = DOCUMENT_FILE.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(documents, file, indent=4, ensure_ascii=False)
        temporary.replace(DOCUMENT_FILE)
        return True
    except OSError as error:
        print(f"Unable to save documents: {error}")
        speak("I could not save the document storage file.")
        return False


def find_document_name(requested_name: str) -> Optional[str]:
    requested = requested_name.strip()
    if requested.isdecimal():
        number = int(requested)
        names = list(documents)
        if 1 <= number <= len(names):
            return names[number - 1]
    for saved_name in documents:
        if saved_name.casefold() == requested.casefold():
            return saved_name
    return None


def read_text_file(path_text: str) -> str:
    path = Path(path_text.strip().strip('"').strip("'"))
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError, UnicodeDecodeError, OSError) as error:
        print(f"Unable to read file {path}: {error}")
        return ""


def recognize_from_microphone(
    recognizer: sr.Recognizer, source: sr.Microphone,
    timeout: int = VOICE_LISTEN_TIMEOUT,
    phrase_time_limit: int = VOICE_PHRASE_LIMIT
) -> str:
    try:
        audio = recognizer.listen(source, timeout=timeout,
                                  phrase_time_limit=phrase_time_limit)
        text = recognizer.recognize_google(audio).strip()
        if text:
            print(f"\nYou said: {text}")
        return text
    except (sr.WaitTimeoutError, sr.UnknownValueError):
        return ""
    except sr.RequestError as error:
        print(f"Speech recognition service unavailable: {error}")
        return ""


def voice_listener_worker() -> None:
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    try:
        with sr.Microphone() as source:
            print("Initializing microphone...")
            recognizer.adjust_for_ambient_noise(
                source, duration=AMBIENT_NOISE_DURATION
            )
            microphone_available_event.set()
            print('Voice input ready. Say "Jarvis" at any time.')
            while not shutdown_event.is_set():
                if speaking_event.is_set():
                    time.sleep(0.1)
                    continue
                text = recognize_from_microphone(recognizer, source)
                if not text or shutdown_event.is_set():
                    continue
                if awaiting_response_event.is_set():
                    response_queue.put(("voice", text))
                    continue
                lowered = text.casefold()
                if WAKE_WORD not in lowered:
                    continue
                position = lowered.find(WAKE_WORD)
                command = text[position + len(WAKE_WORD):].strip()
                command_queue.put(("voice", command or "__WAKE__"))
    except Exception as error:
        print(f"Microphone unavailable or voice listener stopped: {error}")
    finally:
        microphone_available_event.clear()


def keyboard_listener_worker() -> None:
    """Keep keyboard input active while the main thread processes commands.

    input() cannot be reliably interrupted in the Eclipse console; shutdown
    therefore has a Windows-specific final safeguard in main().
    """
    while not shutdown_event.is_set():
        try:
            typed_text = input().strip()
        except EOFError:
            return
        except KeyboardInterrupt:
            command_queue.put(("keyboard", "exit"))
            return
        if shutdown_event.is_set():
            return
        if not typed_text:
            continue
        if awaiting_response_event.is_set():
            response_queue.put(("keyboard", typed_text))
        else:
            command_queue.put(("keyboard", typed_text))


def clear_response_queue() -> None:
    while True:
        try:
            response_queue.get_nowait()
        except queue.Empty:
            return


def get_information(question: str, *, preserve_case: bool = True,
                    allow_empty: bool = False) -> str:
    clear_response_queue()
    awaiting_response_event.set()
    try:
        speak(question)
        if microphone_available_event.is_set():
            print("Answer by speaking, or type your answer and press ENTER.")
        else:
            print("Type your answer and press ENTER.")
        while not shutdown_event.is_set():
            try:
                source, answer = response_queue.get(timeout=0.25)
            except queue.Empty:
                continue
            answer = answer.strip()
            if answer or allow_empty:
                print(f"Input received from {source}.")
                return answer if preserve_case else answer.casefold()
        return ""
    finally:
        awaiting_response_event.clear()


def get_multiline_document_text() -> str:
    clear_response_queue()
    awaiting_response_event.set()
    lines = []
    try:
        speak("Provide the document text. Keyboard users type END on a line "
              "by itself; voice users say FINISHED when done.")
        print("\nDocument entry active. Type END or say FINISHED to finish.")
        while not shutdown_event.is_set():
            try:
                source, text = response_queue.get(timeout=0.25)
            except queue.Empty:
                continue
            cleaned = text.strip()
            if cleaned.casefold() in {"end", "finished", "finish", "done"}:
                break
            if cleaned:
                lines.append(cleaned)
                print(f"Added document text from {source}.")
        return "\n".join(lines).strip()
    finally:
        awaiting_response_event.clear()


def show_menu() -> None:
    print("""
============================================================
                 JARVIS DOCUMENT ASSISTANT
============================================================
Say "Jarvis" followed by a command, or type a menu number.

1. Store a new document
2. Import a text file
3. List stored documents
4. Select a document
5. Show the selected document
6. Read the selected document aloud
7. Delete a document
8. Show accessibility status
9. Show this help menu
0. Exit

Voice examples: Jarvis list documents / Jarvis read / Jarvis exit
============================================================
""")


def interpret_command(text: str) -> str:
    normalized = text.casefold().strip()
    if normalized.startswith(WAKE_WORD):
        normalized = normalized[len(WAKE_WORD):].strip()
    exact = {
        "0": "exit", "1": "store", "2": "import", "3": "list",
        "4": "select", "5": "show", "6": "read", "7": "delete",
        "8": "status", "9": "help", "quit": "exit",
        "close": "exit", "stop": "exit", "menu": "help",
        "shutdown": "exit", "stop program": "exit"
    }
    if normalized in exact:
        return exact[normalized]
    if "store" in normalized or "save document" in normalized:
        return "store"
    if "import" in normalized or "load file" in normalized:
        return "import"
    if "list" in normalized:
        return "list"
    if "select" in normalized or "choose" in normalized:
        return "select"
    if "show" in normalized or "display" in normalized:
        return "show"
    if "read" in normalized or "speak document" in normalized:
        return "read"
    if "delete" in normalized or "remove" in normalized:
        return "delete"
    if "status" in normalized or "accessibility" in normalized:
        return "status"
    if "help" in normalized:
        return "help"
    if any(word in normalized for word in ("exit", "quit", "close program")):
        return "exit"
    return "invalid"


def store_document() -> None:
    global current_doc
    name = get_information("What is the document name?")
    if not name:
        speak("A document name is required.")
        return
    existing = find_document_name(name)
    if existing:
        confirmation = get_information(
            f"{existing} already exists. Say or type yes to replace it.",
            preserve_case=False
        )
        if confirmation not in {"yes", "y"}:
            speak("The existing document was not changed.")
            return
        name = existing
    content = get_multiline_document_text()
    if not content:
        speak("No document text was provided.")
        return
    old = documents.get(name)
    documents[name] = content
    if save_documents():
        current_doc = name
        speak(f"Document {name} has been stored and selected.")
    elif old is None:
        documents.pop(name, None)
    else:
        documents[name] = old


def import_document() -> None:
    global current_doc
    path_text = get_information("What is the complete path to the text file?")
    if not path_text:
        speak("A file path is required.")
        return
    content = read_text_file(path_text)
    if not content:
        speak("I could not import that file, or the file was empty.")
        return
    suggested = Path(path_text.strip().strip('"').strip("'")).stem
    name = get_information(f"What should I call this document? You may use {suggested}.",
                           allow_empty=True) or suggested
    existing = find_document_name(name)
    if existing:
        confirmation = get_information(
            f"{existing} already exists. Say or type yes to replace it.",
            preserve_case=False
        )
        if confirmation not in {"yes", "y"}:
            speak("The existing document was not changed.")
            return
        name = existing
    old = documents.get(name)
    documents[name] = content
    if save_documents():
        current_doc = name
        speak(f"{name} has been imported, saved, and selected.")
    elif old is None:
        documents.pop(name, None)
    else:
        documents[name] = old


def list_documents() -> None:
    if not documents:
        speak("There are no stored documents.")
        return
    speak(f"There are {len(documents)} stored documents.")
    for number, name in enumerate(documents, start=1):
        marker = " (selected)" if name == current_doc else ""
        print(f"{number}. {name}{marker}", flush=True)
        speak(name)


def select_document() -> None:
    global current_doc
    if not documents:
        speak("There are no documents to select.")
        return
    list_documents()
    requested = get_information("Which document would you like to select? "
                                "Say or type its name or number.")
    found = find_document_name(requested)
    if not found:
        speak("Document not found.")
        return
    current_doc = found
    speak(f"{found} is now the selected document.")


def get_selected_document_name() -> Optional[str]:
    if current_doc and current_doc in documents:
        return current_doc
    if not documents:
        speak("There are no stored documents.")
        return None
    speak("No document is currently selected.")
    select_document()
    return current_doc if current_doc in documents else None


def display_document(name: str) -> None:
    print(f"\n---------- {name} ----------")
    print(documents[name])
    print("-" * (22 + len(name)))


def show_document() -> None:
    name = get_selected_document_name()
    if name is not None:
        display_document(name)


def read_selected_document() -> None:
    name = get_selected_document_name()
    if name is None:
        return
    display_document(name)
    speak(f"Reading {name}.")
    read_document_aloud(documents[name])


def delete_document() -> None:
    global current_doc
    if not documents:
        speak("There are no documents to delete.")
        return
    list_documents()
    requested = get_information("Which document should I delete? "
                                "Say or type its name or number.")
    found = find_document_name(requested)
    if not found:
        speak("Document not found.")
        return
    confirmation = get_information(
        f"Say or type yes to permanently delete {found}.",
        preserve_case=False
    )
    if confirmation not in {"yes", "y"}:
        speak("The document was not deleted.")
        return
    old_content = documents.pop(found)
    if save_documents():
        if current_doc == found:
            current_doc = None
        speak(f"{found} has been deleted.")
    else:
        documents[found] = old_content


def show_accessibility_status() -> None:
    status = "available" if microphone_available_event.is_set() else "unavailable"
    print("\nAccessibility Status\n--------------------")
    print("Keyboard input: available")
    print(f"Microphone input: {status}")
    print("Text-to-speech: enabled")
    print(f'Wake word: "{WAKE_WORD.title()}"')
    print("Persistent document storage: enabled")
    speak(f"Keyboard input is available. Microphone input is {status}. "
          f"The wake word is {WAKE_WORD.title()}.")


def execute_command(raw_command: str) -> bool:
    command = interpret_command(raw_command)
    if command == "exit":
        speak("Goodbye.")
        return False
    actions = {
        "store": store_document, "import": import_document,
        "list": list_documents, "select": select_document,
        "show": show_document, "read": read_selected_document,
        "delete": delete_document, "status": show_accessibility_status,
        "help": show_menu
    }
    action = actions.get(command)
    if action:
        action()
    else:
        speak("I did not understand that command. Say Jarvis help "
              "or type help to show the menu.")
    return True


def start_input_threads() -> None:
    global keyboard_thread
    speech_thread = threading.Thread(
        target=text_to_speech_worker, name="TextToSpeechWorker", daemon=True
    )
    keyboard_thread = threading.Thread(
        target=keyboard_listener_worker, name="KeyboardListener", daemon=True
    )
    voice_thread = threading.Thread(
        target=voice_listener_worker, name="VoiceListener", daemon=True
    )
    speech_thread.start()
    tts_ready_event.wait(timeout=5)
    keyboard_thread.start()
    voice_thread.start()


def main() -> None:
    load_documents()
    print("=" * 60)
    print(APP_NAME.center(60))
    print("=" * 60)
    print(f"Storage file: {DOCUMENT_FILE}")
    print("Starting keyboard and voice input...")
    print(f"Speech system: {platform.system()} native speech")
    start_input_threads()
    speak("Jarvis is online.")
    show_menu()
    print('\nVoice is automatic. Say "Jarvis" or type a command.')
    try:
        running = True
        while running and not shutdown_event.is_set():
            try:
                source, raw_command = command_queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if raw_command == "__WAKE__":
                raw_command = get_information("Yes? How can I help you?")
                if not raw_command:
                    speak("I did not receive a command.")
                    continue
            print(f"\nCommand received from {source}: {raw_command}")
            running = execute_command(raw_command)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received.")
    finally:
        # Finish spoken output before initiating shutdown.
        tts_queue.join()
        shutdown_event.set()
        print("JARVIS has closed.", flush=True)
        # Eclipse on Windows can leave input() blocked in a daemon thread.
        # A normal interpreter shutdown can then crash inside stdin cleanup.
        # No document writes are pending here: each save is synchronous.
        # os._exit bypasses Python's interpreter teardown and atexit hooks.
        if platform.system() == "Windows" and keyboard_thread is not None:
            keyboard_thread.join(timeout=0.15)
            if keyboard_thread.is_alive():
                sys.stdout.flush()
                sys.stderr.flush()
                os._exit(0)


if __name__ == "__main__":
    main()
