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
    46: ("fan", "Hommyn ventilation / Electrolux Air Gate"),
    55: ("climate", "Zanussi Barocco DC Inverter"),
    69: ("fan", "Hommyn CO2 breezer"),
    82: ("climate", "Goldstar GSAC"),
}

CLIMATE_TYPES = {t for t, (p, _) in DEVICE_TYPES.items() if p == "climate"}
FAN_TYPES = {t for t, (p, _) in DEVICE_TYPES.items() if p == "fan"}

# Device types that expose useful measurement sensors (CO2 / filter / etc.)
# in addition to their primary platform. Ventilation (46) and breezer (69)
# publish sensor/co2, sensor/temperature, expendables, diag/rssi.
SENSOR_TYPES = {46, 69}

# Device types with a heating element controlled by a temperature setpoint
# (exposed as a number entity).
#   69 breezer       -> verified 5..25 C
#   46 air curtain   -> verified 5..35 C (Electrolux Air Gate)
HEAT_TYPES = {46, 69}

# Per-type fan speed maximum (number of discrete manual steps).
#   69 breezer     -> 1..7
#   46 air curtain -> 1..10
SPEED_MAX_BY_TYPE: dict[int, int] = {46: 10, 69: 7}
DEFAULT_SPEED_MAX = 7

# Per-type heating setpoint range (Celsius).
HEAT_RANGE_BY_TYPE: dict[int, tuple[int, int]] = {46: (5, 35), 69: (5, 25)}
DEFAULT_HEAT_RANGE = (5, 25)

# Device types that expose an "auto" fan preset via mode=4.
# Verified on the breezer (69); the air curtain's extra modes (2/3/4) are
# not yet mapped, so it gets plain on/off + speed for now.
AUTO_PRESET_TYPES = {69}

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

# Per-devtype override of the fan scale. Types not listed here fall back to
# SPEED_TO_FAN above.
#
# devtype 55 (Zanussi Barocco DC Inverter) shows 8 positions in the Hommyn app:
#   AUTO, QUITE, LOW, MID-LOW, MID, MID-HIGH, HIGH, TURBO
# UNVERIFIED: the numeric codes below assume 0..7 in the same order as the app
# dial. If the AC reacts to the wrong speed, this table is what to fix.
SPEED_TO_FAN_BY_TYPE: dict[int, dict[str, str]] = {
    55: {
        "0": "auto",
        "1": "quiet",
        "2": "low",
        "3": "mid_low",
        "4": "medium",
        "5": "mid_high",
        "6": "high",
        "7": "turbo",
    },
}
FAN_TO_SPEED_BY_TYPE: dict[int, dict[str, str]] = {
    devtype: {v: k for k, v in table.items()}
    for devtype, table in SPEED_TO_FAN_BY_TYPE.items()
}

# Climate target-temperature bounds (Celsius).
MIN_TEMP = 16
MAX_TEMP = 30

# Per-devtype override of the upper bound. devtype 55 (Zanussi Barocco DC)
# accepts 31 C in the Hommyn app.
MAX_TEMP_BY_TYPE: dict[int, int] = {55: 31}

# Device types whose louvers can be parked at fixed angles (exposed as two
# select entities in addition to the climate swing on/off).
LOUVER_SELECT_TYPES = {55}

# Device types with display-backlight / buzzer switches.
DISPLAY_SWITCH_TYPES = {55}
SOUND_SWITCH_TYPES = {55}

# Verified on devtype 55: the display backlight lives in `backlight`,
# "true"/"false".
KEY_BACKLIGHT = "backlight"
# Verified on devtype 55: the buzzer lives in state/control `volume`, "1"/"0"
# (unlike `backlight`, not "true"/"false").
KEY_SOUND = "volume"

# Louver control on devtype 55, verified from the AC -> HA stream:
#   program_data/0 — 8-char flag string, "1" at the axis index means "swing"
#   program_data/3 — horizontal louver fixed angle, "01".."05"
#   program_data/4 — vertical louver fixed angle, "01".."05"
LOUVER_ANGLE_FIELD_HORIZONTAL = "program_data/3"
LOUVER_ANGLE_FIELD_VERTICAL = "program_data/4"

LOUVER_OPTION_SWING = "swing"
LOUVER_ANGLES: dict[str, str] = {
    "01": "pos_1",
    "02": "pos_2",
    "03": "pos_3",
    "04": "pos_4",
    "05": "pos_5",
}
LOUVER_ANGLES_REV: dict[str, str] = {v: k for k, v in LOUVER_ANGLES.items()}
LOUVER_OPTIONS: list[str] = [LOUVER_OPTION_SWING, *LOUVER_ANGLES.values()]

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
