# Hommyn Cloud (Rusklimat)

Home Assistant integration for **Hommyn / Rusklimat** smart devices — Ballu, Electrolux, Zanussi, Royal Thermo split air conditioners and Hommyn ventilation / breezers. Works through the existing Hommyn cloud (`mqtt.cloud.rusklimat.ru`), so no rooting, soldering, or third-party broker required.

## Highlights

- **Just paste a share link** from the Hommyn app — that's it.
- **No local broker, no Mosquitto bridge.** Talks directly to Hommyn cloud.
- **Coexists with the official app** — both can control the device at the same time.
- Climate & fan platforms; per-device `unique_id` so HA tracks them properly.

## Supported devices

| `devtype` | Family |
|---|---|
| 8  | Electrolux Atrium / Zanussi Siena / Ballu Lagoon |
| 13 | **Ballu Ice Peak / Electrolux Smartline / Ballu Eco Smart** (primary target) |
| 15 | Electrolux Viking / Zanussi Perfecto / Ballu Greenland |
| 20 | Ballu Platinum Evol / Olympio Legend |
| 46 | Hommyn ventilation |
| 69 | Hommyn CO2 breezer |
| 82 | Goldstar GSAC |

Only `devtype 13` has been tested on real hardware. Others use the same protocol but may have minor quirks — please [open an issue](https://github.com/alimp01/hass-hommyn/issues) with your model.

See the full README in the repository for setup steps and troubleshooting.
