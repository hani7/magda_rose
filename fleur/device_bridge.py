# device_bridge.py RS32
import code
import serial, time, requests, argparse

from fleur.device_bridge_server import post_to_django # type: ignore

# CONFIG
API_URL = "http://127.0.0.1:8000/api/payment/insert-event/"
API_KEY = "dev-secret"

# mapping code reçu -> montant en DA
DENOM_MAP = {
    0x01: 500,    # à ajuster selon ta table DZD
    0x02: 1000,
    0x03: 2000,
}
# si escrow -> stack, puis quand device confirme "stacked" avec code 0x02 :
amount = DENOM_MAP.get(code)
if amount in (500, 1000, 2000):
    post_to_django(payment_id, amount) # type: ignore
    
def post_amount(payment_id, amount):
    requests.post(API_URL, json={
        "payment_id": payment_id,
        "amount": amount,
        "event": "bill_inserted",
    }, headers={"X-Api-Key": API_KEY}, timeout=2)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--com", default="COM3")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--payment", type=int, required=True, help="Payment ID en cours")
    args = ap.parse_args()

    with serial.Serial(args.com, args.baud, timeout=0.1) as ser:
        print(f"[bridge] listening on {args.com} @ {args.baud}, payment={args.payment}")
        while True:
            b = ser.read(1)
            if not b:
                time.sleep(0.01)
                continue
            # Ex: chaque octet code une dénomination
            amount = DENOM_MAP.get(b)
            if amount:
                print(f"[bridge] +{amount} DA")
                try:
                    post_amount(args.payment, amount)
                except Exception as e:
                    print("[bridge] post failed:", e)

if __name__ == "__main__":
    main()
