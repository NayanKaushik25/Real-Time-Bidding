import socket
import threading
import sys

HOST = "127.0.0.1"
PORT = 5000


def receive_messages(sock, stop_event):
    while not stop_event.is_set():
        try:
            msg = sock.recv(1024).decode()
            if not msg:
                break

            print("\r" + " " * 80 + "\r", end="")
            print(msg, end="")

            if "[AUCTION ENDED]" in msg or "Auction has already ended." in msg:
                stop_event.set()
                break

            print("Enter your bid amount (or type quit): ", end="", flush=True)
        except OSError:
            break

    stop_event.set()


def start_client():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((HOST, PORT))

    stop_event = threading.Event()
    name = input("Enter your name: ").strip()

    thread = threading.Thread(
        target=receive_messages, args=(client, stop_event), daemon=True
    )
    thread.start()

    try:
        while not stop_event.is_set():
            bid = input("Enter your bid amount (or type quit): ").strip()

            if stop_event.is_set():
                break

            if bid.lower() == "quit":
                break

            if not bid.isdigit():
                print("Enter numbers only for the bid amount.")
                continue

            client.send(f"{name}:{bid}".encode())
    except OSError:
        pass
    finally:
        stop_event.set()
        client.close()


if __name__ == "__main__":
    start_client()
