# HealthExpress

A hackathon prototype for a multilingual, AI-assisted health-question workflow using phone calls, text messages, and a web interface.

The project explores how someone might answer a structured series of questions in their preferred language and review their responses later. It is an experiment in conversational interfaces—not a medical product.

## What we built

- **Voice and SMS flows:** Twilio handles incoming responses and phone interactions.
- **Guided questions:** A decision-tree structure controls the prompts and follow-up questions.
- **Language support:** The application includes English, Hindi, and Tamil messaging.
- **AI-assisted interpretation:** OpenAI API calls help interpret responses to questions.
- **Audio responses:** ElevenLabs text-to-speech, with AWS S3 used to serve generated audio.
- **Web views:** Flask templates support a web form, conversation views, and an interaction-history page.

## Stack

Python · Flask · Twilio · OpenAI API · ElevenLabs · AWS S3 · HTML/CSS/JavaScript

## Project structure

- [`index.py`](index.py) — Flask routes and Twilio interactions
- [`tree.py`](tree.py) — question/decision-tree data
- [`conversation_logic.py`](conversation_logic.py) — interpreting responses and managing the conversation
- [`tts.py`](tts.py) — multilingual audio generation
- [`user_history.py`](user_history.py) — storing interaction history
- [`templates/`](templates) — the web interface

## Running the prototype

The original project depends on third-party accounts and credentials for Twilio, OpenAI, ElevenLabs, and AWS. It also expects a public callback URL for phone and SMS interactions. You can inspect the source without configuring those services, but **a fresh clone is not a ready-to-run demo**.

The code and pinned dependencies are preserved from the hackathon and have not been validated as a modern production deployment.

## Important limitations

This is a **historical educational prototype**, not a medical device or diagnosis service. Do not rely on its outputs for medical decisions or use real patient data. The original implementation needs security, privacy, and dependency updates—including credential logging and storage review—before it could be deployed responsibly.
