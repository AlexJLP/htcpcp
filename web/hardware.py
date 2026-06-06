import asyncio
import glob
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

import structlog
import yaml

# Try to import hardware-specific libs, fallback to mock if testing not on pi
try:
    from gpiozero import DistanceSensor, OutputDevice
    from luma.core.interface.serial import i2c
    from luma.core.render import canvas
    from luma.oled.device import ssd1306

    HAS_HARDWARE = True
except (ImportError, RuntimeError):
    HAS_HARDWARE = False

from web.models import CoffeePot, PotStatus

log = structlog.get_logger()


class HardwareController:
    """
    Controller for the physical coffee machine hardware.
    """

    def __init__(self, pot: CoffeePot, use_mock: bool = False):
        self.pot = pot
        self.use_mock = not HAS_HARDWARE or use_mock
        self.executor = ThreadPoolExecutor(max_workers=2)

        # Pins (BCM Numbers)
        self.step_pin_id = 17
        self.dir_pin_id = 27
        self.pump_pin_id = 18

        # Physical Pin 36 = BCM 16
        # Physical Pin 16 = BCM 23
        self.trig_pin = 16
        self.echo_pin = 23

        # Device handles
        self.step_pin = None
        self.dir_pin = None
        self.pump_pin = None
        self.distance_sensor = None
        self.oled = None

        self.temp_file: Optional[str] = None
        self.recipes: dict[str, Any] = {}
        self.calibration: dict[str, float] = {}

        self._load_config()

        if not self.use_mock:
            self._setup_hardware()
        else:
            log.info("hardware.mock_mode_active", pot_id=pot.id)

    def _load_config(self):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            yaml_path = os.path.join(base_dir, "recipes.yaml")
            with open(yaml_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
                self.recipes = config.get("recipes", {})
                self.calibration = config.get(
                    "calibration", {"ml_per_second": 5.0, "steps_per_gram": 100}
                )
            log.info("hardware.config_loaded", recipes=list(self.recipes.keys()))
        except Exception as e:
            log.error("hardware.config_load_failed", error=str(e))

    def _setup_hardware(self):
        """Initialize all physical devices."""
        try:
            self.step_pin = OutputDevice(self.step_pin_id)
            self.dir_pin = OutputDevice(self.dir_pin_id)
            self.pump_pin = OutputDevice(self.pump_pin_id)
            self.dir_pin.on()

            # Mug Detection (HC-SR04)
            self.distance_sensor = DistanceSensor(
                echo=self.echo_pin, trigger=self.trig_pin, max_distance=0.5
            )

            # OLED Display (SSD1306 via I2C)
            serial = i2c(port=1, address=0x3C)
            self.oled = ssd1306(serial)

            # Temp Probe
            os.system("modprobe w1-gpio")
            os.system("modprobe w1-therm")
            base_dir = "/sys/bus/w1/devices/"
            device_folder = glob.glob(base_dir + "28*")[0]
            self.temp_file = device_folder + "/w1_slave"

            log.info("hardware.setup_complete", pins=[17, 18, 23, 24])
        except Exception as e:
            log.error("hardware.setup_failed", error=str(e))
            self.use_mock = True

    def check_mug(self) -> bool:
        """Use HC-SR04 to check if a mug is under the brewer."""
        if self.use_mock or not self.distance_sensor:
            return True
        return self.distance_sensor.distance < 0.10  # 10cm

    def read_temp(self) -> float:
        if self.use_mock:
            if self.pot.status == PotStatus.HEATING_WATER:
                self.pot.temperature = min(95.0, self.pot.temperature + 2.0)
            return self.pot.temperature

        if not self.temp_file:
            return 0.0
        try:
            valid_readings = []
            for _ in range(3):
                with open(self.temp_file, encoding="utf-8") as f:
                    lines = f.readlines()
                if lines and "YES" in lines[0]:
                    equals_pos = lines[1].find("t=")
                    if equals_pos != -1:
                        val = float(lines[1][equals_pos + 2 :]) / 1000.0
                        if 0.0 <= val <= 100.0:
                            valid_readings.append(val)

                time.sleep(0.1)
            return (
                sum(valid_readings) / len(valid_readings)
                if valid_readings
                else self.pot.temperature
            )
        except Exception as e:
            log.error("hardware.read_temp_failed", error=str(e))
            return self.pot.temperature

    async def update_loop(self):
        while True:
            self.pot.temperature = self.read_temp()
            self.pot.mug_present = self.check_mug()
            self._update_display()
            await asyncio.sleep(0.5)

    def _update_display(self):
        if self.use_mock or not self.oled:
            return

        with canvas(self.oled) as draw:
            draw.text((0, 0), "--- HTCPCP POT-1 ---", fill="white")

            status_text = f"STATUS: {self.pot.status.name.replace('_', ' ')}"
            draw.text((0, 15), status_text, fill="white")

            temp_text = f"TEMP: {round(self.pot.temperature, 1)}C"
            mug_text = "MUG: [OK]" if self.pot.mug_present else "MUG: MISSING"
            draw.text((0, 30), temp_text, fill="white")
            draw.text((0, 45), mug_text, fill="white")

            if self.pot.status not in [
                PotStatus.IDLE,
                PotStatus.READY,
                PotStatus.NO_MUG,
            ]:
                draw.rectangle((0, 58, 127, 63), outline="white", fill="black")
                width = int((self.pot.progress / 100.0) * 123)
                draw.rectangle((2, 60, 2 + width, 61), outline="white", fill="white")

    async def run_brew_sequence(self, recipe_name: str = "default"):
        log.info("hardware.run_brew_sequence_called", received_recipe_name=recipe_name)
        if not self.pot.mug_present:
            log.warning("hardware.brew_aborted_no_mug")
            self.pot.status = PotStatus.NO_MUG
            await asyncio.sleep(5)
            self.pot.status = PotStatus.IDLE
            return

        recipe = self.recipes.get(recipe_name, self.recipes.get("default"))
        log.info(
            "hardware.brew_recipe_resolved",
            name=recipe.get("name"),
            target_temp=recipe.get("target_temp"),
        )
        self.pot.current_phase = -1
        self.pot.progress = 0.0
        log.info(
            "hardware.brew_sequence_start", pot_id=self.pot.id, recipe=recipe["name"]
        )

        # 1. Grounds
        self.pot.status = PotStatus.DISPENSING_GROUNDS
        steps = int(
            recipe.get("coffee_grams", 15) * self.calibration.get("steps_per_gram", 100)
        )
        log.info("hardware.dispensing_grounds", steps=steps)
        if self.dir_pin:
            self.dir_pin.off()
        await asyncio.to_thread(self._run_stepper, steps=steps)
        log.info("hardware.dispensing_complete")

        # 2. Heat
        target_temp = recipe.get("target_temp", 92.0)
        self.pot.status = PotStatus.HEATING_WATER
        log.info(
            "hardware.heating_start",
            current_temp=self.pot.temperature,
            target=target_temp,
        )
        while self.pot.temperature < target_temp:
            if not self.pot.mug_present:  # Emergency stop
                log.warning("hardware.brew_aborted_mug_removed")
                self.stop_all()
                self.pot.status = PotStatus.NO_MUG
                return
            log.debug(
                "hardware.heating_progress",
                current=self.pot.temperature,
                target=target_temp,
            )
            await asyncio.sleep(1)
        log.info("hardware.heating_complete", final_temp=self.pot.temperature)

        # 3. Pours
        ml_per_sec = self.calibration.get("ml_per_second", 5.0)
        phases = recipe.get("phases", [])
        total_pour_time = sum(
            (p.get("water_ml", 0) / ml_per_sec) + p.get("pause_seconds", 0)
            for p in phases
        )
        elapsed_time = 0.0

        for i, phase in enumerate(phases):
            self.pot.current_phase = i
            action = phase.get("action", "pour")
            if action == "bloom":
                self.pot.status = PotStatus.BLOOMING
            else:
                self.pot.status = PotStatus.POURING

            if not self.pot.mug_present:
                log.warning("hardware.brew_aborted_mug_removed")
                self.stop_all()
                self.pot.status = PotStatus.NO_MUG
                self.pot.progress = 0.0
                return

            duration = phase.get("water_ml", 0) / ml_per_sec
            log.info(
                "hardware.pump_start",
                action=action,
                ml=phase.get("water_ml"),
                duration=round(duration, 2),
            )
            if self.pump_pin:
                self.pump_pin.on()

            # Smooth progress update during pour
            pour_steps = int(duration * 2)
            for _ in range(pour_steps):
                await asyncio.sleep(0.5)
                elapsed_time += 0.5
                self.pot.progress = min(99.0, (elapsed_time / total_pour_time) * 100)

            if duration % 0.5 > 0:
                await asyncio.sleep(duration % 0.5)
                elapsed_time += duration % 0.5

            if self.pump_pin:
                self.pump_pin.off()
            log.info("hardware.pump_stop")
            self.pot.progress = min(99.0, (elapsed_time / total_pour_time) * 100)

            pause = phase.get("pause_seconds", 0)
            if pause > 0:
                log.info("hardware.pause_start", seconds=pause)
                if action != "bloom":
                    self.pot.status = PotStatus.INFUSING

                pause_steps = int(pause * 2)
                for _ in range(pause_steps):
                    await asyncio.sleep(0.5)
                    elapsed_time += 0.5
                    self.pot.progress = min(
                        99.0, (elapsed_time / total_pour_time) * 100
                    )

                if pause % 0.5 > 0:
                    await asyncio.sleep(pause % 0.5)
                    elapsed_time += pause % 0.5
                self.pot.progress = min(99.0, (elapsed_time / total_pour_time) * 100)

        self.pot.status = PotStatus.READY
        self.pot.progress = 100.0
        self.pot.current_phase = -1
        await asyncio.sleep(10)
        self.pot.status = PotStatus.IDLE

    def stop_all(self):
        if self.pump_pin:
            self.pump_pin.off()
        if self.step_pin:
            self.step_pin.off()

    def _run_stepper(self, steps: int):
        if self.use_mock:
            time.sleep(steps * 0.002)
            return
        for _ in range(steps):
            self.step_pin.on()
            time.sleep(0.002)
            self.step_pin.off()
            time.sleep(0.002)


CONTROLLERS: dict[str, HardwareController] = {}


def get_controller(pot_id: str) -> Optional[HardwareController]:
    return CONTROLLERS.get(pot_id)
