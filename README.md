# CCEI BRiO WiL — Home Assistant Integration

Local control for the **CCEI BRiO WiL** pool light controller in Home Assistant.
No cloud, no vendor app required for day-to-day use — the integration talks to
the controller directly over your LAN.

> **Status:** Community integration, not affiliated with or endorsed by CCEI.
> Developed by reverse-engineering the local protocol of a real device.

---

## Features

- **On / off**
- **Brightness** — the controller's four hardware levels, mapped onto Home
  Assistant's brightness slider
- **11 colours** — Warm White, White, Blue, Lagoon, Cyan, Purple, Magenta,
  Pink, Red, Orange, Green (localised into your Home Assistant language)
- **Favorite** — recall the scene stored on the device (see limitations below)
- **7 sequences** — Gradient, Rainbow, Parade, Techno, Horizon, Hazard, Magical
  (kept as English proper names in every language)
- **Live status** — the light reflects changes made from the vendor app too
- **Fully local** — communication over TCP, no internet dependency

Colours, the favorite and the sequences are all offered through the light's
**effect list**, because the device only supports these fixed choices rather
than free RGB colour.

---

## Requirements

- A CCEI BRiO WiL controller on your network, reachable over TCP port **30302**
- The controller's IP address (a DHCP reservation is strongly recommended so it
  doesn't change)

To find the IP, check your router's client list, or scan for the open port:

```
nmap -p 30302 192.168.0.0/24
```

The host that answers on port 30302 is your controller.

---

## Installation

### Via HACS (recommended)

1. In HACS, open the three-dot menu → **Custom repositories**.
2. Add `https://github.com/chermsen/ha-ccei-brio-wil` as an **Integration**.
3. Search for **CCEI BRiO WiL** in HACS and download it.
4. Restart Home Assistant.

### Manual

1. Copy `custom_components/ccei_brio_wil/` into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.

### Configuration

After restarting: **Settings → Devices & Services → Add Integration →
CCEI BRiO WiL**, then enter the controller's IP address (port 30302 is
pre-filled).

---

## Known limitations

These are honest constraints of the device and its local protocol, not bugs:

- **Setting the favorite colour** is not supported from Home Assistant. The
  favorite is stored *on the device*, but the command to *define* it isn't part
  of the local protocol we could observe. Recalling it works; set it in the
  vendor app.
- **Sequence speed** is not exposed. The vendor `pspd` command does not behave
  as a clean speed control on this hardware — sending it while a sequence runs
  also changes the sequence itself. Rather than ship a control that does the
  wrong thing, speed is intentionally left out. Set it in the vendor app.
- **Single connection at a time.** The controller accepts only one TCP
  connection. While the vendor app is actively connected, Home Assistant's
  polling will fail; the integration tolerates a few consecutive misses and
  holds the last known state before marking the device unavailable.
- **Colour picker.** The device has fixed colours, so they're presented as a
  named effect list rather than a colour wheel.

---

## Protocol notes

For the curious (and for anyone who wants to extend this), the local protocol
was decoded from a real device:

- **Transport:** plain TCP, port 30302. Reading returns a 160-char hex status
  frame; the controller may return several concatenated frames in response to a
  command (the state before and after) — the last complete frame is
  authoritative.
- **Commands** (JSON):
  - `{"sprj":1}` / `{"sprj":0}` — power on / off
  - `{"prcn":N}` — colour / sequence (see codes below)
  - `{"plum":N}` — brightness, `0..3` (Low / Medium / Strong / Maximum)
- **Status frame positions:**
  - char 33 — power (`0` = off, `2` = on)
  - chars 64–65 — colour / mode code (hex)
  - chars 70–71 — level byte: low nibble = brightness (`0/4/8/C`)
- **Colour / mode codes:** `00` Warm White, `01` White, `02` Blue, `03` Lagoon,
  `04` Cyan, `05` Purple, `06` Magenta, `07` Pink, `08` Red, `09` Orange,
  `0A` Green, `0B` Favorite, `10` Gradient, `11` Rainbow, `12` Parade,
  `13` Techno, `14` Horizon, `15` Hazard, `16` Magical.

---

## Translations

The integration ships with English, German, French, Spanish, Italian and Dutch.
The 11 colour names are localised; the sequence names are kept as English proper
names. Contributions of further languages are welcome — add a
`custom_components/ccei_brio_wil/translations/<lang>.json` file modelled on the
existing ones and open a pull request.

---

## Disclaimer

This is an unofficial, community-maintained integration. "CCEI" and "BRiO" are
trademarks of their respective owner. Use at your own risk.

## License

Released under the [MIT License](LICENSE).
