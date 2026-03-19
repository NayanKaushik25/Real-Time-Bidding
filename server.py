import socket
import threading

HOST = '127.0.0.1'
PORT = 5000

clients = []
highest_bid = 0
highest_bidder = None
lock = threading.Lock()


def broadcast(message):
    for client in clients:
        try:
            client.send(message.encode())
        except:
            clients.remove(client)


def handle_client(conn, addr):
    global highest_bid, highest_bidder

    while True:
        try:
            data = conn.recv(1024).decode().strip()

            if not data:
                break

            name, bid = data.split(":")
            bid = int(bid)

            with lock:
                if bid > highest_bid:
                    highest_bid = bid
                    highest_bidder = name

                    msg = f"New highest bid: ₹{bid} by {name}\n"
                    print(msg)
                    broadcast(msg)
                else:
                    conn.send(
                        f"Bid too low. Current highest: ₹{highest_bid}\n".encode()
                    )

        except:
            break


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()

    print(f"[SERVER STARTED] on {HOST}:{PORT}")

    while True:
        conn, addr = server.accept()
        clients.append(conn)

        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()


if __name__ == "__main__":
    start_server()