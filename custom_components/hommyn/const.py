"""Constants for the Hommyn Cloud integration."""
from __future__ import annotations

DOMAIN = "hommyn"

# --- Cloud broker ---
# Values pulled from the Hommyn Android app (com.hommyn.app v1.18.3,
# HommynVendor.java) and confirmed against the live broker.
CLOUD_HOST = "mqtt.cloud.rusklimat.ru"
CLOUD_PORT = 8883
APP_USERNAME = "rusclimate_app"
APP_PASSWORD = "42fb1234ee9d1e4b"  # noqa: S105 — public constant, baked into APK

# Each Hommyn app session uses a 40-char clientId formatted as
# "Android " + uuid4().hex.lower(). Anything else gets CONNACK rc=2.
CLIENT_ID_PREFIX = "Android "

# --- Device taxonomy ---
# devtype -> (platform, friendly model family).
# Numbers correspond to the second segment of the MQTT topic:
#   rusclimate/{devtype}/{token}/...
DEVICE_TYPES: dict[int, tuple[str, str]] = {
    8: ("climate", "Electrolux Atrium / Zanussi Siena / Ballu Lagoon"),
    13: ("climate", "Ballu Ice Peak / Electrolux Smartline / Ballu Eco Smart"),
    15: ("climate", "Electrolux Viking / Zanussi Perfecto / Ballu Greenland"),
    20: ("climate", "Ballu Platinum Evol / Olympio Legend"),
    46: ("fan", "Hommyn ventilation"),
    69: ("fan", "Hommyn CO2 breezer"),
    82: ("climate", "Goldstar GSAC"),
}

CLIMATE_TYPES = {t for t, (p, _) in DEVICE_TYPES.items() if p == "climate"}
FAN_TYPES = {t for t, (p, _) in DEVICE_TYPES.items() if p == "fan"}

# --- HVAC mapping (used by climate.py) ---
# State value (string) -> Home Assistant HVAC mode
MODE_TO_HVAC: dict[str, str] = {
    "0": "off",
    "1": "auto",
    "2": "cool",
    "3": "dry",
    "4": "heat",
    "5": "fan_only",
}
HVAC_TO_MODE: dict[str, str] = {v: k for k, v in MODE_TO_HVAC.items()}

# Generic split-AC fan-mode scale (0=auto, 1..5).
# Some sub-families collapse to fewer steps, but reporting more is harmless
# (the device clamps anyway).
SPEED_TO_FAN: dict[str, str] = {
    "0": "auto",
    "1": "low",
    "2": "medium",
    "3": "high",
    "4": "turbo",
    "5": "max",
}
FAN_TO_SPEED: dict[str, str] = {v: k for k, v in SPEED_TO_FAN.items()}

# Climate target-temperature bounds (Celsius).
MIN_TEMP = 16
MAX_TEMP = 30

# --- Swing ---
# The louver state lives in `program_data/0`, an 8-char string where:
#   index 1 -> vertical louver   ('0' = off, '1' = swing, '2'..'6' = fixed angle)
#   index 3 -> horizontal louver ('0' = off, '1' = swing, '2'..'6' = fixed angle)
# We only expose on/off swing here; fixed angles (program_data/3, /4) are TODO.
SWING_FIELD = "program_data/0"
SWING_IDX_VERTICAL = 1
SWING_IDX_HORIZONTAL = 3
SWING_DEFAULT = "00000000"

# --- Config entry keys ---
CONF_DEVICES = "devices"
CONF_DEVICE_TYPE = "device_type"
CONF_DEVICE_TOKEN = "device_token"
CONF_DEVICE_MAC = "device_mac"
CONF_DEVICE_NAME = "device_name"
CONF_DEVICE_MODEL = "device_model"
CONF_SHARE_LINK = "share_link"

# --- Dispatcher signals ---
SIGNAL_STATE_UPDATE = "hommyn_state_{token}"
SIGNAL_AVAILABILITY = "hommyn_availability_{token}"
