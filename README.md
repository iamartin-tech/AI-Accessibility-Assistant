
# JARVIS Document Assistant

## Project Overview

JARVIS Document Assistant is a Python-based accessibility application designed to help users interact with stored text documents through voice commands and keyboard input.

The application uses speech recognition to interpret spoken commands and text-to-speech technology to provide audible responses. Users can access stored documents, listen to their contents, and interact with the program without relying entirely on a keyboard.

The project demonstrates how Python, speech recognition, and document management can be combined to create an accessible application.

## Features

- Continuous listening for the "Jarvis" wake word
- Voice-command recognition
- Keyboard input as an alternative to voice commands
- Text-to-speech responses
- Reading stored documents aloud
- JSON-based document storage
- Document creation, selection, and deletion
- Help commands
- Voice commands for exiting the application

## Technologies Used

- Python 3.10+
- SpeechRecognition
- pyttsx3
- JSON
- Microphone and audio-output support
- Eclipse IDE with PyDev

## Prerequisites

Before running the application, ensure that you have:

- Python 3.10 or newer
- An internet connection for online speech recognition
- A microphone for voice commands
- Speakers or headphones for audio responses
- The required Python dependencies

Keyboard input can be used when voice interaction is unavailable.

## Installation Instructions

### 1. Download the Project

Download or clone the GitHub repository.

```bash
git clone https://github.com/iamartin-tech/AI-Accessibility-Assistant.git
```

Navigate to the project directory:

```bash
cd AI-Accessibility-Assistant
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

### 3. Activate the Virtual Environment

Windows:

```bash
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the Application

```bash
python aiproject.py
```

The application should initialize and announce:

"Jarvis is online."

## Voice Commands

The application supports the following commands:

| Command | Description |
|---------|-------------|
| Jarvis list documents | Lists stored documents |
| Jarvis read | Begins the document-reading process |
| Jarvis help | Provides information about available commands |
| Jarvis exit | Closes the application |

### Direct Exit Commands

The application also recognizes exit commands without requiring the wake word:

- Exit
- Quit
- Close program
- Stop program
- Shutdown

## Document Storage

The application uses a JSON file to store documents.

Example file: `documents.json`

```json
{
    "sample doc text": "Hello, this is a sample document.",
    "sample": "This document demonstrates text storage.",
    "AI Overview": "Artificial intelligence supports speech recognition and other applications."
}
```

Documents can be accessed through the application's voice or keyboard interface.

## Testing Procedures

The following steps can be used to verify the application's functionality.

### Test 1: Application Startup

1. Open the project.
2. Run `aiproject.py`.
3. Verify that the application initializes.
4. Confirm that "Jarvis is online" is announced.

Expected result: The application starts without errors.

### Test 2: Document Listing

1. Activate the voice interface.
2. Say "Jarvis list documents."
3. Verify that stored documents are listed.

Expected result: The application identifies available documents.

### Test 3: Document Reading

1. Say "Jarvis read."
2. Follow the application's prompts to select a document.
3. Listen to the spoken output.

Expected result: The selected document is read aloud.

### Test 4: Keyboard Input

1. Start the application.
2. Use the keyboard input option.
3. Enter a supported command.
4. Verify that the command is processed.

Expected result: The application responds to keyboard input.

### Test 5: Exit Command

1. Start the application.
2. Say "Exit" or "Jarvis exit."
3. Verify that the application terminates.

Expected result: The application closes normally.

## Troubleshooting

### Missing Python Packages

If Python reports missing dependencies, run:

```bash
pip install -r requirements.txt
```

### Microphone Not Working

- Verify that the microphone is connected.
- Check operating system microphone permissions.
- Confirm that the correct audio input device is selected.
- Ensure that the required audio libraries are installed.

### Text-to-Speech Not Working

- Check speaker or headphone connections.
- Verify that the system audio is enabled.
- Confirm that the text-to-speech dependencies are installed.

### Speech Recognition Problems

- Check the internet connection if online recognition is used.
- Speak clearly and minimize background noise.
- Try keyboard input if speech recognition is unavailable.

## Development Environment

The project was developed using:

- Eclipse IDE
- PyDev
- Python

The application uses Python libraries for speech recognition and text-to-speech functionality.

## Project Objectives

The primary objectives of this project are to:

1. Develop a Python application supporting voice interaction.
2. Provide keyboard input as an alternative interface.
3. Implement document storage and retrieval.
4. Use text-to-speech technology to read documents aloud.
5. Explore accessibility-focused software development.

## Future Improvements

Potential improvements include:

- A graphical user interface
- Additional voice commands
- Improved offline speech recognition
- Support for additional document formats
- More advanced document searching

## Author

Ian Martin

Bachelor of Science in Computer and Information Sciences

Lamar University

GitHub: https://github.com/iamartin-tech

Portfolio: https://iamartin-tech.github.io/github-portfolio/
