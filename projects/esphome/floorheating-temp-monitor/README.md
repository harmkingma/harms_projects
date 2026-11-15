# Dual temperature measurement – ESPHome on the Adafruit ESP32-S2 TFT Feather

> Copied into Harms Projects on 2026-11-07. Use the shared ESPHome launcher below;
> [archive instructions](../../../README.md) supersede historical environment paths.

Two DS18B20 temperature sensors on one Adafruit ESP32-S2 TFT Feather
([product 5300](https://www.adafruit.com/product/5300)). The ESP32-S3 TFT Feather
([5483](https://www.adafruit.com/product/5483)) has the same pins: for that board change
`board:` in `feather-temp.yaml` to `adafruit_feather_esp32s3_tft`. The built-in display shows both
temperatures (refreshed every second, sensors read every 5 s). The values are also available:

- in any browser on your network: `http://feather-temp.local`
- in Home Assistant over Wi-Fi, whenever you decide to add it (no USB connection to the
  Home Assistant server is needed, ever)

All setup is done from a Windows laptop.

| File | What it is |
|---|---|
| [feather-temp.yaml](feather-temp.yaml) | ESPHome configuration (the "firmware recipe") |
| [esphome.cmd](esphome.cmd) | Runs ESPHome with the right settings, no venv activation needed (step 5) |
| [secrets.yaml.example](secrets.yaml.example) | Template for your Wi-Fi password and encryption key |
| [wiring_diagram.png](wiring_diagram.png) | Picture showing exactly how to connect everything |
| [tools/make_wiring_diagram.py](tools/make_wiring_diagram.py) | Script that draws the wiring picture |
| [tools/make_ca_bundle.py](tools/make_ca_bundle.py) | Fix for downloads on company networks with SSL inspection (step 3) |
| [shared ESPHome dependencies](../../../dependencies/esphome.txt) | One distribution for all devices |
| [enclosure](../../hardware/floorheating-temp-monitor) | 3D-printable housing: FreeCAD model, generator script, STL/STEP files |

---

## 1. What you need

| Item | Notes |
|---|---|
| Adafruit ESP32-S2 TFT Feather | 4 MB flash / 2 MB PSRAM (the chip name is printed on the metal can on the back) |
| 2 × DS18B20 | bare 3-leg TO-92 package (dry environment) |
| 1 × 4.7 kΩ resistor | colour bands yellow – violet – red – gold. One resistor for both sensors |
| Stranded hook-up wire (red, black, yellow) | e.g. 0.14–0.25 mm² (AWG 26–24) |
| Heat-shrink tubing | ~1.6 mm for the sensor legs, ~3–4.8 mm for the splices and the resistor |
| Soldering iron + solder | |
| USB-C **data** cable | some cheap cables only charge – use one that you know transfers data |
| Windows laptop | Python 3.11 or newer, on the same **2.4 GHz** Wi-Fi network the board will use |

Solder the three wires from the Feather directly into the holes marked **3V**, **GND** and
**A0** (or solder the supplied header strip and use female jumper wires).

---

## 2. Wiring

![Wiring diagram](wiring_diagram.png)

Unplug the USB cable while wiring. There are three **soldered splices** – every wire in one
row is soldered together and the joint is covered with heat-shrink:

| Splice | Feather pin | Sensor 1 | Sensor 2 | 4.7 kΩ resistor |
|---|---|---|---|---|
| **3.3 V** (red) | `3V` (either of the two) | VDD (pin 3) | VDD (pin 3) | one leg |
| **DATA** (yellow) | `A0` (= GPIO18) | DQ (pin 2) | DQ (pin 2) | other leg |
| **GND** (black) | `GND` | GND (pin 1) | GND (pin 1) | – |

- DS18B20 pinout: hold it with the **flat side with text towards you, legs down**. From
  left to right the legs are **1 = GND, 2 = DQ (data), 3 = VDD**.
- Sensor legs: slide a short piece of heat-shrink over each wire **before** soldering, solder
  the wire to the leg, then shrink the tube over the joint so the three legs cannot touch.
- Splices: slide heat-shrink over one wire first, twist the wires together, solder, then
  shrink. The resistor legs go into the 3.3 V and DATA splices; cover the resistor with a
  piece of heat-shrink as well.
- **Never** connect the sensors to the `USB` or `BAT` pin (5 V / battery voltage).
- If you swap VDD and GND on a DS18B20 it gets very hot within seconds. Unplug immediately
  if a sensor feels hot.

---

## 3. Install ESPHome on the laptop (one time)

Open **PowerShell** in this device folder and run:

```powershell
..\..\..\tools\setup.cmd esphome
.\esphome.cmd version             # ESPHome 2026.10.2
```

All devices use the archive's `.venvs\esphome`; do not create a local `.venv`.
Use `.\esphome.cmd` wherever the later instructions say `esphome`. No activation,
execution-policy change or VS Code restart is required.

**Avoid the Windows 260-character path limit.** The ESP32 compiler lives in very deep folders.
The shared launcher defaults `ESPHOME_ESP_IDF_PREFIX` to `C:\esphome-idf` and
respects an existing override.

**Company network with SSL inspection** (downloads fail with `CERTIFICATE_VERIFY_FAILED`):
the download tools use their own certificate list, which does not contain the company's
proxy certificate. Windows does have it, so build one combined list and point the tools at it:

```powershell
..\..\..\.venvs\esphome\Scripts\python.exe tools\make_ca_bundle.py
```

The launcher reads the resulting user certificate bundle automatically.
Re-run the script if the company renews its certificates.

---

## 4. Enter your Wi-Fi details and create a key

1. Copy `secrets.yaml.example` to `secrets.yaml` (same folder).
2. Generate an encryption key:

   ```powershell
   python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"
   ```

3. Open `secrets.yaml` and fill in your Wi-Fi name, Wi-Fi password, the key you just
   generated and a password for the fallback hotspot. **Keep this file private** – it is
   git-ignored and must never be committed. You need the same key later for Home Assistant.

---

## 5. Check and build the firmware

```powershell
esphome config feather-temp.yaml     # checks the file, ends with "Configuration is valid!"
esphome compile feather-temp.yaml    # first run downloads ~1 GB of tools: 10-20 minutes
```

Only the first compile is slow; later builds take about a minute.

**Easiest way on a company laptop:** use the wrapper `.\esphome.cmd` in this folder instead of
`esphome`, e.g. `.\esphome.cmd compile feather-temp.yaml`. It sets the short toolchain path and
the certificate bundle (step 3) itself, so it works without activating the venv and without
restarting VS Code. All other commands work the same way (`.\esphome.cmd upload ...`,
`.\esphome.cmd logs ...`).

> The download needs internet access. On a company network with SSL inspection, set up the
> certificate bundle from step 3 first (or use your home network).

---

## 6. First upload over USB

The very first time, the board must be put in **flash mode** by hand:

1. Plug the USB-C cable into the board and the laptop.
2. On the board, **hold the `Boot` button**, **tap `Rst`**, then **release `Boot`**.
   The display goes dark – that is expected.
3. Find the COM port: *Device Manager → Ports (COM & LPT)* shows a new port, e.g.
   `USB Serial Device (COM7)` or `USB JTAG/serial debug unit (COM7)`.
4. Upload:

   ```powershell
   esphome upload feather-temp.yaml --device COM7
   ```

5. When the upload is finished, **tap `Rst`** once. The display should light up and show
   `Sensor 1` / `Sensor 2` with temperatures (or `--.-` for a few seconds at start-up).

---

## 7. Check the log and fix the sensor order

```powershell
esphome logs feather-temp.yaml --device COM7
```

In the log you should see:

- the board joining Wi-Fi and its **IP address** (write it down);
- the 1-Wire bus listing **two devices**, each with an address like `0x1c0000031edd2a28`;
- temperature readings every 5 seconds.

Press `Ctrl+C` to stop the log.

By default the sensors are ordered by address (`index: 0` / `index: 1`). That order can change
if you ever replace a sensor, so pin them down:

1. Hold **one** sensor between your fingers and watch which value rises (in the log or on the display).
2. In `feather-temp.yaml`, for each sensor replace the `index:` line with the matching
   `address:` line, for example:

   ```yaml
     - platform: dallas_temp
       id: temp_1
       name: "Temperature 1"
       address: 0x1c0000031edd2a28
       update_interval: 5s
   ```

3. Optionally rename `"Temperature 1"` / `"Temperature 2"` (e.g. `"Boiler supply"`) and the
   labels `"Sensor 1"` / `"Sensor 2"` in the `display:` lambda.

---

## 8. Later updates go over Wi-Fi

From now on the USB cable is only needed for power:

```powershell
esphome run feather-temp.yaml --device feather-temp.local
# or with the IP address from the log:
esphome run feather-temp.yaml --device 192.168.1.50
```

`esphome run` compiles, uploads wirelessly and then shows the log.

Prefer clicking over typing? `esphome dashboard .` starts the same web interface Home
Assistant uses, at `http://localhost:6052`.

---

## 9. See the values without Home Assistant

- **On the display** – updated every second.
- **In a browser** – `http://feather-temp.local` (or `http://<ip-address>`). The page shows
  both temperatures and lets you dim the display backlight.

The device does **not** need Home Assistant to work. `api: reboot_timeout: 0s` in the YAML stops
it from rebooting every 15 minutes while no Home Assistant is connected.

---

## 10. Add it to Home Assistant (whenever you like, over Wi-Fi)

1. Make sure Home Assistant and the board are on the same network.
2. In Home Assistant: **Settings → Devices & services**. The device usually appears under
   *Discovered* as **Feather Temp** → **Configure**. If not: **Add integration → ESPHome**
   and enter `feather-temp.local` or the IP address.
3. Enter the **encryption key** from your `secrets.yaml`.
4. You get `Temperature 1`, `Temperature 2` and `Display Backlight` entities, ready for
   dashboards, history graphs and automations.

You can keep using the laptop for updates (step 8). If you later want to manage the device
from the ESPHome Device Builder add-on in Home Assistant instead, copy `feather-temp.yaml` into
it and add `api_key`, `wifi_ssid` and `wifi_password` to the add-on's own *Secrets*. Updates
from there also go over Wi-Fi.

---

## 11. Enclosure (3D print)

The files are in [enclosure/](enclosure/):

- `FeatherEnclosure.FCStd` – the FreeCAD model (Box, Lid, ButtonCap_Reset, ButtonCap_Boot
  and the Adafruit board model for reference).
- `print/*.stl` – ready to print and already lying flat in the right orientation.
- `print/FeatherEnclosure_parts.step` – the same parts in STEP format.
- `make_enclosure.py` – the script that generates everything. Change a parameter at the top
  and run it in FreeCAD (*Macro → Macros… → Execute*).

Outer size: 67.2 × 26.7 × 16.1 mm.

**Printing (Bambu Lab X1 Carbon)**

| Part | Orientation | Settings |
|---|---|---|
| Box | front face (display window) on the plate | 0.2 mm layers, no supports |
| Lid | outside face on the plate | 0.2 mm layers, no supports |
| 2 × button cap | small knob on the plate | 0.12 mm layers, 100 % infill; add a brim if they come loose |

PLA or PETG both work. PETG makes the snap tabs on the lid more forgiving.

**Assembly**

1. Drop the two button caps into the button holes from the inside, knob first. The cone
   centres them in the hole.
2. Place the board display-down into the box, USB-C towards the opening. The two pegs at
   the USB end go into the board's mounting holes. Once the board is in, the caps can no
   longer fall out.
3. Fix the board with a few dots of hot glue on the support ledges at both ends.
4. Lay the resistor in the groove of the cradle in the wire bay and add a dot of hot glue.
   Run the three sensor wires out through the slot in the end wall. A drop of glue on the
   inside works as strain relief.
5. Press the lid on until the four tabs click. To open it again, put a flat screwdriver in
   the notch on the long side and lever gently.

The front panel has engraved **R** (Reset) and **B** (Boot) labels at the holes. Press the caps with a
fingernail: Boot + Rst puts the board in flash mode, exactly as in step 6.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| No new COM port appears | Charge-only USB cable, or the board is not in flash mode (repeat step 6.2). Try another USB port. |
| Upload fails half-way | Put the board in flash mode again (step 6.2) and retry. |
| `This chip is ESP32-S2, not ESP32-S3` (or the other way round) | Wrong `board:` in `feather-temp.yaml` – see the top of this README, then compile again. |
| `Could not open COMxx ... Access is denied` | Another program (serial monitor, a second `esphome logs`) has the port open, or the port number changed. Close it, put the board in flash mode again (step 6.2) and check the port in Device Manager. |
| Display stays dark after upload | Tap `Rst`. Check that `enable_pin: GPIO21` is in the YAML (it powers the display). |
| Display colours wrong (red/blue swapped) | Uncomment `color_order: rgb` in the `display:` section. |
| Picture shifted / garbage at one edge | Adjust `offset_width` / `offset_height` in the `display:` section. |
| Shows `--.-` or log says *found 0 devices* | Check the 4.7 kΩ resistor between 3.3 V and DATA, and the three connections. |
| Only one sensor found | That sensor's DQ or VDD joint is not soldered properly. |
| A reading of exactly **85.0 °C** | The sensor reset during a reading: bad solder joint on VDD or GND. |
| `feather-temp.local` does not open | Use the IP address from the log or from your router. |
| Compile error `bits/c++config.h: No such file` or `cannot execute 'as'` | Windows path-length limit: set `ESPHOME_ESP_IDF_PREFIX` (step 3), **restart VS Code / PowerShell**, check `$env:ESPHOME_ESP_IDF_PREFIX`, delete `%LOCALAPPDATA%\esphome\Cache\idf` and compile again. Or, in an **admin** PowerShell: `Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' LongPathsEnabled 1` and reboot. |
| `CERTIFICATE_VERIFY_FAILED` during the first compile | Company SSL inspection: create the certificate bundle (step 3), restart VS Code / PowerShell, compile again. Or use another network. |
| Board does not join Wi-Fi | It opens its own hotspot **Feather-Temp** (password = `ap_password`). Connect a phone to it and enter the Wi-Fi details. The ESP32 only supports 2.4 GHz. |

---

## Pin reference (used by the YAML)

| Function | GPIO | Board label |
|---|---|---|
| 1-Wire data (both DS18B20) | GPIO18 | `A0` |
| TFT chip select / DC / reset | GPIO7 / GPIO39 / GPIO40 | – (on board) |
| TFT backlight | GPIO45 | – (on board) |
| TFT + I²C power enable | GPIO21 | – (on board) |
| SPI clock / data | GPIO36 / GPIO35 | `SCK` / `MO` |

Regenerate the wiring picture after editing the script:
`.\.venv\Scripts\python.exe tools\make_wiring_diagram.py`.

Sources: Adafruit ESP32-S2 / ESP32-S3 TFT Feather guides and PrettyPins pinouts; CircuitPython
board definitions `adafruit_feather_esp32s2_tft` / `_esp32s3_tft`; esphome.io documentation for
`mipi_spi`, `one_wire`, `dallas_temp`, `api`, `ota` and `logger` (ESPHome 2026.10).
