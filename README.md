# HealthIndia

Start instructions:

```bash
source venv/bin/activate
ngrok http 127.0.0.1:5000
```

## Inspiration
Health disparities in rural India, where language and literacy barriers hinder access to quality healthcare, inspired us. We wanted to use AI to bridge this gap and provide equitable health solutions.

## What it does
HealthIndia utilizes AI-driven speech generation, audio processing, and multilingual support to gather comprehensive medical histories from villagers in rural regions quickly, enabling healthcare providers to make informed decisions without wasting time. The application allows patients to immediately interact with artificial intelligence over phone calls for quick diagnosis and medical documentation, as well as notify medical professionals of their symptoms with a user-friendly web form.

## How we built it
We built HealthIndia using AI speech-to-text and text-to-speech technologies integrated with a decision tree classifier for diagnosis. It’s powered by GPT API for natural language processing and built on a Flask web app framework.

## Challenges we ran into
We faced challenges in ensuring the AI could accurately understand diverse dialects and accents, integrating multiple languages seamlessly, and designing a user-friendly interface for low-tech environments. We also faced challenges in the limited usage of packages that are integral to our application, i.e., free trials for Twillio and rate limited API calls by OpenAI.

## Accomplishments that we're proud of
We're proud to have created a functional system that can bridge communication barriers, making healthcare more accessible to underserved communities. Our app can handle multiple languages and accurately process audio data.

## What we learned
We learned the importance of user testing in real-world scenarios, especially when dealing with varied languages and accents. We also had to be mindful of the limited access to technology for rural and isolated villages.  On the technical side, we learned a number of important frameworks and technologies, including Flask, React, Twilio and OpenAI APIs. 


## What's next for HealthIndia
Next, we plan to enhance the app by adding more language options, improving AI's ability to handle complex medical conversations (i.e. complexifying the decision tree), and utilizing a backend database for efficient and protected storage of patient information.