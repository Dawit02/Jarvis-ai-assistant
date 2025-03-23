import os
import openai
import pvporcupine
import pyaudio
import struct
import speech_recognition as sr
import requests
import pyttsx3
import subprocess
from dotenv import load_dotenv
from serpapi import GoogleSearch
import dateparser
import re
import json
import time
import threading

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORCUPINE_ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

if not OPENAI_API_KEY:
    raise ValueError("❌ Missing OpenAI API Key! Please set OPENAI_API_KEY in your .env file.")
if not PORCUPINE_ACCESS_KEY:
    raise ValueError("❌ Missing Porcupine Access Key! Please set PORCUPINE_ACCESS_KEY in your .env file.")
if not SERPAPI_KEY:
    raise ValueError("❌ Missing SerpAPI Key! Please set SERPAPI_KEY in your .env file.")

# Initialize OpenAI client
import openai
client = openai.OpenAI(api_key=OPENAI_API_KEY)

engine = pyttsx3.init()
engine.setProperty('rate', 160)
engine.setProperty('volume', 1.0)

#############################
# Global states
#############################
muted = False          # If True, Jarvis won't listen or speak
last_button = None     # To avoid repeated triggers
stop_flag = False      # If True, we forcibly stop speech mid-sentence

def speak(text):
    """Speak text in a British male AI voice."""
    global muted
    if muted:
        print(f"(Muted) Would have spoken: {text}")
        return
    engine = pyttsx3.init()
    engine.setProperty('rate', 165)
    engine.setProperty('volume', 1.2)
    engine.setProperty('voice', "com.apple.voice.compact.en-GB.Daniel")
    engine.say(text)
    engine.runAndWait()

#############################
# AppleScript to Query Contacts
#############################
def lookup_contact_in_mac_contacts(name: str):
    applescript = f'''
    tell application "Contacts"
        set matches to every person whose name contains "{name}"
        if (count of matches) > 0 then
            set phoneValue to value of phone 1 of item 1 of matches
            return phoneValue
        else
            return "NOT FOUND"
        end if
    end tell
    '''
    result = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True)
    phone_str = result.stdout.strip()
    if phone_str == "NOT FOUND" or phone_str == "":
        return None
    return phone_str

def speak_phone_number_digits(number_str: str):
    spaced = " ".join(number_str)
    speak(f"The phone number is {spaced}.")

#############################
# YES / NO synonyms
#############################
YES_SYNONYMS = [
    "yes", "yes that is correct", "that's correct", "correct", 
    "sure", "absolutely", "go ahead", "send it", "send email", 
    "yes please", "create event", "add event", "okay", 
    "add", "confirm", "yes do it", "create it", "call", "call now", "make call"
]
NO_SYNONYMS = [
    "no", "nope", "cancel", "stop", "never mind", "nah"
]

def is_affirmative(user_text):
    if not user_text:
        return False
    lt = user_text.lower()
    for syn in YES_SYNONYMS:
        if syn in lt:
            return True
    return False

def is_negative(user_text):
    if not user_text:
        return False
    lt = user_text.lower()
    for syn in NO_SYNONYMS:
        if syn in lt:
            return True
    return False

#############################
# AppleScript Automations
#############################
def shutdown_mac():
    applescript = '''tell application "System Events" to shut down'''
    subprocess.run(["osascript", "-e", applescript])

def send_imessage(contact_or_number, message_body):
    applescript = f'''
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddy to buddy "{contact_or_number}" of targetService
        send "{message_body}" to targetBuddy
    end tell
    '''
    subprocess.run(["osascript", "-e", applescript])

def facetime_call(contact_or_number):
    applescript = f'''
    tell application "FaceTime"
        activate
    end tell
    tell application "System Events"
        keystroke "{contact_or_number}"
        delay 1
        keystroke return
    end tell
    '''
    subprocess.run(["osascript", "-e", applescript])

def send_email_outlook(recipient_email, subject, body):
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

def add_reminder(task_name, date_str):
    applescript = f'''
    tell application "Reminders"
        set newReminder to make new reminder with properties {{name:"{task_name}", remind me date:date "{date_str}"}}
    end tell
    '''
    subprocess.run(["osascript", "-e", applescript])

def add_calendar_event(event_name, start_date, end_date):
    applescript = f'''
    tell application "Calendar"
        tell calendar "Home"
            make new event with properties {{summary:"{event_name}", start date: date "{start_date}", end date: date "{end_date}"}}
        end tell
    end tell
    '''
    subprocess.run(["osascript", "-e", applescript])

#############################
# dateparser
#############################
def parse_natural_datetime(user_text):
    import dateparser
    dt = dateparser.parse(user_text, languages=["en"])
    if not dt:
        return None
    return dt.strftime("%B %d, %Y at %I:%M %p")

#############################
# Hardware Data Integration
#############################
def get_hardware_data():
    """Reads and returns the hardware data from hardware_data.json."""
    try:
        with open("hardware_data.json", "r") as f:
            data = json.load(f)
        return data
    except Exception as e:
        print("Error reading hardware_data.json:", e)
        return None

def answer_temperature_query():
    data = get_hardware_data()
    if data and data.get("dht"):
        try:
            dht_str = data["dht"]  # e.g. "DHT:T:75F, H:40%"
            parts = dht_str[4:].split(',')
            temp_part = parts[0].strip()  # e.g., "T:75F"
            temp_str = temp_part.replace("T:", "").replace("F", "").strip()
            return f"The temperature in your room is {temp_str}°F."
        except Exception as e:
            print("Error parsing DHT data:", e)
            return "I'm sorry, I couldn't retrieve the temperature."
    return "I'm sorry, temperature data is not available right now."

def answer_humidity_query():
    data = get_hardware_data()
    if data and data.get("dht"):
        try:
            dht_str = data["dht"]
            parts = dht_str[4:].split(',')
            hum_part = parts[1].strip()  # e.g., "H:40%"
            hum_str = hum_part.replace("H:", "").replace("%", "").strip()
            return f"The humidity in your room is {hum_str}%."
        except Exception as e:
            print("Error parsing humidity data:", e)
            return "I'm sorry, I couldn't retrieve the humidity."
    return "I'm sorry, humidity data is not available right now."

#############################
# Speech Recognition
#############################
recognizer = sr.Recognizer()
recognizer.pause_threshold = 1.5
recognizer.dynamic_energy_threshold = True

def recognize_speech(phrase_time=30):
    global muted
    if muted:
        print("(Muted) Not listening.")
        return None
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

def chat_with_gpt(prompt):
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
    params = {"q": query, "hl": "en", "gl": "us", "api_key": os.getenv("SERPAPI_KEY")}
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

#############################
# Single-utterance email parse
#############################
DOMAIN_MAP = {
    "gmail": "@gmail.com",
    "yahoo": "@yahoo.com",
    "icloud": "@icloud.com",
    "outlook": "@outlook.com",
    "hotmail": "@hotmail.com"
}
def parse_email_in_one_utterance():
    speak(
        "Please spell each letter or number in one phrase. "
        "For example, if you want to send to JohnDoe at yahoo dot com, "
        "you would say: 'j o h n d o e at yahoo'."
    )
    full_utterance = recognize_speech(30) or ""
    if not full_utterance:
        return None
    speak(f"I heard: {full_utterance}. Let me parse that now.")

    synonyms_map = {
        "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8",
        "nine": "9", "zero": "0", "dot": ".", "period": ".",
        "dash": "-", "underscore": "_"
    }

    tokens = full_utterance.lower().split()
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
            if tok in synonyms_map:
                letter = synonyms_map[tok]
            else:
                letter = tok
            for c in letter:
                local_part.append(c)
        i += 1

    spelled_local = "".join(local_part)
    if not domain_part:
        if "@" in spelled_local:
            final_email = spelled_local
        else:
            speak("I did not recognize a domain like 'gmail' or 'yahoo'. Let's try again.")
            return None
    else:
        final_email = spelled_local + domain_part

    speak(f"You spelled out {final_email}. Is that correct?")
    confirm = recognize_speech(5) or ""
    if is_affirmative(confirm):
        return final_email
    else:
        speak("Let's try again.")
        return None

#############################
# Porcupine: Wake Word
#############################
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

###################################
# Combined logic for messages/calls
###################################
def parse_contact_or_number(user_command: str):
    pattern = r"(send message to|message|text|call|facetime|to)\s*"
    cleaned = re.sub(pattern, "", user_command, flags=re.IGNORECASE).strip()
    result = lookup_contact_in_mac_contacts(cleaned)
    if result:
        phone = re.sub(r"\D", "", result)
        return phone if phone else None
    phone_number = re.sub(r"\D", "", cleaned)
    if phone_number:
        return phone_number
    else:
        return None

def speak_phone_number_digits(number_str: str):
    spaced = " ".join(number_str)
    speak(f"The phone number is {spaced}.")

###################################
# BACKGROUND THREAD: Watch hardware_data.json for button events
###################################
def watch_hardware_data():
    global muted, stop_flag, last_button
    while True:
        data = get_hardware_data()
        if data and data.get("button"):
            button_val = data["button"]
            if button_val != last_button:
                last_button = button_val
                if button_val == "BTN:STOP":
                    print("🛑 Physical Stop Button pressed.")
                    stop_flag = True
                elif button_val == "BTN:MUTE":
                    print("🔇 Physical Mute Button pressed.")
                    muted = True
                elif button_val == "BTN:DEBUG":
                    print("⚙️ Physical Debug Button pressed.")
                    # Add your debug mode toggles here if needed
        time.sleep(0.5)

###################################
# MAIN PROCESS
###################################
def detect_wake_word():
    global stop_flag
    print("🔊 JARVIS is listening for the wake word...")
    while True:
        # If user pressed STOP, forcibly stop any speech
        if stop_flag:
            try:
                engine.stop()
            except:
                pass
            print("Speech forcibly stopped by button.")
            stop_flag = False
            # Return to listening for next wake word
        pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
        import struct
        pcm_unpacked = struct.unpack_from("h" * porcupine.frame_length, pcm)
        keyword_index = porcupine.process(pcm_unpacked)
        if keyword_index >= 0:
            print("\n✅ Wake word detected! JARVIS is ready.")
            if not muted:
                speak("Hello, Creator.")
                process_conversation()
            else:
                print("(Muted) ignoring conversation...")

def process_conversation():
    global stop_flag, muted
    while True:
        if stop_flag:
            try:
                engine.stop()
            except:
                pass
            print("Conversation forcibly stopped by button.")
            stop_flag = False
            return
        user_input = recognize_speech(30) or ""
        if user_input:
            if stop_flag:
                try:
                    engine.stop()
                except:
                    pass
                print("Conversation forcibly stopped by button.")
                stop_flag = False
                return

            # QUIT triggers
            if user_input in ["exit", "quit", "goodbye", "shut down"]:
                print("👋 JARVIS: Goodbye, Creator.")
                speak("Goodbye, Creator.")
                cleanup()
                break

            # SHUT DOWN MAC
            if any(phrase in user_input for phrase in ["shut down mac", "shutdown mac", "turn off mac"]):
                speak("Are you sure you want to shut down your Mac? Yes or no?")
                c = recognize_speech(5) or ""
                if is_affirmative(c):
                    shutdown_mac()
                else:
                    speak("Shutdown cancelled.")
                continue

            # Environment Queries
            if "temperature" in user_input or "temp" in user_input:
                response = answer_temperature_query()
                print(f"🤖 JARVIS: {response}")
                speak(response)
                continue
            if "humidity" in user_input:
                response = answer_humidity_query()
                print(f"🤖 JARVIS: {response}")
                speak(response)
                continue

            # Real-time search or GPT
            if any(keyword in user_input for keyword in ["news", "update", "latest", "who","what", "where", "how"]):
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
    print("🔊 Starting JARVIS with macOS Contacts integration, hardware integration, and dateparser.")
    # Start a background thread to watch hardware_data.json for button events
    watch_thread = threading.Thread(target=watch_hardware_data, daemon=True)
    watch_thread.start()

    try:
        detect_wake_word()
    except KeyboardInterrupt:
        print("\n🛑 JARVIS: Shutting down...")
        cleanup()
        exit()

