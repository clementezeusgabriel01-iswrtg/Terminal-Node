# TerminalNode

A lightweight peer-to-peer (P2P) terminal chat application written in pure Python using `asyncio`.  
Each instance of TerminalNode acts as both a **server** (accepting incoming connections) and a **client** (connecting to other nodes). Messages are framed with a 4-byte length header and exchanged as JSON payloads.

---

## Table of Contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Running the Application](#running-the-application)
5. [Usage & Commands](#usage--commands)
6. [How It Works](#how-it-works)
7. [Code Walkthrough (Line-by-Line Explanation)](#code-walkthrough-line-by-line-explanation)
8. [Protocol Details](#protocol-details)
9. [Example Session](#example-session)
10. [Limitations & Future Improvements](#limitations--future-improvements)
11. [License](#license)

---

## Features

- Fully asynchronous using Python’s built-in `asyncio`
- Simple length-prefixed framing (4-byte big-endian integer + JSON body)
- Unique 8-character node ID derived from host:port via SHA-256
- Interactive console with commands:
  - `/connect <host> <port>` – connect to another node
  - `/peers` – list currently connected peers
  - Any other text is broadcast to all connected peers
- Automatic cleanup of dead connections
- Works on localhost or across a network (provided firewall rules allow the chosen ports)

---

## Requirements

- **Python 3.7+** (asyncio features used are available from 3.7 onward; recommended 3.9+)
- No third-party packages required – only the Python standard library:
  - `asyncio`
  - `hashlib`
  - `json`
  - `sys`

---

## Installation

1. Clone or download the repository / copy the single file `terminal_node.py` to a directory of your choice.

2. (Optional but recommended) Create and activate a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate          # Linux / macOS
   # or
   venv\Scripts\activate             # Windows
   ```

3. No additional packages need to be installed.

---

## Running the Application

### Basic syntax

```bash
python terminal_node.py [host] [port]
```

| Argument | Default     | Description                                      |
|----------|-------------|--------------------------------------------------|
| `host`   | `127.0.0.1` | Interface to bind the listening socket to        |
| `port`   | `8888`      | Port on which the node will listen for peers     |

### Examples

**Start a node on the default host and port (127.0.0.1:8888):**

```bash
python terminal_node.py
```

**Start a node on a specific port:**

```bash
python terminal_node.py 127.0.0.1 9000
```

**Start a node that listens on all interfaces (useful for real network testing):**

```bash
python terminal_node.py 0.0.0.0 8888
```

You can run multiple instances on the same machine by choosing different ports:

```bash
# Terminal 1
python terminal_node.py 127.0.0.1 8888

# Terminal 2
python terminal_node.py 127.0.0.1 8889

# Terminal 3
python terminal_node.py 127.0.0.1 8890
```

---

## Usage & Commands

Once the node is running you will see a prompt:

```
[*] Node ID: a1b2c3d4
[*] Commands:
    /connect <host> <port>  - Connect to a peer node
    /peers                  - List active peer connections
    <your message>          - Broadcast text to all connected peers

> 
```

### Available commands

| Command                    | Description                                                                 |
|----------------------------|-----------------------------------------------------------------------------|
| `/connect <host> <port>`   | Actively connect to another TerminalNode instance                           |
| `/peers`                   | Print the list of currently connected peers                                 |
| Any other text             | Broadcast the text to **all** currently connected peers                     |
| `Ctrl+C`                   | Gracefully shut down the node                                               |

---

## How It Works

1. When the program starts it creates a TCP server that listens on the given host/port.
2. Simultaneously it runs an interactive console loop that reads user input.
3. Incoming connections are accepted and a background task is spawned for each peer to read framed messages.
4. When the user types a normal message, the node serializes it to JSON, prefixes it with a 4-byte length, and writes the frame to every connected peer.
5. When a peer disconnects (or an error occurs), the connection is removed from the peer list.

The design is intentionally minimal – there is no peer discovery, no encryption, no authentication, and no message history.

---

## Code Walkthrough (Line-by-Line Explanation)

```python
import asyncio
import hashlib
import json
import sys
```

- `asyncio` – provides the event loop, TCP server/client primitives, and concurrent task management.
- `hashlib` – used to generate a deterministic short node ID from the host:port string.
- `json` – serializes and deserializes the message payloads.
- `sys` – reads command-line arguments.

---

```python
class TerminalNode:

  def __init__(self, host, port):
    self.host = host
    self.port = port
    self.peers = {}  # {writer: peer_addr_str}
    # Generate a unique 8-character hex ID based on host/port
    self.node_id = hashlib.sha256(f"{host}:{port}".encode()).hexdigest()[:8]
```

- Stores the listening address.
- `self.peers` is a dictionary that maps each connected `StreamWriter` to a human-readable address string.  
  Using the writer object as the key makes it easy to remove a peer when the connection dies.
- The node ID is the first 8 characters of the SHA-256 hash of `"host:port"`.  
  This gives a short, unique-looking identifier without requiring any external coordination.

---

```python
  async def handle_connection(self, reader, writer):
    peer_addr = writer.get_extra_info("peername")
    self.peers[writer] = f"{peer_addr[0]}:{peer_addr[1]}"
    print(f"\n[+] Peer connected: {peer_addr[0]}:{peer_addr[1]}")
    print("> ", end="", flush=True)
```

- Called both for **incoming** connections (by the server) and for **outgoing** connections (after `connect_to_peer`).
- Registers the peer in the dictionary and prints a notification.
- The trailing `print("> ", end="", flush=True)` restores the console prompt after the notification.

```python
    try:
      while True:
        # 1. Read 4-byte big-endian length header
        raw_len = await reader.readexactly(4)
        length = int.from_bytes(raw_len, "big")

        # 2. Read the exact payload body
        payload = await reader.readexactly(length)
        msg = json.loads(payload.decode("utf-8"))

        sender = msg.get("sender", "Unknown")
        text = msg.get("text", "")
        print(f"\n[{sender}] {text}")
        print("> ", end="", flush=True)
```

- Infinite loop that reads framed messages.
- `readexactly(4)` guarantees we receive the full length header (or raise `IncompleteReadError` on disconnect).
- The length is interpreted as a big-endian unsigned 32-bit integer.
- Exactly that many bytes are then read for the JSON body.
- The message is decoded and printed, and the prompt is restored.

```python
    except asyncio.IncompleteReadError:
      pass
    except Exception as e:
      print(f"\n[-] Connection error with {peer_addr}: {e}")
    finally:
      self.peers.pop(writer, None)
      writer.close()
      await writer.wait_closed()
      print(f"\n[-] Peer disconnected: {peer_addr}")
      print("> ", end="", flush=True)
```

- `IncompleteReadError` is the normal way a peer signals that it has closed the connection.
- Any other exception is logged.
- The `finally` block always removes the peer from the dictionary and closes the writer cleanly.

---

```python
  async def connect_to_peer(self, host, port):
    try:
      reader, writer = await asyncio.open_connection(host, port)
      self.peers[writer] = f"{host}:{port}"
      print(f"\n[+] Successfully connected to peer {host}:{port}")
      # Spawn background task to listen for incoming frames from this peer
      asyncio.create_task(self.handle_connection(reader, writer))
    except Exception as e:
      print(f"\n[-] Connection failed to {host}:{port} -> {e}")
```

- Actively opens a TCP connection to another node.
- Immediately registers the writer and starts a background task that runs the same `handle_connection` logic used for incoming peers.
- Errors (connection refused, timeout, etc.) are reported to the console.

---

```python
  async def broadcast(self, text):
    msg = {"sender": self.node_id, "text": text}
    payload = json.dumps(msg).encode("utf-8")
    frame = len(payload).to_bytes(4, "big") + payload

    dead_writers = []
    for writer in list(self.peers.keys()):
      try:
        writer.write(frame)
        await writer.drain()
      except Exception:
        dead_writers.append(writer)

    for w in dead_writers:
      self.peers.pop(w, None)
```

- Builds a JSON message containing the local node ID and the text.
- Encodes it to UTF-8 and prefixes it with a 4-byte big-endian length.
- Iterates over a **copy** of the peers dictionary (`list(self.peers.keys())`) so that the dictionary can be safely modified while iterating.
- Writes the frame to every peer.  Any write that fails is recorded and later removed.

---

```python
  async def console_input_loop(self):
    loop = asyncio.get_running_loop()
    print(f"[*] Node ID: {self.node_id}")
    print("[*] Commands:")
    print("    /connect <host> <port>  - Connect to a peer node")
    print("    /peers                  - List active peer connections")
    print("    <your message>          - Broadcast text to all connected peers\n")

    while True:
      # Run blocking input() in an executor thread and strip stray '>' symbols
      line = await loop.run_in_executor(None, input, "> ")
      line = line.strip().lstrip(">").strip()
      if not line:
        continue

      if line.startswith("/connect "):
        parts = line.split()
        if len(parts) == 3:
          _, h, p = parts
          await self.connect_to_peer(h, int(p))
        else:
          print("[-] Usage: /connect <host> <port>")
      elif line == "/peers":
        print(f"[*] Active Peers ({len(self.peers)}):")
        for addr in self.peers.values():
          print(f"    - {addr}")
      else:
        await self.broadcast(line)
        print(f"[Me] {line}")
```

- Obtains the running event loop so that the blocking `input()` call can be off-loaded to a thread-pool executor.  
  This prevents the event loop from being blocked while waiting for keyboard input.
- Displays the help text once at startup.
- The input loop:
  - Strips whitespace and any accidental leading `>` characters.
  - Parses `/connect` and `/peers` commands.
  - Treats every other non-empty line as a broadcast message and also echoes it locally as `[Me]`.

---

```python
  async def start(self):
    server = await asyncio.start_server(
        self.handle_connection, self.host, self.port
    )
    addr = server.sockets[0].getsockname()
    print(f"[*] P2P Node listening on {addr[0]}:{addr[1]}")

    async with server:
      await asyncio.gather(server.serve_forever(), self.console_input_loop())
```

- Creates the TCP server that will call `handle_connection` for every new incoming connection.
- Prints the actual address the server is bound to (useful when binding to `0.0.0.0`).
- Runs the server and the console input loop concurrently with `asyncio.gather`.  
  The `async with server` context manager ensures the server is closed cleanly when the program exits.

---

```python
if __name__ == "__main__":
  host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
  port = int(sys.argv[2]) if len(sys.argv) > 2 else 8888

  try:
    asyncio.run(TerminalNode(host, port).start())
  except KeyboardInterrupt:
    print("\n[!] Shutting down node...")
```

- Parses optional command-line arguments with sensible defaults.
- Starts the asyncio event loop with `asyncio.run(...)`.
- Catches `KeyboardInterrupt` (Ctrl+C) so the program exits with a friendly message instead of a stack trace.

---

## Protocol Details

Every message on the wire has the following layout:

```
+----------------+---------------------------+
| 4 bytes        | N bytes                   |
| (big-endian)   | (UTF-8 JSON)              |
| length = N     | {"sender": "...", "text": "..."} |
+----------------+---------------------------+
```

- Length is an unsigned 32-bit integer in network byte order (big-endian).
- The JSON object always contains at least the keys `"sender"` (string) and `"text"` (string).
- There is currently no message type field, sequence number, or checksum.

---

## Example Session

**Terminal 1 (port 8888)**

```bash
$ python terminal_node.py 127.0.0.1 8888
[*] P2P Node listening on 127.0.0.1:8888
[*] Node ID: 7f8a9b2c
[*] Commands:
    /connect <host> <port>  - Connect to a peer node
    /peers                  - List active peer connections
    <your message>          - Broadcast text to all connected peers

> 
```

**Terminal 2 (port 8889)**

```bash
$ python terminal_node.py 127.0.0.1 8889
[*] P2P Node listening on 127.0.0.1:8889
[*] Node ID: 3d4e5f6a
...
> /connect 127.0.0.1 8888
[+] Successfully connected to peer 127.0.0.1:8888
```

**Back in Terminal 1**

```
[+] Peer connected: 127.0.0.1:xxxxx
> Hello from node 1!
[Me] Hello from node 1!
```

**Terminal 2 receives**

```
[7f8a9b2c] Hello from node 1!
```

---

## Limitations & Future Improvements

| Limitation                              | Possible Improvement                                      |
|-----------------------------------------|-----------------------------------------------------------|
| No peer discovery                       | Add a simple UDP broadcast / DHT / static peer list       |
| No encryption / authentication          | Add TLS or Noise protocol                                 |
| Single-threaded console input           | Use `aioconsole` or a richer TUI library                  |
| No message history / offline storage    | Persist messages to disk or a database                    |
| No rate limiting / flood protection     | Add simple token-bucket rate limiting                     |
| Node ID is derived only from host:port  | Allow a user-chosen nickname                              |
| No support for binary data              | Extend the protocol with message types                    |

---

## License

This project is provided as-is for educational purposes.  
Feel free to use, modify, and distribute it under the terms of the MIT License (or any other license you prefer).

---

**Happy chatting!**  
If you encounter bugs or have ideas for improvements, open an issue or submit a pull request.
