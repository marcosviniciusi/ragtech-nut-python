#!/usr/bin/env python3
"""
Ragtech NitroUp 2000VA - Continuous Dump
Desconecte da tomada após iniciar para capturar transição
Baseado no driver NUT v1.6
"""
import serial
import time
from datetime import datetime

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 2560
TIMEOUT = 20
REQUEST_COMMAND = bytes.fromhex("AA0400801E9E")

def dump_reading(ser, reading_num):
    """Captura uma leitura e exibe hex + valores chave"""
    try:
        ser.write(REQUEST_COMMAND)
        time.sleep(2)  # Mesmo timeout do script NUT
        response = ser.read(64)  # Le 64 bytes como no script NUT

        if len(response) == 0:
            print(f"[{reading_num}] SEM RESPOSTA")
            return False

        # Pega apenas primeiros 31 bytes (62 hex chars) como no script NUT
        hex_str = ''.join(f'{byte:02x}' for byte in response[:31])
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        print(f"\n{'='*80}")
        print(f"[{reading_num}] {timestamp} - ({len(response)} bytes recebidos)")
        print(f"{'='*80}")
        print(f"HEX (62 chars): {hex_str}")

        # Parseia valores como no script NUT
        if hex_str.startswith("aa25") and len(hex_str) >= 62:
            battery_charge_raw = int(hex_str[16:18], 16)
            battery_charge = min(100, round(battery_charge_raw * 0.393))

            battery_voltage = round(int(hex_str[22:24], 16) * 0.1342, 2)

            input_voltage_raw = int(hex_str[52:54], 16)
            input_voltage = round(input_voltage_raw * 1.009)

            output_voltage_raw = int(hex_str[60:62], 16)
            output_voltage = round(output_voltage_raw * 0.545)

            current_out_raw = int(hex_str[26:28], 16)
            current_out = round(current_out_raw * 0.120, 2)

            load = int(hex_str[28:30], 16)
            temperature = int(hex_str[30:32], 16)

            freq_raw = int(hex_str[48:50], 16)
            frequency = round(freq_raw * -0.1152 + 65, 2)

            print(f"\nVALORES PARSEADOS:")
            print(f"  Entrada:     {input_voltage:6.1f}V @ {frequency:5.2f}Hz [raw: {input_voltage_raw}]")
            print(f"  Saída:       {output_voltage:6.1f}V @ {current_out:5.2f}A")
            print(f"  Bateria:     {battery_charge:3d}% ({battery_voltage:5.2f}V) [raw: {battery_charge_raw}]")
            print(f"  Carga:       {load:3d}%")
            print(f"  Temperatura: {temperature:3d}°C")

            # Detecta status
            if input_voltage < 90:
                status = "🔋 ON BATTERY (OB)"
            else:
                status = "🔌 ON LINE (OL)"

            if battery_charge < 95 and input_voltage > 90:
                status += " + CHARGING"
            elif input_voltage < 90:
                status += " + DISCHARGING"

            print(f"  Status:      {status}")

        else:
            print(f"⚠️  Header inválido ou dados incompletos!")
            print(f"   Header: {hex_str[:4]} (esperado: aa25)")
            print(f"   Length: {len(hex_str)} chars (esperado: 62)")

        return True

    except Exception as e:
        print(f"[{reading_num}] ❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*80)
    print("RAGTECH NITROUP 2000VA - DUMP MODE")
    print("Chipset: Microchip PIC USB-Serial (04d8:000a)")
    print("Protocol: Binary aa25 (62 bytes)")
    print("="*80)
    print(f"Porta: {SERIAL_PORT}")
    print(f"Baud:  {BAUD_RATE}")
    print(f"Timeout: {TIMEOUT}s")
    print(f"\n📋 INSTRUÇÕES:")
    print("1. Script vai começar a ler a cada 5 segundos")
    print("2. ⚡ DESCONECTE DA TOMADA quando aparecer a primeira leitura")
    print("3. ⏱️  Deixe rodar por ~2 minutos (transição + descarga)")
    print("4. 🔌 RECONECTE NA TOMADA")
    print("5. ⏱️  Deixe mais 1 minuto (recarga)")
    print("6. Ctrl+C para parar")
    print("="*80)
    print("\n⏳ Aguardando 3 segundos para você se preparar...")
    time.sleep(3)

    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT) as ser:
            reading = 0
            print("\n🚀 INICIANDO LEITURAS... (AGUARDE PRIMEIRA LEITURA)\n")

            while True:
                reading += 1
                success = dump_reading(ser, reading)

                if reading == 1 and success:
                    print("\n" + "!"*80)
                    print("⚡ AGORA VOCÊ PODE DESCONECTAR DA TOMADA!")
                    print("!"*80 + "\n")

                time.sleep(5)  # Leitura a cada 5 segundos

    except KeyboardInterrupt:
        print("\n\n" + "="*80)
        print("✅ DUMP FINALIZADO")
        print("="*80)
    except Exception as e:
        print(f"\n❌ ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
