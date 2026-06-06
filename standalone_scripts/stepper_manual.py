import sys
import termios
import time
import tty

from gpiozero import OutputDevice

# --- Configuration ---
STEP_PIN = 17
DIR_PIN = 27
SPEED = 0.002 # Seconds per step half-cycle

# --- Setup ---
step = OutputDevice(STEP_PIN)
direction = OutputDevice(DIR_PIN)

def getch():
    """Reads a single character from stdin."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def move_stepper(forward=True, steps=100):
    """Moves the stepper in a specific direction."""
    if forward:
        direction.on()
    else:
        direction.off()

    print(f"  {'Moving Forward' if forward else 'Moving Backward'} ({steps} steps)...")
    for _ in range(steps):
        step.on()
        time.sleep(SPEED)
        step.off()
        time.sleep(SPEED)

print("\n🚀 Stepper Manual Controller")
print("----------------------------")
print("Use Arrow Keys to move:")
print("  [UP]    - Move Forward")
print("  [DOWN]  - Move Backward")
print("  [Q]     - Quit")
print("\n(Press a key...)\n")

try:
    while True:
        char = getch()

        if char == 'q' or char == '\x03': # q or Ctrl+C
            break

        # Arrow keys are escape sequences: \x1b[A, \x1b[B, etc.
        if char == '\x1b':
            # Read the next two characters
            next1 = getch()
            next2 = getch()
            if next1 == '[':
                if next2 == 'A': # Up Arrow
                    move_stepper(forward=True, steps=200)
                elif next2 == 'B': # Down Arrow
                    move_stepper(forward=False, steps=200)

except KeyboardInterrupt:
    pass
finally:
    print("\nStopping...")
    step.off()
    direction.off()
