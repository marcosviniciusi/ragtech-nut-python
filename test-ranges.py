#!/usr/bin/env python3
"""
Test additional command ranges for Ragtech NitroUp 2000VA
Based on devices.xml Family 10 ranges
"""

import serial
import time
import sys

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 2560
TIMEOUT = 20

# Comandos baseados em devices.xml Family 10
COMMANDS = {
    "current": {
        "desc": "Range 0x80 (30 bytes) - ATUAL",
        "cmd": bytes.fromhex("AA0400801E9E"),
        "expected_size": 31,  # aa + response_type + 30 bytes
    },
    "calibration": {
        "desc": "Range 0xF3 (1 byte) - Calibração corrente",
        "cmd": bytes.fromhex("AA0400F301F4"),
        "expected_size": 2,  # aa + 1 byte
    },
    "capacity": {
        "desc": "Range 0x136 (1 byte) - CAPACIDADE BATERIA ⭐",
        "cmd": bytes.fromhex("AA04013601") + bytes([0x37]),  # Checksum: 0x36 + 0x01 = 0x37
        "expected_size": 2,
    },
    "rgb": {
        "desc": "Range 0x171 (4 bytes) - RGB LED",
        "cmd": bytes.fromhex("AA04017104") + bytes([0x75]),  # Checksum: 0x71 + 0x04 = 0x75
        "expected_size": 5,  # aa + 4 bytes
    },
}

def test_command(name, info):
    """Test a single command"""
    print(f"\n{'='*70}")
    print(f"TESTANDO: {info['desc']}")
    print(f"{'='*70}")

    cmd_hex = ' '.join(f'{b:02X}' for b in info['cmd'])
    print(f"Comando: {cmd_hex}")
    print(f"Esperado: ~{info['expected_size']} bytes")

    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT) as ser:
            # Enviar comando
            ser.write(info['cmd'])
            print(f"✓ Comando enviado")

            # Aguardar resposta
            time.sleep(2)

            # Ler resposta
            response = ser.read(64)

            if len(response) == 0:
                print(f"✗ Nenhuma resposta!")
                return None

            # Mostrar resposta
            resp_hex = ' '.join(f'{b:02X}' for b in response[:min(len(response), 20)])
            print(f"✓ Resposta ({len(response)} bytes): {resp_hex}")

            # Análise
            if len(response) >= 2:
                header = f"{response[0]:02x}{response[1]:02x}"
                print(f"  Header: {header}")

                if response[0] == 0xaa:
                    print(f"  ✓ Start marker correto (0xaa)")

                    if name == "capacity" and len(response) >= 3:
                        capacity_raw = response[2]
                        print(f"\n  🔋 CAPACIDADE RAW: {capacity_raw} (0x{capacity_raw:02X})")
                        print(f"  🔋 Possíveis interpretações:")
                        print(f"     - Direto: {capacity_raw} Ah")
                        print(f"     - × 10: {capacity_raw * 10} Ah")
                        print(f"     - × 0.1: {capacity_raw * 0.1} Ah")
                        print(f"     - Binary: {capacity_raw:08b}")

                    elif name == "calibration" and len(response) >= 3:
                        calib_raw = response[2]
                        print(f"\n  ⚙️ CALIBRAÇÃO RAW: {calib_raw} (0x{calib_raw:02X})")

                    elif name == "rgb" and len(response) >= 6:
                        rgb = response[2:6]
                        print(f"\n  🌈 RGB LED:")
                        print(f"     Byte 1: {rgb[0]:02X} ({rgb[0]})")
                        print(f"     Byte 2: {rgb[1]:02X} ({rgb[1]})")
                        print(f"     Byte 3: {rgb[2]:02X} ({rgb[2]})")
                        print(f"     Byte 4: {rgb[3]:02X} ({rgb[3]})")
                else:
                    print(f"  ⚠️ Start marker diferente: 0x{response[0]:02X}")

            return response

    except serial.SerialException as e:
        print(f"✗ Erro serial: {e}")
        return None
    except Exception as e:
        print(f"✗ Erro: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("="*70)
    print("TESTE DE RANGES ADICIONAIS - Ragtech NitroUp 2000VA")
    print("="*70)
    print(f"\nPorta: {SERIAL_PORT}")
    print(f"Baudrate: {BAUD_RATE}")

    results = {}

    # Testar comando atual (baseline)
    print(f"\n{'#'*70}")
    print("BASELINE - Comando atual (deve funcionar)")
    print(f"{'#'*70}")
    results['current'] = test_command('current', COMMANDS['current'])

    if results['current'] is None:
        print("\n✗ Comando baseline falhou! Abortando.")
        sys.exit(1)

    # Testar novos comandos
    for name in ['capacity', 'calibration', 'rgb']:
        print(f"\n{'#'*70}")
        print(f"NOVO COMANDO - {name.upper()}")
        print(f"{'#'*70}")
        results[name] = test_command(name, COMMANDS[name])
        time.sleep(1)  # Delay entre comandos

    # Resumo
    print(f"\n{'='*70}")
    print("RESUMO DOS TESTES")
    print(f"{'='*70}")

    for name, info in COMMANDS.items():
        status = "✓ OK" if results.get(name) else "✗ FALHOU"
        size = len(results[name]) if results.get(name) else 0
        print(f"{info['desc']:40s} {status:10s} ({size} bytes)")

    # Análise especial: capacidade
    if results.get('capacity'):
        print(f"\n{'='*70}")
        print("ANÁLISE: CAPACIDADE DA BATERIA")
        print(f"{'='*70}")

        resp = results['capacity']
        if len(resp) >= 3:
            cap_raw = resp[2]
            print(f"\nValor bruto: {cap_raw} (0x{cap_raw:02X})")
            print(f"\nCapacidade configurada no driver: 40 Ah")
            print(f"Valor lido do nobreak: {cap_raw} Ah")

            if cap_raw == 40:
                print(f"\n✓✓✓ MATCH PERFEITO! Nobreak detectou 40Ah!")
            elif cap_raw == 4:
                print(f"\n⚠️ Possível escala ×10 (4 × 10 = 40 Ah)")
            elif cap_raw == 0:
                print(f"\n✗ Retornou 0 (não detecta capacidade)")
            else:
                print(f"\n⚠️ Valor diferente do esperado (40 Ah)")

    print()

if __name__ == "__main__":
    main()
