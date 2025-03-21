import os
import openai
import pvporcupine
import pyaudio
import struct
import speech_recognition as sr
import requests
import pyttsx3  # Text-to-Speech
from dotenv import load_dotenv
from serpapi import GoogleSearch  # Google Search API for real-time data

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORCUPINE_ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")  # Google Search API Key

# Check if API keys are loaded correctly
if not OPENAI_API_KEY:
    raise ValueError("❌ Missing OpenAI API Key! Please set OPENAI_API_KEY in your .env file.")
if not PORCUPINE_ACCESS_KEY:
    raise ValueError("❌ Missing Porcupine Access Key! Please set PORCUPINE_ACCESS_KEY in your .env file.")
if not SERPAPI_KEY:
    raise ValueError("❌ Missing SerpAPI Key! Please set SERPAPI_KEY in your .env file.")

# Initialize OpenAI client
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Initialize Text-to-Speech Engine
engine = pyttsx3.init()
engine.setProperty('rate', 160)  # Adjust speed of speech
engine.setProperty('volume', 1.0)  # Set volume level

# Set JARVIS voice to Daniel (British English)
def speak(text):
    """Make JARVIS speak using a British male AI voice."""
    engine = pyttsx3.init()
    engine.setProperty('rate', 165)  # Slightly faster speech
    engine.setProperty('volume', 1.2)  # Increase volume for clarity

    # Set to Daniel's British English Voice
    engine.setProperty('voice', "com.apple.voice.compact.en-GB.Daniel")

    engine.say(text)
    engine.runAndWait()

# Initialize Porcupine for wake word detection
porcupine = pvporcupine.create(
    access_key=PORCUPINE_ACCESS_KEY,
    keyword_paths=["/Users/dawitk/Documents/jarvis-ai-assistant/jarvis_mac.ppn"]  # Update path if needed
)

# Initialize Speech Recognizer
recognizer = sr.Recognizer()

# Initialize PyAudio for wake-word detection
pa = pyaudio.PyAudio()
audio_stream = pa.open(
    rate=porcupine.sample_rate,
    channels=1,
    format=pyaudio.paInt16,
    input=True,
    frames_per_buffer=porcupine.frame_length
)

def chat_with_gpt(prompt):
    """Send a message to OpenAI GPT-4 and return the response."""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "You are Jarvis, a helpful AI assistant."},
                      {"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Error communicating with OpenAI: {e}")
        return "I'm sorry, I couldn't process that request."

def search_google(query):
    """Perform a real-time Google search using SerpAPI and return the top result."""
    params = {
        "q": query,
        "hl": "en",
        "gl": "us",
        "api_key": SERPAPI_KEY
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()

        if "organic_results" in results:
            first_result = results["organic_results"][0]["snippet"]
            return first_result
        else:
            return "❌ No real-time results found."
    
    except Exception as e:
        print(f"❌ Error fetching search results: {e}")
        return "I'm sorry, I couldn't fetch live data."

def recognize_speech():
    """Capture user voice input and convert to text using SpeechRecognition."""
    with sr.Microphone() as source:
        print("🎤 Listening for a command...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)

    try:
        command = recognizer.recognize_google(audio).lower()
        print(f"🗣️ You said: {command}")
        return command
    except sr.UnknownValueError:
        print("❌ Sorry, I couldn't understand that.")
        return None
    except sr.RequestError as e:
        print(f"❌ Could not request results; {e}")
        return None

def detect_wake_word():
    """Continuously listens for the wake word 'Hey JARVIS'."""
    print("🔊 JARVIS is listening for the wake word...")
    
    while True:
        pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
        pcm_unpacked = struct.unpack_from("h" * porcupine.frame_length, pcm)

        keyword_index = porcupine.process(pcm_unpacked)
        if keyword_index >= 0:
            print("\n✅ Wake word detected! JARVIS is ready.")
            
            # Greet with "Hello, Creator"
            speak("Hello, Creator.")
            
            process_conversation()

def process_conversation():
    """Processes multiple user commands after wake word detection."""
    while True:
        user_input = recognize_speech()

        if user_input:
            if user_input in ["exit", "quit", "goodbye", "shut down"]:
                print("👋 JARVIS: Goodbye, Creator.")
                speak("Goodbye, Creator.")  # JARVIS will now say goodbye
                cleanup()
                break

            # Check if the query requires real-time search
            if any(keyword in user_input for keyword in ["news", "update", "latest", "who", "what", "where", "how"]):
                response = search_google(user_input)  # Fetch live data
            else:
                response = chat_with_gpt(user_input)  # Use AI for general reasoning

            print(f"🤖 JARVIS: {response}")
            speak(response)  # JARVIS will now speak the response

def cleanup():
    """Properly closes all audio resources to prevent crashes."""
    global audio_stream, pa, porcupine
    try:
        if audio_stream and audio_stream.is_active():
            audio_stream.stop_stream()
            audio_stream.close()
        if pa:
            pa.terminate()
        if porcupine:
            porcupine.delete()
    except Exception as e:
        print(f"Error during cleanup: {e}")

# Run the assistant
if __name__ == "__main__":
    try:
        detect_wake_word()
    except KeyboardInterrupt:
        print("\n🛑 JARVIS: Shutting down...")
        cleanup()
        exit()

