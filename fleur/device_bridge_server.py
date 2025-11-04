# device_bridge_server.py
# Run:  pip install flask flask-cors requests pyserial
#       python device_bridge_server.py
#
# ENV (optional):
#   BRIDGE_HOST=127.0.0.1
#   BRIDGE_PORT=9999
#   DJANGO_API=http://127.0.0.1:8000/api/payment/insert-event/
#   DJANGO_API_KEY=dev-secret
#   SIMULATE=1            # 1=simulate accept immediately, 0=use serial
#   SERIAL_PORT=COM3
#   SERIAL_BAUD=9600

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import time

# Optional serial (only used if SIMULATE=0)
try:
    import serial  # pyserial
except Exception:
    serial = None

app = Flask(__name__)
CORS(app)

# --- Config ---
BRIDGE_HOST   = os.getenv("BRIDGE_HOST", "127.0.0.1")
BRIDGE_PORT   = int(os.getenv("BRIDGE_PORT", "9999"))
DJANGO_API    = os.getenv("DJANGO_API", "http://127.0.0.1:8000/api/payment/insert-event/")
DJANGO_API_KEY= os.getenv("DJANGO_API_KEY", "dev-secret")
SIMULATE      = os.getenv("SIMULATE", "1") == "1"  # True by default
SERIAL_PORT   = os.getenv("SERIAL_PORT", "COM3")
SERIAL_BAUD   = int(os.getenv("SERIAL_BAUD", "9600"))

# Allowed bills in DA
ALLOWED_BILLS = {500, 1000, 2000}

# Simple in-memory session
current_payment_id = None

# Global serial handle (opened lazily)
_ser = None

def open_serial():
    global _ser
    if _ser or SIMULATE:
        return _ser
    if serial is None:
        raise RuntimeError("pyserial not installed; pip install pyserial (or set SIMULATE=1).")
    _ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=0.25)
    return _ser

def post_to_django(payment_id: int, amount: int):
    """Notify Django that a bill was accepted."""
    r = requests.post(
        DJANGO_API,
        json={"payment_id": payment_id, "amount": amount, "event": "bill_inserted"},
        headers={"X-Api-Key": DJANGO_API_KEY},
        timeout=3,
    )
    r.raise_for_status()
    return r.json()

def accept_bill_via_serial(amount: int) -> bool:
    """
    Placeholder for your TB74/TH50N serial logic:
    - Send commands to enable acceptor / stack escrow
    - Wait for device response that confirms the denomination
    - Return True only if the device confirms acceptance of *this* amount
    """
    ser = open_serial()
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # TODO: Replace with your actual protocol.
    # Example pseudo-flow:
    #
    # 1) Enable acceptor / set inhibit mask to allow 500/1000/2000
    #    ser.write(b'\xAA\x...')  # bytes per your device doc
    #
    # 2) Prompt stack escrow or wait for note detection
    #    start = time.time()
    #    denom_code = None
    #    while time.time() - start < 5:
    #        data = ser.read(64)          # read any available bytes
    #        # parse data to detect accepted denomination -> set denom_code
    #        if denom_code_detected:
    #            break
    #
    # 3) Map parsed denom_code to amount and compare with requested 'amount'
    #    if mapped_amount == amount:
    #        return True
    #
    # For now, simulate a tiny delay so UI feels real:
    time.sleep(0.8)
    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    return True

@app.get("/healthz")
def healthz():
    return "ok", 200

@app.get("/status")
def status():
    return jsonify({
        "ok": True,
        "simulate": SIMULATE,
        "payment_id": current_payment_id,
        "serial_port": SERIAL_PORT,
        "serial_baud": SERIAL_BAUD,
        "django_api": DJANGO_API,
    })

@app.post("/set-session")
def set_session():
    global current_payment_id
    data = request.get_json(silent=True) or {}
    pid = data.get("payment_id")
    if not isinstance(pid, int):
        return jsonify({"ok": False, "error": "payment_id required (int)"}), 400
    current_payment_id = pid
    return jsonify({"ok": True, "payment_id": current_payment_id})

@app.post("/stack")
def stack():
    """
    Request stacking a bill.
    JSON body: { "bill": 500|1000|2000, "payment_id": optional }
    Behavior:
      - In SIMULATE=1: immediately posts to Django and returns ok.
      - In SIMULATE=0: runs serial handshake and only posts to Django on success.
    """
    global current_payment_id
    data = request.get_json(silent=True) or {}
    try:
        bill = int(data.get("bill", 0))
    except Exception:
        return jsonify({"ok": False, "error": "bill must be int"}), 400

    pid = data.get("payment_id", current_payment_id)

    if bill not in ALLOWED_BILLS:
        return jsonify({"ok": False, "error": "unsupported bill"}), 400
    if not isinstance(pid, int):
        return jsonify({"ok": False, "error": "no payment_id set"}), 400

    try:
        if SIMULATE:
            # Simulate device acceptance delay
            time.sleep(0.4)
            dj = post_to_django(pid, bill)
            return jsonify({"ok": True, "mode": "simulate", "forwarded": dj})

        # SERIAL MODE
        ok = accept_bill_via_serial(bill)
        if not ok:
            return jsonify({"ok": False, "error": "bill rejected by device"}), 409

        dj = post_to_django(pid, bill)
        return jsonify({"ok": True, "mode": "serial", "forwarded": dj})

    except requests.RequestException as e:
        return jsonify({"ok": False, "error": f"django_api: {e}"}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    # Bind only locally for safety
    app.run(host=BRIDGE_HOST, port=BRIDGE_PORT, debug=False)


# device_bridge_server.py — extrait PSEUDO ID-003
import time

# Map "denomination code" -> montant DA (à ajuster selon ta table Algérie)
DENOM_MAP = {
    0x01: 500,
    0x02: 1000,
    0x03: 2000,
}

def id003_enable_only(ser, codes=(0x01, 0x02, 0x03)):
    """
    Envoie la commande ID-003 "Enable/Inhibit" pour autoriser uniquement les canaux passés.
    Les octets exacts dépendent du manuel ID-003 (format, checksum).
    Utilise Portalum.Id003 comme référence de dialogue si besoin.
    """
    # TODO: construire la trame Enable/Inhibit selon la spec ID-003
    # ser.write(b'\x..\x.. ... \xCHK')  # envoyer et vérifier ACK
    pass

def id003_read_status(ser, timeout=0.5):
    """
    Lis et parse les messages statut (dont ESCROW).
    Retourne par ex: ('ESCROW', code_denom) ou ('IDLE', None) etc.
    """
    start = time.time()
    buf = b""
    while time.time() - start < timeout:
        chunk = ser.read(64)
        if chunk:
            buf += chunk
            # TODO: parser selon framing ID-003 (header, length, payload, checksum)
            # if detected_escrow:
            #     return ('ESCROW', denom_code)
            # elif detected_other_state:
            #     ...
    return ('IDLE', None)

def id003_stack(ser):
    """Envoie la commande STACK (valide uniquement en ESCROW)."""
    # TODO: ser.write(STACK_CMD_BYTES) + lire ACK
    pass

def id003_return(ser):
    """Envoie la commande RETURN (rend le billet en ESCROW)."""
    # TODO: ser.write(RETURN_CMD_BYTES) + lire ACK
    pass

def accept_bill_via_serial(amount_expected: int) -> bool:
    """
    1) Enable uniquement 500/1000/2000
    2) Attendre ESCROW + code_denom
    3) Si DENOM_MAP[code] == amount_expected -> STACK, sinon RETURN
    4) Vérifier confirmation "BILL STACKED", renvoyer True si OK
    """
    ser = open_serial()
    id003_enable_only(ser, (0x01, 0x02, 0x03))  # tes 3 canaux

    # Boucle d’attente d’un billet en escrow
    t0 = time.time()
    while time.time() - t0 < 10:  # 10s max attente
        state, denom_code = id003_read_status(ser, timeout=0.5)
        if state == 'ESCROW' and denom_code in DENOM_MAP:
            value = DENOM_MAP[denom_code]
            if value == amount_expected:
                id003_stack(ser)
                # TODO: attendre message "STACKED" / "ACCEPTED"
                return True
            else:
                id003_return(ser)
                # Repart en attente
    return False


# device_bridge_server.py (add near the top with other config)
RELAY_SERIAL_PORT = os.getenv("RELAY_SERIAL_PORT", "COM4")
RELAY_SERIAL_BAUD = int(os.getenv("RELAY_SERIAL_BAUD", "9600"))
RELAY_PULSE_MS    = int(os.getenv("RELAY_PULSE_MS", "700"))  # how long to hold ON before OFF

_relay_ser = None

def open_relay_serial():
    global _relay_ser
    if SIMULATE:
        return None
    if serial is None:
        raise RuntimeError("pyserial not installed")
    if _relay_ser and _relay_ser.is_open:
        return _relay_ser
    _relay_ser = serial.Serial(RELAY_SERIAL_PORT, RELAY_SERIAL_BAUD, timeout=0.25)
    return _relay_ser

def relay_on_off_bytes(channel: int, on: bool) -> bytes:
    """
    TODO: replace with your relay board protocol.
    Examples you might see in practice:
      - Simple ASCII: b'RELAY%02d %s\\r\\n' % (channel, b'ON' if on else b'OFF')
      - Modbus RTU: Write Single Coil (0x05) with unit id + coil addr per channel.
      - Custom hex frames (vendor docs).
    For now, we just return a placeholder.
    """
    # Placeholder generic ASCII:
    cmd = f"CH{channel}:{'ON' if on else 'OFF'}\r\n"
    return cmd.encode("ascii")

def actuate_slot(channel: int, pulse_ms: int = RELAY_PULSE_MS) -> bool:
    """
    Toggle the relay for `channel` ON then OFF to open the door/solenoid.
    """
    if SIMULATE:
        # Simulate a small delay then success
        time.sleep(pulse_ms / 1000.0)
        return True

    ser = open_relay_serial()
    # Turn ON
    ser.write(relay_on_off_bytes(channel, True))
    ser.flush()
    time.sleep(pulse_ms / 1000.0)
    # Turn OFF
    ser.write(relay_on_off_bytes(channel, False))
    ser.flush()
    return True

# === NEW endpoint ===
@app.post("/open-slot")
def open_slot():
    """
    Body JSON: { "channel": 1..12 }
    Pulses the relay for that channel to open the slot case.
    """
    data = request.get_json(silent=True) or {}
    ch = int(data.get("channel", 0))
    if ch < 1 or ch > 12:
        return jsonify({"ok": False, "error": "channel must be 1..12"}), 400
    try:
        ok = actuate_slot(ch)
        if not ok:
            return jsonify({"ok": False, "error": "actuation failed"}), 500
        return jsonify({"ok": True, "channel": ch})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
