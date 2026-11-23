# Harms Projects

Private project archive, copied on 2026-11-07. No source files were moved.
Open [harms_projects.code-workspace](harms_projects.code-workspace) in VS Code.

## Project map

| Area | Location |
| --- | --- |
| Water meter Python library, tests, calibration, add-on, data, tools | [projects/espcam-water](projects/espcam-water) |
| Water meter firmware + board-test firmware | [projects/esphome/espcam-water](projects/esphome/espcam-water) |
| Dual-temperature firmware, wiring diagram, supporting tools/photos | [projects/esphome/floorheating-temp-monitor](projects/esphome/floorheating-temp-monitor) |
| Seven imported HA automations + water-meter packages/dashboard | [projects/home-assistant](projects/home-assistant) |
| Home battery / fixed vs dynamic contract analysis (HA package, dashboard, Energy Analyzer add-on) | [projects/home-assistant/home_battery](projects/home-assistant/home_battery) |
| Daikin Altherma hybrid heat pump monitor via P1P2MQTT (package, dashboard, curve tuning, entity inventory) | [projects/home-assistant/heatpump_monitor](projects/home-assistant/heatpump_monitor) |
| Camera holder and presence box CAD/STL/STEP | [projects/hardware/espcam-water](projects/hardware/espcam-water) |
| Dual-temperature enclosure, print files and board reference | [projects/hardware/floorheating-temp-monitor](projects/hardware/floorheating-temp-monitor) |
| Future schematic/PCB designs | [projects/electronics](projects/electronics) |
| Reusable libraries/packages | [libraries](libraries) |

Use one folder per new device, automation/integration, CAD design or electronics
design. The water meter spans several areas; its Python/add-on project references
the firmware, HA and hardware projects above rather than maintaining duplicates.

## Shared dependencies

Install `uv` and Python 3.12/3.13, then run from this archive in PowerShell:

```powershell
.\tools\setup.cmd esphome
.\tools\setup.cmd watermeter
# Optional, only when running the HA package's integration tests:
.\tools\setup.cmd home-assistant
# Optional, only when regenerating wiring diagrams:
.\tools\setup.cmd cad-tools
```

The CMD launchers work from PowerShell even when PowerShell script execution
is disabled. No execution-policy change is needed.

There is **one active ESPHome installation** at `.venvs\esphome`, version
2026.10.2, for all devices. Different devices still need separate firmware builds.
ESPHome's ESP-IDF toolchain uses the existing short `C:\esphome-idf` location.
Override `ESPHOME_ESP_IDF_PREFIX` if necessary. The setup/launchers respect the
existing user CA bundle without disabling certificate verification.

CV uses Python 3.13 and a separate shared environment because its MQTT client
requires 2.x while this ESPHome version requires 1.x. Home Assistant's test
harness has its own environment and existing dependency overrides.
FreeCAD uses its own Python; run the CAD generators through FreeCAD/FreeCADCmd,
not ordinary Python.

The ESPHome and CV Windows dependency locks were captured from the working
source environments. Update the central declarations/locks deliberately, then
validate every affected project. Do not create an ESPHome venv per device.
The existing CV and HA manifests remain the authoritative project declarations;
central profiles reference them. CAD plotting dependencies are separately pinned.
The watermeter profile also installs the existing `watermeter` library editable
from its new `pyproject.toml`; other projects can import the same source.
HA/CAD profiles also have Windows locks captured from the resolved archive
environments. All four shared environments have been created successfully.

## Commands

```powershell
.\tools\esphome.cmd config .\projects\esphome\espcam-water\espcam-water.yaml
.\tools\esphome.cmd config .\projects\esphome\floorheating-temp-monitor\feather-temp.yaml
.\tools\esphome.cmd run .\projects\esphome\espcam-water\espcam-water.yaml --device espcam-water.local
.\tools\esphome.cmd run .\projects\esphome\floorheating-temp-monitor\feather-temp.yaml --device COM49
# New devices can use the generic shared launcher:
.\tools\esphome.cmd config .\projects\esphome\MY_DEVICE\device.yaml

Push-Location .\projects\espcam-water\cv
try { & ..\..\..\.venvs\watermeter\Scripts\python.exe -m pytest -q }
finally { Pop-Location }

& .\.venvs\watermeter\Scripts\python.exe .\projects\espcam-water\tools\stage_addon.py
```

Run the original relative-path capture/data-analysis commands from
`projects\espcam-water`. The old water-meter update batch file and dual-temperature
ESPHome launcher now forward to the central environment.
The original water-meter PLAN and dual-temperature README contain historical
paths/setup commands; the archive instructions here supersede those sections.

## Home Assistant

Each automation folder keeps its original `packages` and dashboard layout.
Copy only the packages you intend to enable into HA's configured packages
directory and add dashboards separately. Review entity IDs and helper names
before deployment. In particular, `ev_chargin_old.yaml` is a historical package:
do not deploy it alongside `ev_charging.yaml`. Preserved notes are not HA config.
No HA deployment or device flashing was performed during migration.

## Chats and local preservation

Both chats are in [chats](chats): full importable JSON, readable Markdown and
unchanged original JSONL operation logs. Open this workspace, run **Chat: Import
Chat...**, and select the corresponding JSON to continue. Importing does not
restore old edit checkpoints or remap historical file references; tell the agent
to use this README's project map and not to edit `C:\github\espcam`.

`local\source-snapshots\espcam` is a byte-for-byte copy of the **complete** old
workspace, including original venvs, build caches, staged add-on, datasets,
secrets and logs. These are preservation snapshots, not active environments.
The older dual-temperature project has a portable snapshot alongside it.
`local\copy-manifest.csv` records source/destination SHA-256 values.

Secrets, chats, data, snapshots, logs, venvs and build outputs are Git-ignored.
They remain on disk but will **not** travel with a Git clone; back them up
separately in a secure location. CAD generator scripts and reference inputs are
retained in Git; rebuildable FreeCAD documents, STL/STEP exports and generated
wiring previews are excluded.
No commit or push was made. Review staged content for secrets before publishing.

See [migration report](docs/MIGRATION.md) for provenance and verification.
