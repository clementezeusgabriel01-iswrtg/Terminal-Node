import asyncio
import hashlib
import json
import sys


class TerminalNode:

  def __init__(self, host, port):
    self.host = host
    self.port = port
    self.peers = {}  # {writer: peer_addr_str}
    # Generate a unique 8-character hex ID based on host/port
    self.node_id = hashlib.sha256(f"{host}:{port}".encode()).hexdigest()[:8]

  async def handle_connection(self, reader, writer):
    peer_addr = writer.get_extra_info("peername")
    self.peers[writer] = f"{peer_addr[0]}:{peer_addr[1]}"
    print(f"\n[+] Peer connected: {peer_addr[0]}:{peer_addr[1]}")
    print("> ", end="", flush=True)

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

  async def connect_to_peer(self, host, port):
    try:
      reader, writer = await asyncio.open_connection(host, port)
      self.peers[writer] = f"{host}:{port}"
      print(f"\n[+] Successfully connected to peer {host}:{port}")
      # Spawn background task to listen for incoming frames from this peer
      asyncio.create_task(self.handle_connection(reader, writer))
    except Exception as e:
      print(f"\n[-] Connection failed to {host}:{port} -> {e}")

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

  async def start(self):
    server = await asyncio.start_server(
        self.handle_connection, self.host, self.port
    )
    addr = server.sockets[0].getsockname()
    print(f"[*] P2P Node listening on {addr[0]}:{addr[1]}")

    async with server:
      await asyncio.gather(server.serve_forever(), self.console_input_loop())


if __name__ == "__main__":
  host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
  port = int(sys.argv[2]) if len(sys.argv) > 2 else 8888

  try:
    asyncio.run(TerminalNode(host, port).start())
  except KeyboardInterrupt:
    print("\n[!] Shutting down node...")
