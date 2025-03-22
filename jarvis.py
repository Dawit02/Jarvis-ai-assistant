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
import dateparser  # For natural date/time parsing
import re

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

#############################
# AppleScript to Query Contacts
#############################
def lookup_contact_in_mac_contacts(name: str):
    """
    Try to find a person in the macOS Contacts whose name contains 'name' (case-insensitive).
    If found, return the first phone number of the first matched person. Otherwise return None.
    """
    # AppleScript to find a contact by partial name
    # and return the *value of phone 1* from the first match
    # If none found, we return "NOT FOUND"
    # This is minimal logic—if multiple contacts match, it just picks the first.
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
    # phone_str might be e.g. "(303) 333-1111" or "303.333.1111"
    return phone_str

def speak_phone_number_digits(number_str: str):
    """Read out each digit with spaces, e.g. '3033331111' => '3 0 3 3 3 3 1 1 1 1'."""
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
    """
    Attempts to start a FaceTime call. 
    Launch FaceTime, type the number, press return.
    """
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
    dt = dateparser.parse(user_text, languages=["en"])
    if not dt:
        return None
    return dt.strftime("%B %d, %Y at %I:%M %p")

#############################
# Speech Recognition
#############################
recognizer = sr.Recognizer()
recognizer.pause_threshold = 1.5
recognizer.dynamic_energy_threshold = True

def recognize_speech(phrase_time=30):
    """Capture user voice input with up to phrase_time seconds."""
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
    params = {"q": query, "hl": "en", "gl": "us", "api_key": SERPAPI_KEY}
    try:
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
    """
    1) Extract the name from user_command, e.g. 'message John'
    2) Try to find that in the Mac Contacts. If found => return phone from contact.
    3) Otherwise, treat as phone => remove dashes/spaces => returns digits.
    """
    # e.g. 'message john' => we remove 'message' => 'john'
    # e.g. 'text 303-333-1111' => we remove 'text' => '303-333-1111'
    # e.g. 'call dad' => remove 'call' => 'dad'
    pattern = r"(send message to|message|text|call|facetime|to)\s*"
    cleaned = re.sub(pattern, "", user_command, flags=re.IGNORECASE).strip()

    # 1) See if cleaned is in Mac Contacts
    result = lookup_contact_in_mac_contacts(cleaned)
    if result:
        # e.g. '303-333-1111'
        # Remove non digits
        phone = re.sub(r"\D", "", result)
        return phone if phone else None

    # 2) If not found, assume user gave a phone number. remove non digits
    phone_number = re.sub(r"\D", "", cleaned)
    if phone_number:
        return phone_number
    else:
        return None

def speak_phone_number_digits(number_str: str):
    spaced = " ".join(number_str)
    speak(f"The phone number is {spaced}.")

###################################
# MAIN PROCESS
###################################
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
        user_input = recognize_speech(30) or ""
        if user_input:

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

            # SEND EMAIL
            if "send email" in user_input:
                spelled_email = parse_email_in_one_utterance()
                if not spelled_email:
                    speak("No valid email address was provided. Cancelling.")
                    continue
                speak("What is the subject of your email?")
                subject_line = recognize_speech(30) or "No Subject"

                speak("What would you like the message to say? Take your time.")
                body_content = recognize_speech(30) or ""

                speak(f"You want me to send an email to {spelled_email}, subject {subject_line}, with content: {body_content}. Shall I send it now?")
                confirm = recognize_speech(5) or ""
                if is_affirmative(confirm):
                    send_email_outlook(spelled_email, subject_line, body_content)
                    speak("Email sent.")
                else:
                    speak("Email cancelled.")
                continue

            # REMINDERS
            if any(phrase in user_input for phrase in ["remind me", "add reminder", "set reminder"]):
                speak("What is your reminder about?")
                task_name = recognize_speech(30) or "No Task Provided"

                speak("When should I remind you? For example: 'tomorrow at 5 pm' or 'march 25 at 2 pm'.")
                date_input = recognize_speech(30) or ""
                parsed = parse_natural_datetime(date_input)
                if not parsed:
                    speak("I couldn't parse the date. Cancelling reminder.")
                    continue

                speak(f"Remind you '{task_name}' on {parsed}? Yes or no?")
                c = recognize_speech(5) or ""
                if is_affirmative(c):
                    add_reminder(task_name, parsed)
                    speak(f"Reminder set for {parsed}.")
                else:
                    speak("Reminder creation cancelled.")
                continue

            # CALENDAR EVENT
            if any(phrase in user_input for phrase in ["calendar event", "add event", "create event", "schedule event"]):
                speak("What is the name of your event?")
                event_name = recognize_speech(30) or "Untitled Event"

                speak("When does it start? For example: 'tomorrow at 2 pm' or 'March 29 at 10 am'")
                start_user = recognize_speech(30) or ""
                start_parsed = parse_natural_datetime(start_user)
                if not start_parsed:
                    speak("I couldn't parse the start date. Cancelling.")
                    continue

                speak("When does it end?")
                end_user = recognize_speech(30) or ""
                end_parsed = parse_natural_datetime(end_user)
                if not end_parsed:
                    speak("I couldn't parse the end date. Cancelling.")
                    continue

                speak(f"Create event '{event_name}' from {start_parsed} to {end_parsed}? Yes or no?")
                c = recognize_speech(5) or ""
                if is_affirmative(c):
                    add_calendar_event(event_name, start_parsed, end_parsed)
                    speak(f"Event '{event_name}' added from {start_parsed} to {end_parsed}.")
                else:
                    speak("Event creation cancelled.")
                continue

            # MESSAGES (SINGLE STEP)
            # e.g. "message John" or "text 303-333-3333"
            if any(x in user_input for x in ["message ", "send message to", "text "]):
                phone = parse_contact_or_number(user_input)
                if not phone:
                    speak("Sorry, I couldn't parse the contact or phone number. Cancelling.")
                    continue

                speak_phone_number_digits(phone)
                speak("Is this correct?")
                c = recognize_speech(5) or ""
                if not is_affirmative(c):
                    speak("Message cancelled.")
                    continue

                speak("What is the message content?")
                msg_body = recognize_speech(30) or ""
                speak(f"You want to send '{msg_body}' to that number. Shall I send it now?")
                c = recognize_speech(5) or ""
                if is_affirmative(c):
                    send_imessage(phone, msg_body)
                    speak("Message sent.")
                else:
                    speak("Message cancelled.")
                continue

            # FACETIME (SINGLE STEP)
            # e.g. "call John" or "facetime 303-333-3333"
            if any(x in user_input for x in ["call ", "facetime "]):
                phone = parse_contact_or_number(user_input)
                if not phone:
                    speak("Sorry, I couldn't parse the contact or phone number. Cancelling.")
                    continue

                speak_phone_number_digits(phone)
                speak("Shall I start FaceTime call now?")
                c = recognize_speech(5) or ""
                if is_affirmative(c):
                    facetime_call(phone)
                    speak(f"Calling now...")
                else:
                    speak("Call cancelled.")
                continue

            # "open X in safari"
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
    print("🔊 Starting JARVIS with macOS Contacts integration for messages/calls, phone-digit reading, and dateparser.")
    try:
        detect_wake_word()
    except KeyboardInterrupt:
        print("\n🛑 JARVIS: Shutting down...")
        cleanup()
        exit()

