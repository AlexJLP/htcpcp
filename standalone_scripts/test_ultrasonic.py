from time import sleep

from gpiozero import DistanceSensor

# --- CONFIGURATION ---
# Using BCM numbers.
# Physical Pin 36 = BCM 16
# Physical Pin 16 = BCM 23
TRIG_PIN = 16
ECHO_PIN = 23

print(f"🚀 Initializing HC-SR04 (Trig: GPIO {TRIG_PIN}, Echo: GPIO {ECHO_PIN})")

try:
    # Initializing sensor
    sensor = DistanceSensor(echo=ECHO_PIN, trigger=TRIG_PIN, max_distance=2.0)

    print("Reading distance... Press Ctrl+C to stop.\n")

    while True:
        # Distance is returned in meters
        distance_cm = sensor.distance * 100

        # Detection logic
        mug_present = "YES" if distance_cm < 10 else "NO"

        print(f"Distance: {distance_cm:5.1f} cm | Mug Present: {mug_present}", end="\r")
        sleep(0.1)

except KeyboardInterrupt:
    print("\n\nStopping test.")
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nTroubleshooting tips:")
    print("1. Ensure you have a 4.7k/10k voltage divider on the Echo pin.")
    print("2. Check that the sensor is powered by 5V (but Echo signal is 3.3V).")
    print("3. Verify your GPIO numbers (BCM vs Physical).")
