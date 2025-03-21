import os
import openai
import pvporcupine
import pyaudio
import struct
import speech_recognition as sr
import requests
import pyttsx3  # Text-to-Speech
import subprocess  # For Safari opening
from dotenv import load_dotenv
from serpapi import GoogleSearch  # Google Search API for real-time data

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORCUPINE_ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")  # Google Search API Key

if not OPENAI_API_KEY:
    raise ValueError("❌ Missing OpenAI API Key! Please set OPENAI_API_KEY in your .env file.")
if not PORCUPINE_ACCESS_KEY:
    raise ValueError("❌ Missing Porcupine Access Key! Please set PORCUPINE_ACCESS_KEY in your .env file.")
if not SERPAPI_KEY:
    raise ValueError("❌ Missing SerpAPI Key! Please set SERPAPI_KEY in your .env file.")

# Initialize OpenAI client
client = openai.OpenAI(api_key=OPENAI_API_KEY)

engine = pyttsx3.init()
engine.setProperty('rate', 160)
engine.setProperty('volume', 1.0)

def speak(text):
    """Speak text in a British male AI voice."""
    engine = pyttsx3.init()
    engine.setProperty('rate', 165)
    engine.setProperty('volume', 1.2)
    engine.setProperty('voice', "com.apple.voice.compact.en-GB.Daniel")
    engine.say(text)
    engine.runAndWait()

# Synonyms for user confirmations
YES_SYNONYMS = [
    "yes", "yes that is correct", "that's correct", "correct", "sure", "absolutely",
    "go ahead", "send it", "send email", "yes please"
]
NO_SYNONYMS = [
    "no", "nope", "cancel", "stop", "never mind", "nah"
]

def is_affirmative(user_text: str) -> bool:
    """Return True if user_text matches any yes synonyms."""
    lt = user_text.lower().strip()
    for syn in YES_SYNONYMS:
        if syn in lt:
            return True
    return False

def is_negative(user_text: str) -> bool:
    """Return True if user_text matches any no synonyms."""
    lt = user_text.lower().strip()
    for syn in NO_SYNONYMS:
        if syn in lt:
            return True
    return False

# Mapping recognized domain words to actual domain strings
DOMAIN_MAP = {
    "gmail": "@gmail.com",
    "yahoo": "@yahoo.com",
    "icloud": "@icloud.com",
    "outlook": "@outlook.com",
    "hotmail": "@hotmail.com"
}

def parse_email_in_one_utterance():
    """
    Prompt user to speak the entire email, e.g. "j o h n d o e at yahoo".
    We'll parse tokens -> local part, then domain, building "johndoe@yahoo.com".
    Once domain is recognized, we finalize.
    """
    speak(
        "Please spell each letter or number in one phrase. "
        "For example, if you want to send to JohnDoe at yahoo dot com, "
        "you would say: 'j o h n d o e at yahoo'."
    )
    full_utterance = recognize_speech() or ""
    if not full_utterance:
        return None

    speak(f"I heard: {full_utterance}. Let me parse that now.")
    tokens = full_utterance.lower().split()

    # synonyms for digits etc.
    synonyms_map = {
        "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8",
        "nine": "9", "zero": "0", "dot": ".", "period": ".",
        "dash": "-", "underscore": "_"
    }

    local_part = []
    domain_part = None

    i = 0
    while i < len(tokens):
        tok = tokens[i].strip()

        if tok == "at" and (i + 1) < len(tokens):
            maybe_domain = tokens[i+1].lower().strip()
            if maybe_domain in DOMAIN_MAP:
                domain_part = DOMAIN_MAP[maybe_domain]
                i += 2
                break
            else:
                speak(f"I didn't recognize domain '{maybe_domain}'. Let's try again.")
                return None
        else:
            # handle synonyms
            if tok in synonyms_map:
                letter = synonyms_map[tok]
            else:
                letter = tok

            # expand if user lumps multiple chars
            for c in letter:
                local_part.append(c)
        i += 1

    spelled_local = "".join(local_part)
    if not domain_part:
        # maybe user spelled full "john@yahoo.com" or didn't specify domain
        if "@" in spelled_local:
            final_email = spelled_local
        else:
            speak("I did not hear a recognized domain like 'gmail' or 'yahoo'. Let's try again.")
            return None
    else:
        final_email = spelled_local + domain_part

    speak(f"You spelled out {final_email}. Is that correct?")
    confirm = recognize_speech() or ""
    if is_affirmative(confirm):
        return final_email
    else:
        speak("Let's try again.")
        return None

def send_email_outlook(recipient_email, subject, body):
    """Sends an Outlook email via AppleScript."""
    applescript = f'''
    tell application "Microsoft Outlook"
        set newMessage to make new outgoing message
        tell newMessage
            make new recipient with properties {{email address:{{address:"{recipient_email}"}}}}
            set subject to "{subject}"
            set content to "{body}"
            send
        end tell
    end tell
    '''
    subprocess.run(["osascript", "-e", applescript])

########################################
# Speech Recognition
########################################

recognizer = sr.Recognizer()
recognizer.pause_threshold = 1.5
recognizer.dynamic_energy_threshold = True

def recognize_speech(phrase_time=10):
    """
    Capture user voice input with a default phrase_time seconds limit.
    """
    with sr.Microphone() as source:
        print("🎤 Listening for a command...")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        audio = recognizer.listen(source, phrase_time_limit=phrase_time)
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

def recognize_speech_long():
    """
    For the email body: let's allow more time, say 30 seconds to avoid cutoff.
    """
    return recognize_speech(phrase_time=30)

########################################
# GPT & Search
########################################

def chat_with_gpt(prompt):
    """Use GPT for normal queries."""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are Jarvis, a helpful AI assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Error communicating with OpenAI: {e}")
        return "I'm sorry, I couldn't process that request."

def search_google(query):
    """Use SerpAPI for real-time search."""
    params = {"q": query, "hl": "en", "gl": "us", "api_key": SERPAPI_KEY}
    try:
        from serpapi import GoogleSearch
        gs = GoogleSearch(params)
        results = gs.get_dict()
        if "organic_results" in results:
            return results["organic_results"][0].get("snippet", "")
        else:
            return "❌ No real-time results found."
    except Exception as e:
        print(f"❌ Error fetching search results: {e}")
        return "I'm sorry, I couldn't fetch live data."

########################################
# Wake Word & Main
########################################

import pvporcupine
porcupine = pvporcupine.create(
    access_key=PORCUPINE_ACCESS_KEY,
    keyword_paths=["/Users/dawitk/Documents/jarvis-ai-assistant/jarvis_mac.ppn"]
)

import pyaudio
pa = pyaudio.PyAudio()
audio_stream = pa.open(
    rate=porcupine.sample_rate,
    channels=1,
    format=pyaudio.paInt16,
    input=True,
    frames_per_buffer=porcupine.frame_length
)

def detect_wake_word():
    print("🔊 JARVIS is listening for the wake word...")
    while True:
        pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
        import struct
        pcm_unpacked = struct.unpack_from("h" * porcupine.frame_length, pcm)
        keyword_index = porcupine.process(pcm_unpacked)
        if keyword_index >= 0:
            print("\n✅ Wake word detected! JARVIS is ready.")
            speak("Hello, Creator.")
            process_conversation()

def process_conversation():
    while True:
        user_input = recognize_speech()
        if user_input:
            # QUIT
            if user_input in ["exit", "quit", "goodbye", "shut down"]:
                print("👋 JARVIS: Goodbye, Creator.")
                speak("Goodbye, Creator.")
                cleanup()
                break

            # SEND EMAIL
            if "send email" in user_input:
                spelled_email = parse_email_in_one_utterance()
                if not spelled_email:
                    speak("No valid email address was provided. Cancelling.")
                    continue

                speak("What is the subject of your email?")
                subject_line = recognize_speech() or "No Subject"

                speak("What would you like the message to say? Take your time.")
                # Use the longer speech for body
                body_content = recognize_speech_long() or ""

                speak(f"You want me to send an email to {spelled_email}, subject {subject_line}, with content: {body_content}. Shall I send it now?")
                confirm = recognize_speech() or ""
                if is_affirmative(confirm):
                    send_email_outlook(spelled_email, subject_line, body_content)
                    speak("Email sent.")
                else:
                    speak("Email cancelled.")
                continue

            # "open X in safari" => X.com
            if "open" in user_input and "in safari" in user_input:
                domain = user_input.replace("open", "").replace("in safari", "").strip()
                if not domain.endswith(".com"):
                    domain += ".com"
                safari_url = f"https://{domain}"
                subprocess.run(["open", "-a", "Safari", safari_url])
                speak(f"Opening {domain}.")
                continue

            # "open X" => Mac app
            if user_input.startswith("open "):
                app_name = user_input.replace("open ", "").strip()
                subprocess.run(["open", "-a", app_name])
                speak(f"Opening {app_name}.")
                continue

            # "search X"
            if user_input.startswith("search "):
                search_query = user_input.replace("search ", "").strip()
                google_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
                subprocess.run(["open", "-a", "Safari", google_url])
                speak(f"Searching for {search_query}.")
                continue

            # Real-time search or GPT
            if any(keyword in user_input for keyword in ["news", "update", "latest", "who", "what", "where", "how"]):
                response = search_google(user_input)
            else:
                response = chat_with_gpt(user_input)

            print(f"🤖 JARVIS: {response}")
            speak(response)

def cleanup():
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

if __name__ == "__main__":
    try:
        detect_wake_word()
    except KeyboardInterrupt:
        print("\n🛑 JARVIS: Shutting down...")
        cleanup()
        exit()

