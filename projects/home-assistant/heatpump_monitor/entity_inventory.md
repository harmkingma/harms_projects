# P1P2MQTT entity inventory

All entities the P1P2MQTT bridge (`bridge0`) publishes for the Daikin Altherma R hybrid, with
Control_Function and Counter_Request_Function on. Values are a snapshot of 23 Nov 2026 22:30
(heat pump running, outside 2 °C). `CONTROL` marks entities that write to the Daikin.
Regenerate after firmware updates; the bridge may add or rename entities.

Total: 457 entities in 18 devices.

## Sensors (17)

| Entity | Value | Notes |
|---|---:|---|
| `sensor.bridge0_sensors_flow` | 12.9 L/min | Water flow |
| `sensor.bridge0_sensors_temperature_outside` | 2.004 °C | Outside temperature used by the WD curve (before averaging) |
| `sensor.bridge0_sensors_temperature_outside_param15` | 2.0 °C | Outdoor air (other packet), same value |
| `sensor.bridge0_sensors_temperature_outside_unit` | 2.000 °C | Outdoor unit air temperature |
| `sensor.bridge0_sensors_temperature_r1t_hp2gas_water` | 28.9 °C | Water after heat pump heat exchanger, before gas boiler |
| `sensor.bridge0_sensors_temperature_r2t_leaving_water` | 29.0 °C | Leaving water temperature (after gas boiler) |
| `sensor.bridge0_sensors_temperature_r3t_refrigerant` | 25.922 °C | Refrigerant liquid line (R3T) |
| `sensor.bridge0_sensors_temperature_r4t_return_water` | 26.2 °C | Return water temperature |
| `sensor.bridge0_sensors_temperature_r9t_return_water` | 0.000 °C | Not present on this unit (0) |
| `sensor.bridge0_sensors_temperature_refrigerant_2` | -1.500 °C | Outdoor coil refrigerant temperature |
| `sensor.bridge0_sensors_temperature_refrigerant_2_param15` | -1.5 °C | Same, other packet |
| `sensor.bridge0_sensors_temperature_refrigerant_after_heat_exchanger` | 0.000 °C | Not reported by this unit (0) |
| `sensor.bridge0_sensors_temperature_refrigerant_discharge` | 48.0 °C | Compressor discharge temperature |
| `sensor.bridge0_sensors_temperature_refrigerant_q_param15` | 14.4 °C | Refrigerant temperature (function not certain) |
| `sensor.bridge0_sensors_temperature_room` | 20.4 °C | Room temperature from the Daikin room thermostat |
| `sensor.bridge0_sensors_temperature_room_wall` | 20.4 °C | Same room thermostat reading |
| `sensor.bridge0_sensors_water_pressure` | 0.0 bar | Not reported by this unit (0) |

## Room (4)

| Entity | Value | Notes |
|---|---:|---|
| `climate.bridge0_room_room_cooling` | unavailable | |
| `climate.bridge0_room_room_heating` | heat | CONTROL: room thermostat setpoint / on-off (RT mode) |
| `sensor.bridge0_room_room_cooling_setpoint` | 26.0 °C | |
| `sensor.bridge0_room_room_heating_setpoint` | 22.0 °C | Room thermostat heating setpoint |

## LWT (7)

| Entity | Value | Notes |
|---|---:|---|
| `climate.bridge0_lwt_deviation_cooling` | unavailable | |
| `climate.bridge0_lwt_deviation_heating` | heat | CONTROL: LWT offset -10..+10 K (WD mode) |
| `sensor.bridge0_lwt_abs_cooling` | 20.000 °C | |
| `sensor.bridge0_lwt_abs_heating` | 40.000 °C | Absolute LWT setpoint (used only in Abs mode) |
| `sensor.bridge0_lwt_deviation_cooling` | 0 °C | |
| `sensor.bridge0_lwt_deviation_heating` | 0 °C | LWT offset on the WD curve (read-only mirror) |
| `sensor.bridge0_lwt_lwt_setpoint` | 28.7 °C | Active LWT setpoint = WD curve + offset |

## LWT2 (7)

| Entity | Value | Notes |
|---|---:|---|
| `climate.bridge0_lwt2_deviation_cooling_add` | unavailable | |
| `climate.bridge0_lwt2_deviation_heating_add` | unavailable | |
| `sensor.bridge0_lwt2_abs_cooling_add` | 7.000 °C | |
| `sensor.bridge0_lwt2_abs_heating_add` | 45.000 °C | |
| `sensor.bridge0_lwt2_deviation_cooling_add` | 0 °C | |
| `sensor.bridge0_lwt2_deviation_heating_add` | 0 °C | |
| `sensor.bridge0_lwt2_lwt_setpoint_add` | 48.0 °C | |

## Mode (34)

| Entity | Value | Notes |
|---|---:|---|
| `binary_sensor.bridge0_mode_buh` | off | |
| `binary_sensor.bridge0_mode_buh_2` | off | |
| `binary_sensor.bridge0_mode_circulation_pump` | on | Circulation pump running |
| `binary_sensor.bridge0_mode_climate_cooling` | off | |
| `binary_sensor.bridge0_mode_climate_hc_auto` | off | |
| `binary_sensor.bridge0_mode_climate_heating` | on | |
| `binary_sensor.bridge0_mode_compressor` | on | Compressor running |
| `binary_sensor.bridge0_mode_compressor_climate` | on | |
| `binary_sensor.bridge0_mode_defrost_active` | off | Defrost active |
| `binary_sensor.bridge0_mode_external_thermostat_cooling` | off | |
| `binary_sensor.bridge0_mode_external_thermostat_cooling_add` | off | |
| `binary_sensor.bridge0_mode_external_thermostat_heating` | off | |
| `binary_sensor.bridge0_mode_external_thermostat_heating_add` | off | |
| `binary_sensor.bridge0_mode_gasboiler_active` | off | Gas boiler active |
| `binary_sensor.bridge0_mode_heating_only` | on | |
| `binary_sensor.bridge0_mode_preferential_mode` | off | |
| `binary_sensor.bridge0_mode_shc_tank` | off | |
| `binary_sensor.bridge0_mode_valve_zone_add` | off | |
| `binary_sensor.bridge0_mode_valve_zone_main` | on | |
| `button.bridge0_mode_daikin_defrost_request` | unknown | CONTROL: ask for a defrost |
| `number.bridge0_mode_preset_cooling_comfort` | 24.0 | |
| `number.bridge0_mode_preset_cooling_eco` | 26.0 | |
| `number.bridge0_mode_preset_heating_comfort` | 19.0 | |
| `number.bridge0_mode_preset_heating_eco` | 19.0 | |
| `select.bridge0_mode_heating_cooling_auto` | Heating | CONTROL: heating/cooling/auto |
| `select.bridge0_mode_preset_mode` | Schedule | |
| `select.bridge0_mode_program_wd_abs` | WD | CONTROL: weather-dependent or absolute LWT |
| `sensor.bridge0_mode_compressor_rpm` | 36 Hz | Compressor frequency |
| `sensor.bridge0_mode_date_time_daikin` | Mo 2026-11-23 22:08 | |
| `sensor.bridge0_mode_errorcode1` | 0x00 | |
| `sensor.bridge0_mode_errorcode2` | 0x00 | |
| `sensor.bridge0_mode_errorsubcode` | 0x00 | |
| `sensor.bridge0_mode_fan_rpm` | 2375 | Outdoor fan speed |
| `switch.bridge0_mode_altherma_on` | on | CONTROL: space heating on/off |

## Power (5)

| Entity | Value | Notes |
|---|---:|---|
| `sensor.bridge0_power_consumption_buh` | 0 W | |
| `sensor.bridge0_power_consumption_heatpump` | 644 W | Estimated electrical power (inverter current x 230 V) |
| `sensor.bridge0_power_inverter_primary_current` | 2.8 A | Inverter primary current |
| `sensor.bridge0_power_production_gasboiler` | 0 W | Gas boiler heat output, flow x (R2T - R1T) |
| `sensor.bridge0_power_production_heatpump` | 2534 W | Heat pump heat output, flow x (R1T - R4T) |

## COP (4)

| Entity | Value | Notes |
|---|---:|---|
| `sensor.bridge0_cop_cop_after_bridge` | 0.000 | COP since the bridge locked the counters |
| `sensor.bridge0_cop_cop_before_bridge` | 3.782 | |
| `sensor.bridge0_cop_cop_lifetime` | 3.782 | Lifetime COP from Daikin counters |
| `sensor.bridge0_cop_cop_realtime` | 3.935 | Real-time COP (estimate based) |

## Meters (32)

| Entity | Value | Notes |
|---|---:|---|
| `sensor.bridge0_meters_counter_gasboiler_dhw` | 0 | |
| `sensor.bridge0_meters_counter_gasboiler_heating` | 0 | |
| `sensor.bridge0_meters_counter_gasboiler_total` | 0 | |
| `sensor.bridge0_meters_counter_unknown_00` | 0 | |
| `sensor.bridge0_meters_counter_unknown_01` | 0 | |
| `sensor.bridge0_meters_counter_unknown_02` | 0 | |
| `sensor.bridge0_meters_electricity_consumed_backup_dhw` | 0 kWh | |
| `sensor.bridge0_meters_electricity_consumed_backup_heating` | 0 kWh | |
| `sensor.bridge0_meters_electricity_consumed_compressor_cooling` | 0 kWh | |
| `sensor.bridge0_meters_electricity_consumed_compressor_dhw` | 0 kWh | |
| `sensor.bridge0_meters_electricity_consumed_compressor_heating` | 4959 kWh | |
| `sensor.bridge0_meters_electricity_consumed_heatpump_external` | 0.000 kWh | |
| `sensor.bridge0_meters_electricity_consumed_total` | 5072 kWh | |
| `sensor.bridge0_meters_energy_produced_compressor_cooling` | 0 kWh | |
| `sensor.bridge0_meters_energy_produced_compressor_dhw` | 0 kWh | |
| `sensor.bridge0_meters_energy_produced_compressor_heating` | 18756 kWh | |
| `sensor.bridge0_meters_energy_produced_compressor_total` | 18756 kWh | |
| `sensor.bridge0_meters_gas_consumed` | 0.000 kWh | |
| `sensor.bridge0_meters_hours_backup1_dhw` | 0 h | |
| `sensor.bridge0_meters_hours_backup1_heating` | 0 h | |
| `sensor.bridge0_meters_hours_backup2_dhw` | 0 h | |
| `sensor.bridge0_meters_hours_backup2_heating` | 0 h | |
| `sensor.bridge0_meters_hours_booster` | 0 h | |
| `sensor.bridge0_meters_hours_circulation_pump` | 6390 h | |
| `sensor.bridge0_meters_hours_compressor_cooling` | 0 h | |
| `sensor.bridge0_meters_hours_compressor_dhw` | 0 h | |
| `sensor.bridge0_meters_hours_compressor_heating` | 5752 h | |
| `sensor.bridge0_meters_hours_drain_pan_heater` | 0 h | |
| `sensor.bridge0_meters_hours_gasboiler_dhw` | 193 h | |
| `sensor.bridge0_meters_hours_gasboiler_heating` | 538 h | |
| `sensor.bridge0_meters_starts_compressor` | 5114 | |
| `sensor.bridge0_meters_starts_gasboiler` | 36576 | |

## DHW (8)

| Entity | Value | Notes |
|---|---:|---|
| `binary_sensor.bridge0_dhw_dhw` | on | |
| `binary_sensor.bridge0_dhw_dhw_demand` | off | Hot water tap open (gas boiler DHW) |
| `binary_sensor.bridge0_dhw_dhw_related_q` | off | |
| `binary_sensor.bridge0_dhw_valve_dhw_tank` | off | |
| `climate.bridge0_dhw_dhw_setpoint` | heat | |
| `sensor.bridge0_dhw_dhw_setpoint` | 55.0 °C | |
| `sensor.bridge0_dhw_temperature_r5t_dhw_tank` | -40.742 °C | No tank: hot water comes from the gas boiler (invalid value) |
| `switch.bridge0_dhw_dhw_boost` | off | |

## Quiet (4)

| Entity | Value | Notes |
|---|---:|---|
| `select.bridge0_quiet_quiet_level` | Quiet Level 0 | CONTROL: quiet level (power limitation) |
| `select.bridge0_quiet_quiet_level_when_on` | Level 2 | |
| `select.bridge0_quiet_quiet_mode` | Always off | CONTROL: quiet mode |
| `sensor.bridge0_quiet_quiet_mode_active` | 0 | |

## Prices (3)

| Entity | Value | Notes |
|---|---:|---|
| `number.bridge0_prices_gas` | 17.0 €/kWh | |
| `sensor.bridge0_prices_electricity` | 9.00 €/kWh | Daikin price setting (not used in ecological mode) |
| `sensor.bridge0_prices_gas` | 17.00 €/kWh | Daikin price setting (not used in ecological mode) |

## SG (16)

| Entity | Value | Notes |
|---|---:|---|
| `sensor.bridge0_sg_sg_35_005c_general_power_limit_q_2` | 127 | |
| `sensor.bridge0_sg_sg_35_0093_general_power_limit_active_q` | 2 | |
| `sensor.bridge0_sg_sg_35_0094_general_power_limit_kw` | 10.0 | |
| `sensor.bridge0_sg_sg_general_power_limit_2` | 127 | |
| `sensor.bridge0_sg_sg_q_35_0095` | 0 | |
| `sensor.bridge0_sg_sg_q_35_0096` | 0 | |
| `sensor.bridge0_sg_sg_q_35_0097` | 0 | |
| `sensor.bridge0_sg_sg_q_35_0098` | 0 | |
| `sensor.bridge0_sg_sg_q_35_0099` | 0 | |
| `sensor.bridge0_sg_sg_q_35_009a` | 0 | |
| `sensor.bridge0_sg_sg_q_35_009b` | 0 | |
| `sensor.bridge0_sg_sg_q_35_009c` | 0 | |
| `sensor.bridge0_sg_sg_q_35_009d` | 0 | |
| `sensor.bridge0_sg_sg_q_35_009e` | 0 | |
| `sensor.bridge0_sg_sg_q_35_009f` | 0 | |
| `sensor.bridge0_sg_sg_q_35_00a0` | 0 | |

## FieldSettings (246)

Field settings are read-only here; change them on the Daikin interface. The code in the
entity name is the field setting, e.g. `1_02` = [1-02].

| Code | Entity | Value |
|---|---|---:|
| [0-00] | `sensor.bridge0_fieldsettings_0_00_a3123_lwt_heating_add_wd_curve_high_amb_lwt` | 35  |
| [0-01] | `sensor.bridge0_fieldsettings_0_01_a3123_lwt_heating_add_wd_curve_low_amb_lwt` | 60  |
| [0-02] | `sensor.bridge0_fieldsettings_0_02_a3123_lwt_heating_add_wd_curve_high_amb` | 15  |
| [0-03] | `sensor.bridge0_fieldsettings_0_03_a3123_lwt_heating_add_wd_curve_low_amb` | -10  |
| [0-04] | `sensor.bridge0_fieldsettings_0_04_a3124_lwt_cooling_add_wd_curve_high_amb_lwt` | 8  |
| [0-05] | `sensor.bridge0_fieldsettings_0_05_a3124_lwt_cooling_add_wd_curve_low_amb_lwt` | 12  |
| [0-06] | `sensor.bridge0_fieldsettings_0_06_a3124_lwt_cooling_add_wd_curve_high_amb` | 35  |
| [0-07] | `sensor.bridge0_fieldsettings_0_07_a3124_lwt_cooling_add_wd_curve_low_amb` | 20  |
| [0-08] | `sensor.bridge0_fieldsettings_0_08_unspecified_0` | 0  |
| [0-09] | `sensor.bridge0_fieldsettings_0_09_unspecified_0` | 0  |
| [0-0A] | `sensor.bridge0_fieldsettings_0_0a_unspecified_0` | 0  |
| [0-0B] | `sensor.bridge0_fieldsettings_0_0b_a47_dhw_wd_curve_high_amb_setpoint` | 55  |
| [0-0C] | `sensor.bridge0_fieldsettings_0_0c_a47_dhw_wd_curve_low_amb_setpoint` | 60  |
| [0-0D] | `sensor.bridge0_fieldsettings_0_0d_a47_dhw_wd_curve_high_amb` | 15  |
| [0-0E] | `sensor.bridge0_fieldsettings_0_0e_a47_dhw_wd_curve_low_amb` | -10  |
| [1-00] | `sensor.bridge0_fieldsettings_1_00_a3113_lwt_heating_main_wd_curve_low_amb` | -10  |
| [1-01] | `sensor.bridge0_fieldsettings_1_01_a3113_lwt_heating_main_wd_curve_high_amb` | 10  |
| [1-02] | `sensor.bridge0_fieldsettings_1_02_a3113_lwt_heating_main_wd_curve_low_amb_lwt` | 33  |
| [1-03] | `sensor.bridge0_fieldsettings_1_03_a3113_lwt_heating_main_wd_curve_high_amb_lwt` | 26  |
| [1-04] | `sensor.bridge0_fieldsettings_1_04_lwt_cooling_main_wd_enabled` | 1  |
| [1-05] | `sensor.bridge0_fieldsettings_1_05_lwt_cooling_add_wd_enabled` | 1  |
| [1-06] | `sensor.bridge0_fieldsettings_1_06_a3114_lwt_cooling_main_wd_curve_low_amb` | 20  |
| [1-07] | `sensor.bridge0_fieldsettings_1_07_a3114_lwt_cooling_main_wd_curve_high_amb` | 35  |
| [1-08] | `sensor.bridge0_fieldsettings_1_08_a3114_lwt_cooling_main_wd_curve_low_amb_lwt` | 22  |
| [1-09] | `sensor.bridge0_fieldsettings_1_09_a3114_lwt_cooling_main_wd_curve_high_amb_lwt` | 18  |
| [1-0A] | `sensor.bridge0_fieldsettings_1_0a_a64_averaging_time` | 1  |
| [1-0B] | `sensor.bridge0_fieldsettings_1_0b_9i_delta_t_heating_main` | 0  |
| [1-0C] | `sensor.bridge0_fieldsettings_1_0c_9i_delta_t_heating_add` | 0  |
| [1-0D] | `sensor.bridge0_fieldsettings_1_0d_9i_delta_t_cooling_main` | 0  |
| [1-0E] | `sensor.bridge0_fieldsettings_1_0e_9i_delta_t_cooling_add` | 0  |
| [2-00] | `sensor.bridge0_fieldsettings_2_00_a442_dhw_disinfection_operation_day` | 5  |
| [2-01] | `sensor.bridge0_fieldsettings_2_01_a441_dhw_disinfection` | 0  |
| [2-02] | `sensor.bridge0_fieldsettings_2_02_a443_dhw_disinfection_start_time` | 23  |
| [2-03] | `sensor.bridge0_fieldsettings_2_03_a444_dhw_disinfection_setpoint` | 60  |
| [2-04] | `sensor.bridge0_fieldsettings_2_04_a445_dhw_disinfection_duration` | 40  |
| [2-05] | `sensor.bridge0_fieldsettings_2_05_room_antifrost_temperature` | 8  |
| [2-06] | `sensor.bridge0_fieldsettings_2_06_room_antifrost_protection` | 1  |
| [2-07] | `sensor.bridge0_fieldsettings_2_07_unspecified_0` | 0  |
| [2-08] | `sensor.bridge0_fieldsettings_2_08_unspecified_0` | 0  |
| [2-09] | `sensor.bridge0_fieldsettings_2_09_a323_ext_room_sensor_offset` | 0.0  |
| [2-0A] | `sensor.bridge0_fieldsettings_2_0a_a322_room_temperature_offset` | 0.0  |
| [2-0B] | `sensor.bridge0_fieldsettings_2_0b_a65_ext_amb_sensor_offset` | 0.0  |
| [2-0C] | `sensor.bridge0_fieldsettings_2_0c_9i_emitter_type_main` | 0  |
| [2-0D] | `sensor.bridge0_fieldsettings_2_0d_9i_emitter_type_add` | 0  |
| [2-0E] | `sensor.bridge0_fieldsettings_2_0e_9i_maximum_current` | 0  |
| [3-00] | `sensor.bridge0_fieldsettings_3_00_a61_auto_restart_allowed` | 1  |
| [3-01] | `sensor.bridge0_fieldsettings_3_01_unspecified_3_01_rw_0` | 0  |
| [3-02] | `sensor.bridge0_fieldsettings_3_02_unspecified_3_02_rw_1` | 1  |
| [3-03] | `sensor.bridge0_fieldsettings_3_03_unspecified_3_03_rw_4` | 4  |
| [3-04] | `sensor.bridge0_fieldsettings_3_04_unspecified_3_04_rw_2` | 2  |
| [3-05] | `sensor.bridge0_fieldsettings_3_05_unspecified_3_05_rw_1` | 1  |
| [3-06] | `sensor.bridge0_fieldsettings_3_06_a3212_temp_range_room_heating_max` | 30.0  |
| [3-07] | `sensor.bridge0_fieldsettings_3_07_a3211_temp_range_room_heating_min` | 12.0  |
| [3-08] | `sensor.bridge0_fieldsettings_3_08_a3214_temp_range_room_cooling_max` | 35.0  |
| [3-09] | `sensor.bridge0_fieldsettings_3_09_a3213_temp_range_room_cooling_min` | 15.0  |
| [3-0A] | `sensor.bridge0_fieldsettings_3_0a_9i_pump_model` | 0  |
| [3-0B] | `sensor.bridge0_fieldsettings_3_0b_unspecified_0` | 0  |
| [3-0C] | `sensor.bridge0_fieldsettings_3_0c_unspecified_0` | 0  |
| [3-0D] | `sensor.bridge0_fieldsettings_3_0d_unspecified_0` | 0  |
| [3-0E] | `sensor.bridge0_fieldsettings_3_0e_unspecified_0` | 0  |
| [4-00] | `sensor.bridge0_fieldsettings_4_00_unspecified_4_00_ro_1` | 1  |
| [4-01] | `sensor.bridge0_fieldsettings_4_01_unspecified_4_01_ro_0` | 0  |
| [4-02] | `sensor.bridge0_fieldsettings_4_02_a331_heating_amb_temperature_max` | 25  |
| [4-03] | `sensor.bridge0_fieldsettings_4_03_unspecified_4_03_ro_3` | 3  |
| [4-04] | `sensor.bridge0_fieldsettings_4_04_water_pipe_antifrost_protection` | 1  |
| [4-05] | `sensor.bridge0_fieldsettings_4_05_unspecified_4_05_rw_0` | 0  |
| [4-06] | `sensor.bridge0_fieldsettings_4_06_unspecified_4_06_rw_0` | 0  |
| [4-07] | `sensor.bridge0_fieldsettings_4_07_unspecified_4_07_ro_1` | 1  |
| [4-08] | `sensor.bridge0_fieldsettings_4_08_a631_power_consumption_control_mode` | 0  |
| [4-09] | `sensor.bridge0_fieldsettings_4_09_a632_power_consumption_control_type` | 1  |
| [4-0A] | `sensor.bridge0_fieldsettings_4_0a_unspecified_4_0a_ro_0` | 0  |
| [4-0B] | `sensor.bridge0_fieldsettings_4_0b_auto_cooling_heating_changeover_hysteresis` | 1.0  |
| [4-0C] | `sensor.bridge0_fieldsettings_4_0c_unspecified_0` | 0  |
| [4-0D] | `sensor.bridge0_fieldsettings_4_0d_auto_cooling_heating_changeover_offset` | 3.0  |
| [4-0E] | `sensor.bridge0_fieldsettings_4_0e_unspecified_4_0e_ro_0` | 0  |
| [5-00] | `sensor.bridge0_fieldsettings_5_00_equilibrium_enabled` | 1  |
| [5-01] | `sensor.bridge0_fieldsettings_5_01_a522_equilibrium_temp` | -6  |
| [5-02] | `sensor.bridge0_fieldsettings_5_02_unspecified_5_02_ro_0` | 0  |
| [5-03] | `sensor.bridge0_fieldsettings_5_03_unspecified_5_03_rw_0` | 0  |
| [5-04] | `sensor.bridge0_fieldsettings_5_04_unspecified_5_04_rw_10` | 10  |
| [5-05] | `sensor.bridge0_fieldsettings_5_05_a633_a6351_power_consumption_control_amp_value_1` | 50  |
| [5-06] | `sensor.bridge0_fieldsettings_5_06_a6351_power_consumption_control_amp_value_2` | 50  |
| [5-07] | `sensor.bridge0_fieldsettings_5_07_a6351_power_consumption_control_amp_value_3` | 50  |
| [5-08] | `sensor.bridge0_fieldsettings_5_08_a6351_power_consumption_control_amp_value_4` | 50  |
| [5-09] | `sensor.bridge0_fieldsettings_5_09_a634_a6361_power_consumption_control_kw_value_1` | 20.0  |
| [5-0A] | `sensor.bridge0_fieldsettings_5_0a_a6361_power_consumption_control_kw_value_2` | 20.0  |
| [5-0B] | `sensor.bridge0_fieldsettings_5_0b_a6361_power_consumption_control_kw_value_3` | 20.0  |
| [5-0C] | `sensor.bridge0_fieldsettings_5_0c_a6361_power_consumption_control_kw_value_4` | 20.0  |
| [5-0D] | `sensor.bridge0_fieldsettings_5_0d_unspecified_5_0d_ro_1` | 1  |
| [5-0E] | `sensor.bridge0_fieldsettings_5_0e_unspecified_5_0e_ro_0` | 0  |
| [6-00] | `sensor.bridge0_fieldsettings_6_00_temp_diff_determining_on` | 2  |
| [6-01] | `sensor.bridge0_fieldsettings_6_01_temp_diff_determining_off` | 2  |
| [6-02] | `sensor.bridge0_fieldsettings_6_02_unspecified_6_02_ro_0` | 0.0  |
| [6-03] | `sensor.bridge0_fieldsettings_6_03_unspecified_6_03_ro_0` | 0.0  |
| [6-04] | `sensor.bridge0_fieldsettings_6_04_unspecified_6_04_ro_0` | 0.0  |
| [6-05] | `sensor.bridge0_fieldsettings_6_05_unspecified_6_05_ro_0` | 0.0  |
| [6-06] | `sensor.bridge0_fieldsettings_6_06_unspecified_6_06_ro_0` | 0.0  |
| [6-07] | `sensor.bridge0_fieldsettings_6_07_unspecified_6_07_rw_0` | 0  |
| [6-08] | `sensor.bridge0_fieldsettings_6_08_unspecified_6_08_rw_5` | 5  |
| [6-09] | `sensor.bridge0_fieldsettings_6_09_unspecified_6_09_rw_0` | 0  |
| [6-0A] | `sensor.bridge0_fieldsettings_6_0a_7431_tank_storage_comfort` | 60  |
| [6-0B] | `sensor.bridge0_fieldsettings_6_0b_7432_tank_storage_eco` | 50  |
| [6-0C] | `sensor.bridge0_fieldsettings_6_0c_7433_tank_reheat` | 50  |
| [6-0D] | `sensor.bridge0_fieldsettings_6_0d_a41_dhw_reheat` | 2  |
| [6-0E] | `sensor.bridge0_fieldsettings_6_0e_a45_dhw_setpoint_max` | 65  |
| [7-00] | `sensor.bridge0_fieldsettings_7_00_unspecified_7_00_ro_0` | 0  |
| [7-01] | `sensor.bridge0_fieldsettings_7_01_unspecified_7_01_ro_2` | 2  |
| [7-02] | `sensor.bridge0_fieldsettings_7_02_a218_number_of_lwt_zones` | 0  |
| [7-03] | `sensor.bridge0_fieldsettings_7_03_pe_factor` | 2.5  |
| [7-04] | `sensor.bridge0_fieldsettings_7_04_a67_savings_mode_ecological` | 1  |
| [7-05] | `sensor.bridge0_fieldsettings_7_05_unspecified_7_05_ro_0` | 0  |
| [7-06] | `sensor.bridge0_fieldsettings_7_06_9i_compressor_forced_off` | 0  |
| [7-07] | `sensor.bridge0_fieldsettings_7_07_9i_bbr16_activation` | 0  |
| [7-08] | `sensor.bridge0_fieldsettings_7_08_9i_unspecified_rw_0` | 0  |
| [7-09] | `sensor.bridge0_fieldsettings_7_09_9i_pump_minimum_pwm_value` | 0  |
| [7-0A] | `sensor.bridge0_fieldsettings_7_0a_9i_pump_fixed_add_zone_bizonekit` | 0  |
| [7-0B] | `sensor.bridge0_fieldsettings_7_0b_9i_pump_fixed_main_zone_bizonekit` | 0  |
| [7-0C] | `sensor.bridge0_fieldsettings_7_0c_9i_mixing_valve_time_bizonekit` | 0  |
| [7-0D] | `sensor.bridge0_fieldsettings_7_0d_9i_bivalent_hysteresis_heating` | 0  |
| [7-0E] | `sensor.bridge0_fieldsettings_7_0e_9i_setpoint_offset_excess_state` | 0  |
| [8-00] | `sensor.bridge0_fieldsettings_8_00_dhw_running_time_min` | 1  |
| [8-01] | `sensor.bridge0_fieldsettings_8_01_dhw_running_time_max` | 30  |
| [8-02] | `sensor.bridge0_fieldsettings_8_02_anti_recycling_time` | 1.5  |
| [8-03] | `sensor.bridge0_fieldsettings_8_03_unspecified_8_03_ro_50` | 50  |
| [8-04] | `sensor.bridge0_fieldsettings_8_04_unspecified_8_04_ro_0` | 0  |
| [8-05] | `sensor.bridge0_fieldsettings_8_05_a3115_lwt_modulation_allow` | 0  |
| [8-06] | `sensor.bridge0_fieldsettings_8_06_lwt_modulation_max` | 5  |
| [8-07] | `sensor.bridge0_fieldsettings_8_07_7423_lwt_main_cooling_comfort` | 18  |
| [8-08] | `sensor.bridge0_fieldsettings_8_08_7424_lwt_main_cooling_eco` | 20  |
| [8-09] | `sensor.bridge0_fieldsettings_8_09_7421_lwt_main_heating_comfort` | 40  |
| [8-0A] | `sensor.bridge0_fieldsettings_8_0a_7422_lwt_main_heating_eco` | 40  |
| [8-0B] | `sensor.bridge0_fieldsettings_8_0b_flow_target_heatpump` | 13.0  |
| [8-0C] | `sensor.bridge0_fieldsettings_8_0c_flow_target_hybrid` | 13.0  |
| [8-0D] | `sensor.bridge0_fieldsettings_8_0d_flow_target_gasboiler` | 16.0  |
| [8-0E] | `sensor.bridge0_fieldsettings_8_0e_unspecified_0` | 0  |
| [9-00] | `sensor.bridge0_fieldsettings_9_00_a31122_temp_heating_main_max` | 40  |
| [9-01] | `sensor.bridge0_fieldsettings_9_01_a31121_temp_heating_main_min` | 25  |
| [9-02] | `sensor.bridge0_fieldsettings_9_02_a31124_temp_cooling_main_max` | 22  |
| [9-03] | `sensor.bridge0_fieldsettings_9_03_a31123_temp_cooling_main_min` | 5  |
| [9-04] | `sensor.bridge0_fieldsettings_9_04_unspecified_9_04_ro_1` | 1  |
| [9-05] | `sensor.bridge0_fieldsettings_9_05_a31221_temp_heating_add_min` | 25  |
| [9-06] | `sensor.bridge0_fieldsettings_9_06_a31222_temp_heating_add_max` | 80  |
| [9-07] | `sensor.bridge0_fieldsettings_9_07_a31223_temp_cooling_add_min` | 5  |
| [9-08] | `sensor.bridge0_fieldsettings_9_08_a31224_temp_cooling_add_max` | 22  |
| [9-09] | `sensor.bridge0_fieldsettings_9_09_delta_t` | 5  |
| [9-0A] | `sensor.bridge0_fieldsettings_9_0a_unspecified_9_0a_rw_5` | 5  |
| [9-0B] | `sensor.bridge0_fieldsettings_9_0b_a3117_emitter_slow` | 1  |
| [9-0C] | `sensor.bridge0_fieldsettings_9_0c_room_temperature_hysteresis` | 1.0  |
| [9-0D] | `sensor.bridge0_fieldsettings_9_0d_pump_speed_limitation` | 6  |
| [9-0E] | `sensor.bridge0_fieldsettings_9_0e_unknown` | 6  |
| [A-00] | `sensor.bridge0_fieldsettings_a_00_unspecified_a_00_0` | 0  |
| [A-01] | `sensor.bridge0_fieldsettings_a_01_unspecified_a_01_0` | 0  |
| [A-02] | `sensor.bridge0_fieldsettings_a_02_unspecified_a_02_0` | 0  |
| [A-03] | `sensor.bridge0_fieldsettings_a_03_unspecified_a_03_0` | 0  |
| [A-04] | `sensor.bridge0_fieldsettings_a_04_unspecified_a_04_0` | 0  |
| [A-05] | `sensor.bridge0_fieldsettings_a_05_unspecified_0` | 0  |
| [A-06] | `sensor.bridge0_fieldsettings_a_06_unspecified_0` | 0  |
| [A-07] | `sensor.bridge0_fieldsettings_a_07_unspecified_0` | 0  |
| [A-08] | `sensor.bridge0_fieldsettings_a_08_unspecified_0` | 0  |
| [A-09] | `sensor.bridge0_fieldsettings_a_09_unspecified_0` | 0  |
| [A-0A] | `sensor.bridge0_fieldsettings_a_0a_unspecified_0` | 0  |
| [A-0B] | `sensor.bridge0_fieldsettings_a_0b_unspecified_0` | 0  |
| [A-0C] | `sensor.bridge0_fieldsettings_a_0c_unspecified_0` | 0  |
| [A-0D] | `sensor.bridge0_fieldsettings_a_0d_unspecified_0` | 0  |
| [A-0E] | `sensor.bridge0_fieldsettings_a_0e_unspecified_0` | 0  |
| [B-00] | `sensor.bridge0_fieldsettings_b_00_unspecified_b_00_0` | 0  |
| [B-01] | `sensor.bridge0_fieldsettings_b_01_unspecified_b_01_0` | 0  |
| [B-02] | `sensor.bridge0_fieldsettings_b_02_unspecified_b_02_0` | 0  |
| [B-03] | `sensor.bridge0_fieldsettings_b_03_unspecified_b_03_0` | 0  |
| [B-04] | `sensor.bridge0_fieldsettings_b_04_unspecified_b_04_0` | 0  |
| [B-05] | `sensor.bridge0_fieldsettings_b_05_unspecified_0` | 0  |
| [B-06] | `sensor.bridge0_fieldsettings_b_06_unspecified_0` | 0  |
| [B-07] | `sensor.bridge0_fieldsettings_b_07_unspecified_0` | 0  |
| [B-08] | `sensor.bridge0_fieldsettings_b_08_unspecified_0` | 0  |
| [B-09] | `sensor.bridge0_fieldsettings_b_09_unspecified_0` | 0  |
| [B-0A] | `sensor.bridge0_fieldsettings_b_0a_unspecified_0` | 0  |
| [B-0B] | `sensor.bridge0_fieldsettings_b_0b_unspecified_0` | 0  |
| [B-0C] | `sensor.bridge0_fieldsettings_b_0c_unspecified_0` | 0  |
| [B-0D] | `sensor.bridge0_fieldsettings_b_0d_unspecified_0` | 0  |
| [B-0E] | `sensor.bridge0_fieldsettings_b_0e_unspecified_0` | 0  |
| [C-00] | `sensor.bridge0_fieldsettings_c_00_dhw_priority` | 0  |
| [C-01] | `sensor.bridge0_fieldsettings_c_01_unspecified_c_01_ro_0` | 0  |
| [C-02] | `sensor.bridge0_fieldsettings_c_02_external_backup` | 0  |
| [C-03] | `sensor.bridge0_fieldsettings_c_03_bivalent_activation_temperature` | 0  |
| [C-04] | `sensor.bridge0_fieldsettings_c_04_bivalent_hysteresis_temperature` | 3  |
| [C-05] | `sensor.bridge0_fieldsettings_c_05_a224_contact_type_main` | 2  |
| [C-06] | `sensor.bridge0_fieldsettings_c_06_a225_contact_type_add` | 2  |
| [C-07] | `sensor.bridge0_fieldsettings_c_07_a217_unit_control_method` | 2  |
| [C-08] | `sensor.bridge0_fieldsettings_c_08_a22b_external_sensor` | 0  |
| [C-09] | `sensor.bridge0_fieldsettings_c_09_a2263_digital_io_pcb_alarm_output` | 0  |
| [C-0A] | `sensor.bridge0_fieldsettings_c_0a_indoor_quick_heatup_enable` | 1  |
| [C-0B] | `sensor.bridge0_fieldsettings_c_0b_unspecified_0` | 0  |
| [C-0C] | `sensor.bridge0_fieldsettings_c_0c_7451_electricity_price_high` | 3  |
| [C-0D] | `sensor.bridge0_fieldsettings_c_0d_7452_electricity_price_medium` | 3  |
| [C-0E] | `sensor.bridge0_fieldsettings_c_0e_7453_electricity_price_low` | 3  |
| [D-00] | `sensor.bridge0_fieldsettings_d_00_unspecified_d_00_rw_0` | 0  |
| [D-01] | `sensor.bridge0_fieldsettings_d_01_a216_preferential_kwh_rate` | 0  |
| [D-02] | `sensor.bridge0_fieldsettings_d_02_a22a_dhw_pump` | 0  |
| [D-03] | `sensor.bridge0_fieldsettings_d_03_lwt_0c_compensation_shift` | 0  |
| [D-04] | `sensor.bridge0_fieldsettings_d_04_a227_demand_pcb` | 0  |
| [D-05] | `sensor.bridge0_fieldsettings_d_05_unspecified_d_05_ro_0` | 1  |
| [D-06] | `sensor.bridge0_fieldsettings_d_06_unspecified_0` | 0  |
| [D-07] | `sensor.bridge0_fieldsettings_d_07_a2262_digital_io_pcb_solar_kit` | 0  |
| [D-08] | `sensor.bridge0_fieldsettings_d_08_a228_external_kwh_meter_1` | 0  |
| [D-09] | `sensor.bridge0_fieldsettings_d_09_unspecified_d_09_ro_0` | 0  |
| [D-0A] | `sensor.bridge0_fieldsettings_d_0a_a22c_external_gas_meter_1` | 0  |
| [D-0B] | `sensor.bridge0_fieldsettings_d_0b_unspecified_d_0b_rw_2` | 2  |
| [D-0C] | `sensor.bridge0_fieldsettings_d_0c_7451_electricity_price_high_do_not_use` | 40  |
| [D-0D] | `sensor.bridge0_fieldsettings_d_0d_7452_electricity_price_medium_do_not_use` | 40  |
| [D-0E] | `sensor.bridge0_fieldsettings_d_0e_7453_electricity_price_low_do_not_use` | 40  |
|  | `button.bridge0_fieldsettings_daikin_restart_careful` | unknown  |
| [E-00] | `sensor.bridge0_fieldsettings_e_00_a211_ro_unit_type` | 3  |
| [E-01] | `sensor.bridge0_fieldsettings_e_01_a212_ro_compressor_type` | 0  |
| [E-02] | `sensor.bridge0_fieldsettings_e_02_a213_ro_indoor_software_type` | 1  |
| [E-03] | `sensor.bridge0_fieldsettings_e_03_unspecified_e_03_ro_0` | 0  |
| [E-04] | `sensor.bridge0_fieldsettings_e_04_a21a_ro_power_saving_available` | 1  |
| [E-05] | `binary_sensor.bridge0_fieldsettings_e_05_a221_dhw_operation` | on  |
| [E-06] | `binary_sensor.bridge0_fieldsettings_e_06_a222_dhw_tank_installed` | off  |
| [E-07] | `sensor.bridge0_fieldsettings_e_07_a223_dhw_tank_type` | 4  |
| [E-08] | `sensor.bridge0_fieldsettings_e_08_power_saving_enabled` | 1  |
| [E-09] | `sensor.bridge0_fieldsettings_e_09_unspecified_e_09_rw_0` | 0  |
| [E-0A] | `sensor.bridge0_fieldsettings_e_0a_unspecified_e_0a_ro_0` | 0  |
| [E-0B] | `sensor.bridge0_fieldsettings_e_0b_unspecified_e_0b_ro_0` | 0  |
| [E-0C] | `sensor.bridge0_fieldsettings_e_0c_unspecified_e_0c_ro_0` | 0  |
| [E-0D] | `sensor.bridge0_fieldsettings_e_0d_unspecified_e_0d_ro_0` | 0  |
| [E-0E] | `sensor.bridge0_fieldsettings_e_0e_unspecified_0` | 0  |
| [F-00] | `sensor.bridge0_fieldsettings_f_00_pump_operation_outside_range_allowed` | 0  |
| [F-01] | `sensor.bridge0_fieldsettings_f_01_a332_cooling_amb_temperature_min` | 20  |
| [F-02] | `sensor.bridge0_fieldsettings_f_02_unspecified_f_02_rw_3` | 3  |
| [F-03] | `sensor.bridge0_fieldsettings_f_03_unspecified_f_03_rw_5` | 5  |
| [F-04] | `sensor.bridge0_fieldsettings_f_04_unspecified_f_04_rw_0` | 0  |
| [F-05] | `sensor.bridge0_fieldsettings_f_05_unspecified_f_05_rw_0` | 0  |
| [F-06] | `sensor.bridge0_fieldsettings_f_06_unspecified_f_06_rw_0` | 0  |
| [F-07] | `sensor.bridge0_fieldsettings_f_07_efficiency_calculation_0` | 0  |
| [F-08] | `sensor.bridge0_fieldsettings_f_08_continuous_heating_defrost_enable` | 0  |
| [F-09] | `sensor.bridge0_fieldsettings_f_09_pump_operation_during_flow_abnormality` | 0  |
| [F-0A] | `sensor.bridge0_fieldsettings_f_0a_unspecified_f_0a_rw_0` | 0  |
| [F-0B] | `sensor.bridge0_fieldsettings_f_0b_a31161_shutoff_valve_closed_during_thermo_off` | 0  |
| [F-0C] | `sensor.bridge0_fieldsettings_f_0c_a31162_shutoff_valve_closed_during_cooling` | 1  |
| [F-0D] | `sensor.bridge0_fieldsettings_f_0d_a219_pump_operation_mode` | 2  |
|  | `sensor.bridge0_fieldsettings_f_oe_max_power_tank_heating_support` | 0  |
|  | `select.bridge0_fieldsettings_number_of_zones` | 1 LWT zone  |
|  | `number.bridge0_fieldsettings_overshoot` | 1  |
|  | `select.bridge0_fieldsettings_rt_lwt` | RT  |
|  | `select.bridge0_fieldsettings_rt_modulation` | No modulation  |
|  | `number.bridge0_fieldsettings_rt_modulation_max` | 5  |

## UI (11)

| Entity | Value | Notes |
|---|---:|---|
| `binary_sensor.bridge0_ui_aux_f0_advanced` | on | |
| `binary_sensor.bridge0_ui_aux_f0_installer` | off | |
| `binary_sensor.bridge0_ui_aux_f0_lcd_light` | off | |
| `binary_sensor.bridge0_ui_main_advanced` | on | |
| `binary_sensor.bridge0_ui_main_installer` | off | |
| `binary_sensor.bridge0_ui_main_lcd_light` | off | |
| `button.bridge0_ui_bridge_lcd_fake_off` | unknown | |
| `button.bridge0_ui_bridge_lcd_fake_on` | unknown | |
| `button.bridge0_ui_bridge_mode_0_normal_user` | unknown | |
| `button.bridge0_ui_bridge_mode_1_advanced_user` | unknown | |
| `button.bridge0_ui_bridge_mode_2_installer` | unknown | |

## Bridge (24)

| Entity | Value | Notes |
|---|---:|---|
| `binary_sensor.bridge0_bridge_esp_eeprom_saved` | off | |
| `binary_sensor.bridge0_bridge_esp_factory_reset_scheduled` | off | |
| `binary_sensor.bridge0_bridge_esp_throttling` | off | |
| `binary_sensor.bridge0_bridge_esp_waiting_for_counters_d13` | off | |
| `button.bridge0_bridge_eeprom_esp_save_changes` | unknown | |
| `button.bridge0_bridge_eeprom_esp_set_cons_prod_counters` | unknown | |
| `button.bridge0_bridge_eeprom_esp_undo_changes` | unknown | |
| `button.bridge0_bridge_mqtt_rebuild` | unknown | |
| `button.bridge0_bridge_restart_p1p2monitor_atmega` | unknown | |
| `button.bridge0_bridge_restart_p1p2mqtt_esp` | unknown | |
| `number.bridge0_bridge_r1toffset_mid` | 0.0 °C | |
| `number.bridge0_bridge_r2toffset_lwt` | 0.0 °C | |
| `number.bridge0_bridge_r4toffset_rwt` | 0.0 °C | |
| `number.bridge0_bridge_rtoffset_room` | 0.0 °C | |
| `number.bridge0_bridge_write_budget` | 100 | Writes allowed before throttling |
| `number.bridge0_bridge_write_budget_period` | 15 | |
| `sensor.bridge0_bridge_control_id` | 0xF0 | |
| `sensor.bridge0_bridge_error_budget` | 11 | Bus errors allowed before the bridge switches control off |
| `sensor.bridge0_bridge_v_interface` | 15.3 V | |
| `sensor.bridge0_bridge_wifi_rssi` | -35 | |
| `sensor.bridge0_bridge_writes_refused_budget` | 0 | |
| `sensor.bridge0_bridge_writes_refused_busy` | 0 | |
| `switch.bridge0_bridge_control_function` | on | Bridge auxiliary controller mode (needed for controls and field settings) |
| `switch.bridge0_bridge_counter_request_function` | on | Bridge requests Daikin counters every minute |

## Setup (5)

| Entity | Value | Notes |
|---|---:|---|
| `button.bridge0_setup_factory_reset_esp_after_restart` | unknown | |
| `button.bridge0_setup_factory_reset_esp_cancel` | unknown | |
| `button.bridge0_setup_mqtt_delete_all_rebuild` | unknown | |
| `button.bridge0_setup_mqtt_delete_own_rebuild` | unknown | |
| `switch.bridge0_setup_ha_setup` | on | |

## Unknown (11)

| Entity | Value | Notes |
|---|---:|---|
| `binary_sensor.bridge0_unknown_buh1_q` | off | |
| `binary_sensor.bridge0_unknown_climate_active_q4` | on | |
| `binary_sensor.bridge0_unknown_climate_mode_q` | off | |
| `binary_sensor.bridge0_unknown_climate_on_q` | on | |
| `binary_sensor.bridge0_unknown_climate_q_1` | off | |
| `binary_sensor.bridge0_unknown_climate_q_2` | off | |
| `binary_sensor.bridge0_unknown_climate_related_q` | off | |
| `binary_sensor.bridge0_unknown_dhw_related_q` | off | |
| `sensor.bridge0_unknown_setpoint_room_q` | 30.0 °C | |
| `sensor.bridge0_unknown_temperature_unused_11_16` | 0.000 °C | |
| `sensor.bridge0_unknown_temperature_unused_11_18` | 0.000 °C | |

## 15_param (19)

| Entity | Value | Notes |
|---|---:|---|
| `binary_sensor.bridge0_15_param_defrost_active_param15` | unknown | |
| `sensor.bridge0_15_param_param15_00` | 0 | |
| `sensor.bridge0_15_param_param15_01` | 1 | |
| `sensor.bridge0_15_param_param15_04` | 0 | |
| `sensor.bridge0_15_param_param15_07` | 0 | |
| `sensor.bridge0_15_param_param15_09` | 0 | |
| `sensor.bridge0_15_param_param15_0b` | 0.0 °C | |
| `sensor.bridge0_15_param_param15_0d` | 0 | |
| `sensor.bridge0_15_param_param15_0e` | 80 | |
| `sensor.bridge0_15_param_param15_0f` | 178 | |
| `sensor.bridge0_15_param_param15_11_fan2_q` | 30 | |
| `sensor.bridge0_15_param_param15_12` | 0 | |
| `sensor.bridge0_15_param_param15_13` | 0 | |
| `sensor.bridge0_15_param_param15_14` | 0 | |
| `sensor.bridge0_15_param_param15_15` | 0 | |
| `sensor.bridge0_15_param_param15_16` | 0 | |
| `sensor.bridge0_15_param_param15_17` | 0 | |
| `sensor.bridge0_15_param_param15_temperature_18` | 0.0 °C | |
| `sensor.bridge0_15_param_param15_temperature_19` | 0.1 °C | |
