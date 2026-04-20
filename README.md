# Real-Time Bidding (Auction) — TCP + Web UI

A simple real-time auction/bidding system built with:
- **Python** backend
  - **TCP server over TLS/SSL** for command-line bidders
  - **HTTP server** that serves a small **React (CDN) web UI** + JSON APIs
- **Frontend**: plain HTML/CSS + React via UMD builds (no build step)

## Features
- Start an auction by entering an **item name** and **base price**
- Accept bids from:
  - **Web UI** (HTTP API)
  - **CLI TCP clients** (TLS-wrapped socket)
- Tracks:
  - current highest bid + bidder
  - auction active/ended state
  - remaining time (timer resets on each valid highest bid)
  - a small in-memory event log

## Project structure
- `server.py` — main server (TCP + HTTP + auction logic)
- `client.py` — CLI bidder client (TLS socket)
- `frontend/`
  - `index.html` — loads React from CDN and mounts the app
  - `app.js` — UI + polling / bid submission logic
  - `styles.css` — styling
- `cert.pem`, `key.pem` — TLS certificate and key used by the TCP server

## Prerequisites
- Python 3.9+ (should work on most Python 3 versions)
- No pip dependencies required (uses Python standard library)

## Run the server
1. Start the server:
   ```bash
   python server.py
   ```

2. When prompted, enter:
   - the item being auctioned
   - the base price (non-negative integer)

3. Open the web UI in your browser:
   - `http://127.0.0.1:8000`

Server ports (defaults from `server.py`):
- HTTP: `8000`
- TCP (TLS): `5000`

## Bid from the web UI
- Open `http://127.0.0.1:8000`
- Enter your name and bid amount
- The UI fetches auction state from:
  - `GET /api/state`
- It submits bids via:
  - `POST /api/bid` with JSON: `{ "name": "...", "bid": 123 }`

## Bid from the CLI client (TCP over TLS)
Run in a separate terminal (same machine or another machine on the network):

```bash
python client.py
```

- Enter server IP (defaults to `127.0.0.1`)
- Enter your name
- Enter bids as numbers
- Type `quit` to exit

### Notes for LAN usage
- The server prints an IP hint: **“Use IP: <server-ip> and port 5000”**
- Ensure your firewall allows inbound connections to:
  - `8000` (HTTP) and `5000` (TCP/TLS)

## Auction rules / behavior
- Auction duration is **150 seconds** (`AUCTION_DURATION = 150`)
- Timer starts when the auction starts and **resets** whenever a new highest bid is accepted
- Base price rule:
  - If there is no highest bidder yet, bids must be **>= base price**
- New bids must be **strictly greater** than the current highest bid
- When time runs out, the auction ends and:
  - announces the winner (or no valid bids)
  - disconnects TCP clients

## Security note (important)
This repo includes `cert.pem` and `key.pem` and the client disables certificate verification for local/self-signed testing:
- `context.check_hostname = False`
- `context.verify_mode = ssl.CERT_NONE`

For production-like usage, you should generate your own certificates and enable proper verification.

## Troubleshooting
- **Port already in use**: change `HTTP_PORT` or `TCP_PORT` in `server.py`
- **Other devices can’t connect**:
  - use the server machine’s LAN IP (not `127.0.0.1`)
  - open firewall for ports 8000/5000
- **TLS errors**: regenerate `cert.pem` / `key.pem` or ensure they match and are readable
