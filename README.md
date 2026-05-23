# Hommyn Cloud (Rusklimat) — Home Assistant integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Управление кондиционерами и вентиляцией **Ballu / Electrolux / Zanussi / Royal Thermo / Hommyn** (платформа Rusklimat) из Home Assistant — без локального брокера, без перепайки, без рутования телефона.

Интеграция подключается к официальному облаку `mqtt.cloud.rusklimat.ru` под учётной записью мобильного приложения, поэтому **работает параллельно с приложением Hommyn** (никто никого не отключает).

> *English version is below.*

---

## Поддерживаемые устройства

| `devtype` | Семейство |
|---|---|
| 8  | Electrolux Atrium / Zanussi Siena / Ballu Lagoon |
| 13 | **Ballu Ice Peak / Electrolux Smartline / Ballu Eco Smart** (основной target) |
| 15 | Electrolux Viking / Zanussi Perfecto / Ballu Greenland |
| 20 | Ballu Platinum Evol / Olympio Legend |
| 46 | Hommyn вентиляция |
| 69 | Hommyn CO₂-бризер |
| 82 | Goldstar GSAC |

Полевые испытания пока проведены только на `devtype 13`. Остальные модели используют тот же MQTT-протокол, но могут иметь нюансы — заводите [issue](https://github.com/alimp01/hass-hommyn/issues) с моделью устройства и логами.

## Что появится в HA

Для split-кондиционеров — entity `climate.<имя>` с:

- режимами `off / auto / cool / dry / heat / fan_only`
- скоростями вентилятора `auto / low / medium / high / turbo`
- направлением обдува (swing): `off / vertical / horizontal / both`
- целевой и текущей температурой (комнатный датчик внутреннего блока)

Для бризеров / вентиляции — entity `fan.<имя>`:

- **7 ступеней скорости** (ручной режим)
- пресет **«auto»** (устройство само управляет скоростью)
- вкл/выкл

плюс отдельные сущности:
- `number.*_heating_setpoint` — **подогрев** (уставка 5–25 °C)
- `sensor.*_co2` — **CO₂**, ppm
- `sensor.*_air_temperature` — температура воздуха
- `sensor.*_filter_life` — ресурс фильтра, %
- `sensor.*_wifi_signal` — сигнал WiFi (диагностика)

Все entity сгруппированы в HA-устройство с правильными MAC, моделью и производителем.

## Установка

### Через HACS (рекомендуется)

1. Откройте **HACS → Integrations → ⋮ → Custom repositories**.
2. Repository: `https://github.com/alimp01/hass-hommyn` — Type: **Integration** — **Add**.
3. Найдите *Hommyn Cloud (Rusklimat)* в списке и нажмите **Download**.
4. Перезапустите Home Assistant.

### Вручную

1. Склонируйте репозиторий или скачайте ZIP.
2. Скопируйте папку `custom_components/hommyn` в `<config>/custom_components/` вашей HA.
3. Перезапустите Home Assistant.

## Настройка

1. **Settings → Devices & Services → Add Integration → Hommyn Cloud**.
2. В мобильном приложении Hommyn:
   1. Откройте кондиционер/бризер.
   2. Меню — **Поделиться устройством** (*Share device*).
   3. Скопируйте ссылку. Она выглядит так:
      ```
      rusklimat://device-share/rusclimate/13/206ef16d0558?token=aa5c45a91f0afd9b7bfcca0da44cad0e&name=Ballu%20Ice%20Peak&attributes_model=ballu_ice_peak_dc
      ```
3. Вставьте ссылку в окне HA и при желании задайте своё имя.
4. Готово — entity появится сразу.

Чтобы добавить второе устройство — повторите шаги 1–4.

## Как это работает (для любопытных)

- В APK Hommyn зашиты `username=rusclimate_app` / `password=42fb1234ee9d1e4b` и формат clientId `Android <uuid.hex>`. Все остальные форматы брокер отбивает с rc=2 (identifier rejected).
- Под этими кредами **ACL брокера** разрешает читать `rusclimate/<type>/<token>/state/#` и публиковать в `rusclimate/<type>/<token>/control/*`. Именно так работает официальное приложение.
- Поскольку у нас уникальный `clientId` (другой UUID для каждой инсталляции HA), мы **не вытесняем настоящий AC** с его сессии. Hommyn-приложение и HA могут работать одновременно.

## Известные ограничения

- Облако `rusklimat.ru` доступно только через интернет — если у вас нет внешней сети, интеграция работать не будет.
- Если устройство **не подключилось к облаку** (например, на роутере включён DNS-перехват `mqtt.cloud.rusklimat.ru`), интеграция будет видеть только последнее *retained*-состояние и не сможет отправлять команды. Уберите DNS-редирект и перезагрузите устройство по питанию.
- Перепайка/сторонний MQTT-broker (Open MQTT режим WF-02) на текущей прошивке требует ECDH-pairing — этой интеграцией не охвачено.

## Troubleshooting

Включите debug-лог:

```yaml
logger:
  default: warning
  logs:
    custom_components.hommyn: debug
```

Состояния (`AC->HA`) и команды (`HA->AC`) видны в Settings → System → Logs.

Если HA не подключается:

- Проверьте интернет и что `mqtt.cloud.rusklimat.ru` резолвится в публичный IP (а не в локальный).
- Проверьте, что устройство активно в Hommyn-приложении (т.е. реально онлайн на облаке).

---

## English

Home Assistant integration for **Ballu / Electrolux / Zanussi / Royal Thermo / Hommyn** climate devices on the Rusklimat IoT platform.

Connects to the official `mqtt.cloud.rusklimat.ru` cloud using app credentials extracted from the Hommyn Android app. Uses a unique client identifier so it **does not kick the device off the cloud** — HA and the Hommyn app can control the device in parallel.

Climate entities expose hvac mode, fan speed, swing (off/vertical/horizontal/both), and target + current temperature.

### Setup

1. Install via HACS as a custom repository: `https://github.com/alimp01/hass-hommyn`, type **Integration**.
2. Restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → Hommyn Cloud**.
4. In the Hommyn mobile app, open your device → **Share device** → copy the `rusklimat://device-share/...` link → paste it into the HA dialog.

### Supported

Split AC `devtype` 8/13/15/20/82, ventilation/breezer 46/69. Only 13 is field-tested; others use the same protocol but may have quirks — please open an issue with your model.

### Limitations

- Requires internet access to `mqtt.cloud.rusklimat.ru`.
- If your router transparently hijacks DNS for `mqtt.cloud.rusklimat.ru`, the device will fall back into a LAN-only mode and HA will only see stale retained state. Remove the DNS override and power-cycle the device.

## License

MIT — see [LICENSE](LICENSE).
