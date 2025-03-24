# Voice Assistant Web UI

A modern web UI for a voice assistant application built with Vue.js and FastAPI.

## Features

- ChatGPT-style user interface
- Real-time voice recording and transcription
- WebSocket-based communication for streaming responses
- Red recording indicator with pulse animation
- Keyboard shortcuts for quick access

## Prerequisites

- Python 3.7+
- Web browser with microphone access support

## Installation

1. Clone this repository
2. Install the required Python packages:

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the root directory with your OpenAI API key:

```
OPENAI_API_KEY=your_api_key_here
```

## Running the Application

1. Start the FastAPI server:

```bash
python server.py
```

2. Open your web browser and navigate to:

```
http://localhost:8000/ui
```

## Usage

- Click the circle button or press `k` to start recording
- Speak your query/question
- Click the circle button or press `k` again to stop recording and process
- The assistant will respond with text (and voice if configured)
- Press `q` to quit the application

## Project Structure

- `server.py` - FastAPI server with WebSocket support
- `agent.py` - Voice agent workflow implementation
- `ui/` - Web UI files
  - `index.html` - Main HTML file
  - `css/styles.css` - CSS styles
  - `js/app.js` - Vue.js application
  - `assets/` - Icons and other assets

## Technical Details

This application uses:
- Vue.js from CDN for frontend reactivity
- FastAPI for the backend API and WebSocket server
- WebSockets for bidirectional communication
- Web Audio API for capturing audio
- The OpenAI Agents library for voice processing
