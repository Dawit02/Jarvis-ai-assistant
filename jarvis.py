import speech_recognition as sr
import openai
import os
import pyttsx3
from dotenv import load_dotenv

# Load API Key from .env file
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize Text-to-Speech Engine
tts_engine = pyttsx3.init()

def speak(text):
    """Convert text to speech and speak it."""
    tts_engine.say(text)
    tts_engine.runAndWait()

def recognize_speech():
    """Capture voice input and convert to text."""
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    
    with mic as source:
        print("Listening... Speak now.")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)

    try:
        text = recognizer.recognize_google(audio)
        print(f"You said: {text}")
        return text
    except sr.UnknownValueError:
        print("Could not understand audio")
        return None
    except sr.RequestError:
        print("Error connecting to speech recognition service")
        return None

def chat_with_gpt(prompt):
    """Send input to GPT and return response."""
    try:
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "You are JARVIS, an AI assistant."},
                      {"role": "user", "content": prompt}],
            max_tokens=150
        )
        return response.choices[0].message.content
    except Exception as e:
        print("Error communicating with GPT:", e)
        return None

if __name__ == "__main__":
    while True:
        print("\nSay something to JARVIS...")
        user_input = recognize_speech()
        
        if user_input:
            if user_input.lower() in ["exit", "quit"]:
                speak("Goodbye!")
                break
            
            response = chat_with_gpt(user_input)
            if response:
                print("JARVIS:", response)
                speak(response)

