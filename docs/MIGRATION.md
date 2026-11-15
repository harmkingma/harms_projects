# Migration record: 2026-11-07

## Sources

- Complete workspace: `C:\github\espcam`.
- Preferred automation/device copies:
  `C:\Users\310132174\OneDrive - Philips\Documents\pers\automations`.
- Earlier dual-temperature project/enclosure:
  `C:\github\M2F_firmware_dev\esphome\dual_temperature_measurement`.
- Comparison-only automation folders:
  `C:\github\hk-own-code\dataloggerv2\capsense_simulator v2`.

Only the seven matching automation folders in the comparison-only source were
examined. No capsense/modeling code was imported.

## Comparison

SHA-256 comparisons covered all files, including dashboards, packages,
documentation, test files and dependency manifests.

| Project | Preferred files | Older files | Result |
| --- | ---: | ---: | --- |
| airco_automation | 2 | 2 | All identical |
| bathroom_radiator_automation | 3 | 3 | All identical |
| bathroom_ventilation_automation | 3 | 3 | All identical |
| ev_battery_health | 11 | 11 | All identical |
| ev_charging_automation | 4 | 4 | All identical |
| floor_heating_monitor | 2 | 2 | All identical |
| lighting_automation | 2 | 2 | All identical |
| Dual-temperature device | 3 | 3 matching files | Firmware, secrets, wiring image identical |

The source spells the device folder `flooheating_temp_monitor`. The archive uses
`floorheating-temp-monitor`; firmware/entity names were not changed.
The older project supplied enclosure files, tools, photos and documentation
missing from OneDrive. No differing older automation versions needed retaining.

## Preservation and intentional changes

- 24,342 copies were verified against source and destination SHA-256 values,
  including 157 chat edit-checkpoint files.
- The complete ESPCAM workspace is preserved unchanged in a local-only snapshot.
  It contains all 22,977 original files, including generated environments/caches.
- Active projects have one canonical firmware/HA/CAD/library location.
- Original environments/caches are snapshots only. Shared tooling uses
  `.venvs\esphome`, `.venvs\watermeter`, and optional HA/CAD profiles.
- Existing water-meter and dual-temperature launchers forward to shared ESPHome.
- The existing HA installation/activation wrappers use the shared HA test
  environment. Archive notes update the affected setup documentation.
- The existing `watermeter` package gained installable packaging metadata and
  is installed editable; no Python runtime implementation was duplicated.
- No firmware behavior, HA entity naming, CAD geometry or CV algorithm changed.
- Two original chat logs were copied unchanged. Replayed JSON exports preserve
  all 55 water-meter turns and all 4 housing-design turns, including tool records.
  The array push/splice replay follows VS Code's `objectMutationLog` format.
  Native import accepts an object containing `requests` and `responderUsername`.
- No sources were moved, edited or deleted. No Git commit, push, HA deployment
  or device flashing was requested/performed.

Local preservation files are intentionally ignored by Git; protect their backups.

## Final verification

| Check | Result |
| --- | --- |
| Source hashes and complete snapshot file set | All unchanged/intact |
| Shared ESPHome version | 2026.10.2 |
| Water-meter + board-test + dual-temperature config validation | All 3 passed |
| Production water-meter and dual-temperature firmware compilation | Both passed |
| Water-meter regression tests after editable installation | 39 passed |
| Home Assistant battery-health regression tests | 15 passed |
| Home Assistant package/dashboard YAML parsing | All 19 files passed |
| ESPHome and watermeter dependency compatibility | Passed |
| Shared HA/CAD locked installation and HA activation wrapper | Passed |
| Native chat JSON shape, URI components and turn counts | Both passed |
| Readable transcripts | 434 water-meter / 22 housing assistant Markdown parts |
| Rebuilt add-on ZIP and canonical library staging | Passed |
| Git-eligible files scanned against copied credential values | No matches |

HA tests emit one existing dependency deprecation warning about aiohttp
application inheritance. No unrelated code was changed to suppress it.
The native VS Code import format was verified against its parser; opening the
imported conversations in the UI remains the user's next step.
