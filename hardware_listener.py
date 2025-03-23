import serial
import subprocess
import time
import json

# Set your Arduino's serial port and baud rate.
SERIAL_PORT = "/dev/cu.usbmodem3101"  # Your port
BAUD_RATE = 115200

# Global dictionary to store the latest data.
latest_data = {
    "volume": None,   # Volume percentage (0-100)
    "dht": None,      # DHT sensor data as a string (e.g., "DHT:T:75F, H:40%")
    "button": None    # Button event (e.g., "BTN:STOP")
}

def set_system_volume(volume):
    """
    Sets the MacBook's system volume to the given percentage using AppleScript.
    """
    script = f"set volume output volume {volume}"
    subprocess.run(["osascript", "-e", script])
    print(f"System volume set to {volume}%")

def process_line(line):
    """
    Process a single line from the Arduino's Serial output.
    Expected messages include:
      - "VOL:xx" for volume updates
      - "BTN:..." for button events
      - "DHT:..." for sensor data
    """
    global latest_data
    line = line.strip()
    print("Received:", line)
    if line.startswith("VOL:"):
        try:
            volume = int(line.split(":")[1])
            latest_data["volume"] = volume
            set_system_volume(volume)
        except ValueError:
            print("Error parsing volume from:", line)
    elif line.startswith("BTN:"):
        latest_data["button"] = line
        print("Button event received:", line)
    elif line.startswith("DHT:"):
        latest_data["dht"] = line
        print("DHT data received:", line)
    else:
        print("Other message:", line)
    
    # Write the updated latest_data to a JSON file.
    try:
        with open("hardware_data.json", "w") as f:
            json.dump(latest_data, f)
    except Exception as e:
        print("Error writing hardware_data.json:", e)

def serial_listener():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    except Exception as e:
        print("Error opening serial port:", e)
        return
    time.sleep(2)  # Wait for the Arduino to initialize.
    print("Serial listener running on", SERIAL_PORT)
    
    while True:
        if ser.in_waiting > 0:
            try:
                line = ser.readline().decode("utf-8")
                process_line(line)
            except Exception as e:
                print("Error reading line:", e)
        time.sleep(0.1)

def main():
    serial_listener()

if __name__ == "__main__":
    main()

