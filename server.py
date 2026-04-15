import json
import socket
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import ssl

HOST = "0.0.0.0"
TCP_PORT = 5000
HTTP_PORT = 8000
AUCTION_DURATION = 150
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"

clients = []
highest_bid = 0
highest_bidder = None
auction_active = True
auction_end_time = None
item_name = ""
base_price = 0
event_log = []
lock = threading.Lock()


def record_event(message):
    timestamp = time.strftime("%H:%M:%S")
    event_log.append({"time": timestamp, "message": message.strip()})
    del event_log[:-25]


def broadcast(message):
    disconnected_clients = []

    for client in clients:
        try:
            client.send(message.encode())
        except OSError:
            disconnected_clients.append(client)

    for client in disconnected_clients:
        if client in clients:
            clients.remove(client)


def get_server_ip():
    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except OSError:
        return "Unable to detect automatically"


def get_auction_state():
    with lock:
        remaining_time = max(0, int(auction_end_time - time.time())) if auction_end_time else 0
        return {
            "itemName": item_name,
            "basePrice": base_price,
            "highestBid": highest_bid,
            "highestBidder": highest_bidder,
            "auctionActive": auction_active,
            "remainingTime": remaining_time,
            "auctionDuration": AUCTION_DURATION,
            "events": list(event_log),
        }


def submit_bid(name, bid):
    global highest_bid, highest_bidder, auction_end_time

    clean_name = name.strip()
    if not clean_name:
        return False, "Please enter your name."

    if bid < 0:
        return False, "Bid must be a non-negative whole number."

    with lock:
        if not auction_active:
            return False, "Auction has ended. No more bids are accepted."

        if highest_bidder is None and bid < base_price:
            return False, f"Bid too low. Base price for {item_name} is Rs.{base_price}"

        if bid <= highest_bid:
            return False, f"Bid too low. Current highest for {item_name}: Rs.{highest_bid}"

        highest_bid = bid
        highest_bidder = clean_name
        auction_end_time = time.time() + AUCTION_DURATION

    message = (
        f"New highest bid for {item_name}: Rs.{bid} by {clean_name}. "
        f"Timer reset to {AUCTION_DURATION} seconds.\n"
    )
    print(message.strip())
    record_event(message)
    broadcast(message)
    return True, message.strip()


def close_auction():
    global auction_active
    while True:
        with lock:
            if not auction_active:
                return

            remaining_time = auction_end_time - time.time()
            if remaining_time <= 0:
                auction_active = False
                if highest_bidder is not None:
                    message = (
                        f"\n[AUCTION ENDED] {item_name} sold to {highest_bidder} for Rs.{highest_bid}\n"
                    )
                else:
                    message = f"\n[AUCTION ENDED] No valid bids were placed for {item_name}.\n"
                break

        time.sleep(min(remaining_time, 0.5))

    print(message.strip())
    record_event(message)
    broadcast(message)

    for client in clients[:]:
        try:
            client.close()
        except OSError:
            pass
        finally:
            if client in clients:
                clients.remove(client)


def handle_client(conn, addr):
    try:
        conn.send(
            (
                f"Auction for {item_name} is live for {AUCTION_DURATION} seconds.\n"
                f"Base price: Rs.{base_price}\n"
                "Enter bids as name:amount\n"
            ).encode()
        )

        while True:
            data = conn.recv(1024).decode().strip()

            if not data:
                break

            try:
                name, bid_text = data.split(":", 1)
                bid = int(bid_text)
            except ValueError:
                conn.send("Invalid bid received.\n".encode())
                continue

            success, response = submit_bid(name, bid)
            if not success:
                conn.send(f"{response}\n".encode())
                if response.startswith("Auction has ended"):
                    break
    except OSError:
        pass
    finally:
        if conn in clients:
            clients.remove(conn)
        conn.close()


class AuctionHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            self._send_json(get_auction_state())
            return

        self._serve_static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/bid":
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body or b"{}")
            name = str(payload.get("name", ""))
            bid = int(payload.get("bid", -1))
        except (ValueError, json.JSONDecodeError):
            self._send_json(
                {"ok": False, "message": "Please send a valid name and numeric bid."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        success, message = submit_bid(name, bid)
        status = HTTPStatus.OK if success else HTTPStatus.BAD_REQUEST
        self._send_json({"ok": success, "message": message, "state": get_auction_state()}, status)

    def log_message(self, format, *args):
        return

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, request_path):
        relative_path = request_path.lstrip("/") or "index.html"
        if relative_path == "":
            relative_path = "index.html"

        candidate = (FRONTEND_DIR / relative_path).resolve()
        try:
            candidate.relative_to(FRONTEND_DIR.resolve())
        except ValueError:
            self._send_json({"error": "Forbidden"}, status=HTTPStatus.FORBIDDEN)
            return

        if not candidate.exists() or not candidate.is_file():
            candidate = FRONTEND_DIR / "index.html"

        content_type = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
        }.get(candidate.suffix.lower(), "application/octet-stream")

        body = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_http_server():
    http_server = ThreadingHTTPServer((HOST, HTTP_PORT), AuctionHTTPRequestHandler)
    print(f"[WEB CLIENT] Open http://127.0.0.1:{HTTP_PORT} in your browser")
    http_server.serve_forever()


def start_tcp_server():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile="cert.pem", keyfile="key.pem")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, TCP_PORT))
    server.listen()
    server.settimeout(0.5)

    print(f"[TCP SERVER STARTED WITH SSL] on {HOST}:{TCP_PORT}")
    print(f"[CONNECT FROM OTHER PCS] Use IP: {get_server_ip()} and port {TCP_PORT}")
    print(f"[ITEM] {item_name}")
    print(f"[BASE PRICE] Rs.{base_price}")
    print(f"[AUCTION] Ends automatically in {AUCTION_DURATION} seconds")

    while True:
        with lock:
            if not auction_active:
                break

        try:
            raw_conn, addr = server.accept()
            try:
                conn = context.wrap_socket(raw_conn, server_side=True)
            except ssl.SSLError:
                raw_conn.close()
                continue
        except socket.timeout:
            continue

        with lock:
            if not auction_active:
                conn.send("Auction has already ended.\n".encode())
                conn.close()
                continue

            clients.append(conn)

        thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        thread.start()

    server.close()


def start_server():
    global item_name, base_price, auction_end_time

    item_name = input("Enter the item being auctioned: ").strip() or "Unnamed item"

    while True:
        base_price_text = input("Enter the base price: ").strip()
        try:
            base_price = int(base_price_text)
            if base_price < 0:
                raise ValueError
            break
        except ValueError:
            print("Please enter a non-negative whole number for the base price.")

    auction_end_time = time.time() + AUCTION_DURATION
    record_event(
        f"Auction started for {item_name}. Base price is Rs.{base_price}. "
        f"Initial timer is {AUCTION_DURATION} seconds."
    )

    timer_thread = threading.Thread(target=close_auction, daemon=True)
    timer_thread.start()

    web_thread = threading.Thread(target=start_http_server, daemon=True)
    web_thread.start()

    start_tcp_server()


if __name__ == "__main__":
    start_server()
