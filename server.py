import socket
import threading
import time

HOST = "0.0.0.0"
PORT = 5000
AUCTION_DURATION = 45

clients = []
highest_bid = 0
highest_bidder = None
auction_active = True
auction_end_time = None
item_name = ""
base_price = 0
lock = threading.Lock()


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
                    message = (
                        f"\n[AUCTION ENDED] No valid bids were placed for {item_name}.\n"
                    )
                break

        time.sleep(min(remaining_time, 0.5))

    print(message.strip())
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
    global highest_bid, highest_bidder, auction_end_time

    try:
        conn.send(
            (
                f"Auction for {item_name} is live for {AUCTION_DURATION} seconds.\n"
                f"Base price: Rs.{base_price}\n"
                "Enter bid amounts only.\n"
            ).encode()
        )

        while True:
            data = conn.recv(1024).decode().strip()

            if not data:
                break

            with lock:
                if not auction_active:
                    conn.send("Auction has ended. No more bids are accepted.\n".encode())
                    break

            try:
                name, bid_text = data.split(":", 1)
                bid = int(bid_text)
            except ValueError:
                conn.send("Invalid bid received.\n".encode())
                continue

            with lock:
                if not auction_active:
                    conn.send("Auction has ended. No more bids are accepted.\n".encode())
                    break

                if highest_bidder is None and bid < base_price:
                    conn.send(
                        f"Bid too low. Base price for {item_name} is Rs.{base_price}\n".encode()
                    )
                    continue

                if bid > highest_bid:
                    highest_bid = bid
                    highest_bidder = name
                    auction_end_time = time.time() + AUCTION_DURATION
                    msg = (
                        f"New highest bid for {item_name}: Rs.{bid} by {name}. "
                        f"Timer reset to {AUCTION_DURATION} seconds.\n"
                    )
                    print(msg.strip())
                    broadcast(msg)
                else:
                    conn.send(
                        f"Bid too low. Current highest for {item_name}: Rs.{highest_bid}\n".encode()
                    )
    except OSError:
        pass
    finally:
        if conn in clients:
            clients.remove(conn)
        conn.close()


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

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    server.settimeout(0.5)

    print(f"[SERVER STARTED] on {HOST}:{PORT}")
    print(f"[CONNECT FROM OTHER PCS] Use IP: {get_server_ip()} and port {PORT}")
    print(f"[ITEM] {item_name}")
    print(f"[BASE PRICE] Rs.{base_price}")
    print(f"[AUCTION] Ends automatically in {AUCTION_DURATION} seconds")

    auction_end_time = time.time() + AUCTION_DURATION

    timer_thread = threading.Thread(target=close_auction, daemon=True)
    timer_thread.start()

    while True:
        with lock:
            if not auction_active:
                break

        try:
            conn, addr = server.accept()
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


if __name__ == "__main__":
    start_server()
