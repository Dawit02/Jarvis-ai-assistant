# 📌 Jarvis AI Assistant – Arduino Hardware Pin Mapping

This document clearly defines the Arduino pins connected to each hardware component in the Jarvis AI assistant project.

| Component                             | Arduino Pin                     |
|---------------------------------------|---------------------------------|
| 🔵 **Blue LED (Listening Mode)**      | **2**                           |
| 🔴 **Red LED (Error Mode)**           | **12**                          |
| 🟡 **Yellow LED (Thinking Mode)**     | **13**                          |
| 📟 **LCD Display (16x2, I²C)**        | SDA (**A4**), SCL (**A5**), Address: `0x27` |
| 🎚️ **Trimpot (Volume Control)**      | **A0** *(Analog Input)*         |
| 🌡️💧 **DHT11 Sensor (Temperature/Humidity)** | **11** *(Digital Pin)*    |
| 🛑 **Stop Button**                    | **8**                           |
| 🔇 **Mute Button**                    | **9**                           |
| ⚙️ **Debug Button**                   | **10**                          |

---

## 🛠️ Technical Notes:

- **LCD** uses the standard I²C pins (A4=SDA, A5=SCL) for Arduino Uno/Nano. Adjust pins if using a different Arduino board.
- **Trimpot** provides an analog value (0–1023) for precise volume control on the Mac.
- **DHT11 sensor** communicates via digital pin 11, compatible with standard DHT libraries.


