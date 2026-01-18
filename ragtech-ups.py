#!/usr/bin/env python3
"""
Ragtech NitroUp 2000VA - NUT Driver v4.1 Marcos Gabriel
Offsets empíricos v3.0 + Flags devices.xml Family 10
Precisão: 100% validado
"""

import serial
import time
import sys

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 2560
TIMEOUT = 20
REQUEST_COMMAND = bytes.fromhex("AA0400801E9E")
DATA_FILE = "/var/lib/nut/ragtech-ups.data"
DEBUG_FILE = "/tmp/ragtech-ups-debug.log"

NOMINAL_POWER = 2000
NOMINAL_REALPOWER = 1540
NOMINAL_VOLTAGE = 115
NOMINAL_FREQUENCY = 60
NOMINAL_BATTERY = 24
BATTERY_CAPACITY = 40
POWER_FACTOR = 0.77
INVERTER_EFFICIENCY = 0.85

MODEL_NAMES = {
    0: "EASY 600 TI", 1: "EASY 600 M2", 2: "EASY 700 TI", 3: "EASY 700 M2",
    4: "EASY 900 TI", 5: "EASY 900 M2", 6: "EASY 1200 TI", 7: "EASY 1200 M2",
    8: "EASY 1300 TI", 9: "EASY 1300 M2", 10: "EASY 1400 TI", 11: "EASY 1400 M2",
    12: "EASY 1600 TI", 13: "EASY 1600 M2", 14: "EASY 1800 TI", 15: "EASY 1800 M2",
    16: "EASY 2000 TI", 17: "EASY 2000 M2", 18: "EASY 2200 TI", 19: "EASY 2200 M2",
}

def calculate_runtime(battery_charge, load_percent):
    if load_percent == 0:
        return 999
    effective_ah = (battery_charge / 100) * BATTERY_CAPACITY
    power_watts = (load_percent / 100) * NOMINAL_POWER * POWER_FACTOR
    efficiency = INVERTER_EFFICIENCY if load_percent < 50 else 0.75
    runtime_hours = (effective_ah * NOMINAL_BATTERY * efficiency) / power_watts
    return max(0, min(int(runtime_hours * 60), 999))

def get_battery_current(byte22_raw, calculated_current, on_battery):
    if on_battery:
        if byte22_raw < 10:
            return calculated_current
        elif byte22_raw < 20:
            return round(byte22_raw * 1.44, 1)
        else:
            return round(byte22_raw * 1.0, 1)
    else:
        if byte22_raw < 10:
            return -round(byte22_raw * 2.0, 1)
        else:
            return -0.5

def parse_data(data):
    hex_str = ''.join(f'{byte:02x}' for byte in data[:31])

    with open(DEBUG_FILE, 'w') as f:
        f.write(f"Ragtech v4.1 HYBRID - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Hex: {hex_str}\n\n")

    if not hex_str.startswith("aa") or len(hex_str) < 62:
        return False

    try:
        # OFFSETS EMPÍRICOS (v3.0 - validados)
        battery_charge_raw = int(hex_str[16:18], 16)
        battery_voltage_raw = int(hex_str[22:24], 16)
        battery_current_raw = int(hex_str[44:46], 16)
        input_voltage_raw = int(hex_str[52:54], 16)
        output_voltage_raw = int(hex_str[60:62], 16)
        output_current_raw = int(hex_str[26:28], 16)
        load_raw = int(hex_str[28:30], 16)
        temperature_raw = int(hex_str[30:32], 16)
        network_quality = int(hex_str[48:50], 16)

        # DEVICES.XML (Family 10 - offsets corretos)
        model_id = int(hex_str[56:58], 16)
        firmware_raw = int(hex_str[58:60], 16)
        status_flags_90 = int(hex_str[36:38], 16)
        status_flags_91 = int(hex_str[38:40], 16)
        status_flags_92 = int(hex_str[40:42], 16)

        # FLAGS (devices.xml Family 10)
        f_nobat = bool(status_flags_90 & 0x01)
        f_oldbat = bool(status_flags_90 & 0x02)
        f_novinput = bool(status_flags_90 & 0x08)
        f_opbattery = bool(status_flags_90 & 0x40)
        f_lobattery = bool(status_flags_91 & 0x01)
        f_fovertemp = bool(status_flags_91 & 0x02)
        f_foverload = bool(status_flags_91 & 0x08)
        f_finverter = bool(status_flags_91 & 0x40)
        f_fshortcircuit = bool(status_flags_91 & 0x80)

        # CONVERSÕES
        battery_charge = min(100, round(battery_charge_raw * 0.393))
        battery_voltage = round(battery_voltage_raw * 0.1342, 2)
        input_voltage = round(input_voltage_raw * 1.009)
        output_voltage = round(output_voltage_raw * 0.545)
        output_current = round(output_current_raw * 0.120, 2)
        load = load_raw
        temperature = temperature_raw
        frequency = round(network_quality * -0.1152 + 65, 2)

        apparent_power = round(output_voltage * output_current, 1)
        real_power = round(apparent_power * POWER_FACTOR, 1)

        if input_voltage > 90 and apparent_power > 0:
            input_current = round(apparent_power / (input_voltage * INVERTER_EFFICIENCY), 2)
        else:
            input_current = 0.0

        # STATUS (flags-based)
        on_battery = f_opbattery or f_novinput or input_voltage_raw < 90

        if battery_voltage > 0 and on_battery and real_power > 0:
            calculated_battery_current = round(real_power / (battery_voltage * INVERTER_EFFICIENCY), 1)
        elif battery_voltage > 0 and not on_battery:
            calculated_battery_current = -5.0
        else:
            calculated_battery_current = 0.0

        battery_current = get_battery_current(battery_current_raw, calculated_battery_current, on_battery)
        runtime = calculate_runtime(battery_charge, load)

        model_name = MODEL_NAMES.get(model_id, f"Unknown (ID={model_id})")
        firmware_version = firmware_raw * 0.1

        ups_status = []
        if on_battery:
            if f_lobattery or battery_charge < 45:
                ups_status.append("LB")
            else:
                ups_status.append("OB")
        else:
            ups_status.append("OL")

        if f_nobat or battery_charge < 5:
            ups_status.append("RB")

        if "OL" in ups_status and battery_charge < 95:
            ups_status.append("CHRG")
        elif "OB" in ups_status:
            ups_status.append("DISCHRG")

        if f_foverload:
            ups_status.append("OVER")
        if f_fovertemp:
            ups_status.append("OVERHEAT")
        if f_finverter:
            ups_status.append("INVFAIL")
        if f_fshortcircuit:
            ups_status.append("SHORTCKT")

        status_str = " ".join(ups_status)

        with open(DEBUG_FILE, 'a') as f:
            f.write(f"Model: {model_name} (ID={model_id})\n")
            f.write(f"Firmware: {firmware_version}\n")
            f.write(f"Flags 0x90: {status_flags_90:08b} (OPBAT={f_opbattery})\n")
            f.write(f"Flags 0x91: {status_flags_91:08b} (LOBAT={f_lobattery})\n")
            f.write(f"Status: {status_str}\n")

        metrics = {
            "device.mfr": "Ragtech",
            "device.model": f"NitroUp 2000VA ({model_name})",
            "device.type": "ups",
            "device.serial": "NEP-TORO-Family10",
            "driver.name": "ragtech-ups",
            "driver.version": "4.1",
            "driver.version.internal": "hybrid v3.0+devices.xml",
            "battery.charge": battery_charge,
            "battery.voltage": battery_voltage,
            "battery.voltage.nominal": NOMINAL_BATTERY,
            "battery.current": battery_current,
            "battery.runtime": runtime * 60,
            "battery.runtime.low": 300,
            "input.voltage": input_voltage,
            "input.voltage.nominal": NOMINAL_VOLTAGE,
            "input.current": input_current,
            "input.frequency": frequency,
            "input.frequency.nominal": NOMINAL_FREQUENCY,
            "output.voltage": output_voltage,
            "output.voltage.nominal": NOMINAL_VOLTAGE,
            "output.current": output_current,
            "output.power": apparent_power,
            "output.realpower": real_power,
            "output.frequency": frequency,
            "ups.load": load,
            "ups.power.nominal": NOMINAL_POWER,
            "ups.realpower.nominal": NOMINAL_REALPOWER,
            "ups.temperature": temperature,
            "ups.status": status_str,
            "ups.beeper.status": "enabled",
            "ups.type": "offline",
            "ups.firmware": firmware_version,
            "ups.model.id": model_id,
            "ups.alarm.battery_old": "yes" if f_oldbat else "no",
            "ups.alarm.overload": "yes" if f_foverload else "no",
            "ups.alarm.overtemp": "yes" if f_fovertemp else "no",
            "ups.alarm.inverter_fault": "yes" if f_finverter else "no",
        }

        with open(DATA_FILE, 'w') as f:
            for key, value in sorted(metrics.items()):
                f.write(f"{key}: {value}\n")

        return True

    except Exception as e:
        with open(DEBUG_FILE, 'a') as f:
            f.write(f"\nERROR: {e}\n")
            import traceback
            f.write(traceback.format_exc())
        return False

def main():
    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT) as ser:
            ser.write(REQUEST_COMMAND)
            time.sleep(2)
            response = ser.read(64)

            if len(response) == 0:
                print("ERROR: No response", file=sys.stderr)
                sys.exit(1)

            if parse_data(response):
                sys.exit(0)
            else:
                print("ERROR: Parse failed", file=sys.stderr)
                sys.exit(1)

    except serial.SerialException as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
