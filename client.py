
"""Interactive two-player Battleship client for the TCP Battleship server."""

import argparse
import json
import socket
import sys
import threading

SHIPS = {"Carrier": 5, "Battleship": 4, "Cruiser": 3,
         "Submarine": 3, "Destroyer": 2}


def valid_port(text):
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1024 <= value <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1024 and 65535")
    return value


def send(sock, message):
    sock.sendall((json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8"))


def show_board(title, board):
    print(f"\n{title}")
    print("    " + " ".join(str(i) for i in range(10)))
    for row, cells in enumerate(board):
        print(f"{row:>2}  " + " ".join(cells))
    print("Legend: S = your ship, X = hit, o = miss, . = unknown/water")


class Client:
    def __init__(self, sock):
        self.sock = sock
        self.cv = threading.Condition()
        self.player_id = None
        self.placing = False
        self.placed = 0
        self.game_started = False
        self.my_turn = False
        self.over = False
        self.waiting_response = False
        self.error = None
        self.own_board = None
        self.target_board = None

    def process(self, msg):
        kind = msg.get("msg_type")
        with self.cv:
            if kind == "LOBBY_WAIT":
                if msg.get("player_id"):
                    self.player_id = msg["player_id"]
                self.placed = msg.get("ships_placed", self.placed)
                self.placing = "Place your five ships" in msg.get("message", "") or (
                    "Placed " in msg.get("message", ""))
                if "Opponent left" in msg.get("message", ""):
                    self.game_started = False
                    self.placing = False
                self.waiting_response = False
                print(f"\n[{self.player_id}] {msg.get('message', '')}", flush=True)
            elif kind == "GAME_START":
                self.game_started = True
                self.placing = False
                self.my_turn = self.player_id == msg.get("first_turn")
                print("\nGame started! Player_1 goes first.", flush=True)
            elif kind == "STATE_UPDATE":
                self.own_board = msg.get("own_board")
                self.target_board = msg.get("target_board")
                self.my_turn = self.player_id == msg.get("active_player")
                last = msg.get("last_move")
                if last:
                    print(f"\n{last['player_id']} attacked ({last['row']}, {last['col']}): "
                          f"{last['result']}{' (' + last['ship'] + ')' if 'ship' in last else ''}",
                          flush=True)
                print(f"Score: {msg.get('hits', 0)} hits, {msg.get('misses', 0)} misses, "
                      f"{msg.get('ships_sunk', 0)} ships sunk. "
                      f"{'Your turn!' if self.my_turn else 'Waiting for opponent...'}",
                      flush=True)
                self.waiting_response = False
            elif kind == "ERROR":
                self.error = msg.get("message", "Unknown error")
                self.waiting_response = False
                print(f"\n[ERROR] {self.error}", flush=True)
                if msg.get("error_code") in ("ROOM_FULL", "HANDSHAKE"):
                    self.over = True
            elif kind == "GAME_OVER":
                self.over = True
                self.waiting_response = False
                print(f"\nGAME OVER! Winner: {msg.get('winner')}; "
                      f"reason: {msg.get('reason')}", flush=True)
                print("Final scores:", json.dumps(msg.get("final_scores", {}), indent=2),
                      flush=True)
            else:
                print(f"\n[WARNING] Unexpected server message: {kind}", flush=True)
            self.cv.notify_all()

    def receive(self):
        buffer = bytearray()
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buffer.extend(chunk)
                if len(buffer) > 65536 and b"\n" not in buffer:
                    print("\n[ERROR] Server message too large.", flush=True)
                    break
                while b"\n" in buffer:
                    raw, _, rest = buffer.partition(b"\n")
                    buffer = bytearray(rest)
                    try:
                        msg = json.loads(raw.decode("utf-8"))
                        if isinstance(msg, dict):
                            self.process(msg)
                    except (ValueError, UnicodeDecodeError):
                        print("\n[ERROR] Malformed server message.", flush=True)
        except OSError:
            pass
        finally:
            with self.cv:
                if not self.over:
                    print("\n[DISCONNECTED] Server connection closed.", flush=True)
                self.over = True
                self.waiting_response = False
                self.cv.notify_all()

    def await_event(self, condition):
        with self.cv:
            self.cv.wait_for(lambda: self.over or condition())
            return not self.over

    def ask_coordinate(self, prompt):
        while True:
            answer = input(prompt).strip().replace(",", " ").split()
            if len(answer) == 2:
                try:
                    row, col = map(int, answer)
                    if 0 <= row <= 9 and 0 <= col <= 9:
                        return row, col
                except ValueError:
                    pass
            print("Enter two numbers from 0 to 9 (example: 3 5).")

    def run(self):
        threading.Thread(target=self.receive, daemon=True).start()
        if not self.await_event(lambda: self.player_id is not None):
            return
        print("To quit at a prompt, press Ctrl+C.")
        ship_names = list(SHIPS)
        while True:
            if not self.await_event(lambda: self.placing or self.game_started):
                return
            if self.game_started:
                break
            with self.cv:
                index = self.placed
                player_id = self.player_id
            if index >= len(ship_names):
                self.await_event(lambda: self.game_started or not self.placing)
                continue
            ship = ship_names[index]
            print(f"\nPlace {ship} (length {SHIPS[ship]}) [{index + 1}/5]")
            row, col = self.ask_coordinate("Starting row and col (0-9): ")
            direction = input("Direction (h = horizontal, v = vertical): ").strip().lower()
            if direction not in ("h", "v", "horizontal", "vertical"):
                print("Use h or v.")
                continue
            direction = "horizontal" if direction.startswith("h") else "vertical"
            with self.cv:
                self.error = None
                self.waiting_response = True
            send(self.sock, {"msg_type": "PLACE_SHIP", "player_id": player_id,
                             "ship": ship, "row": row, "col": col,
                             "direction": direction})
            if not self.await_event(lambda: not self.waiting_response):
                return

        while True:
            if not self.await_event(lambda: self.my_turn):
                return
            with self.cv:
                if self.own_board is not None:
                    show_board("Your fleet", self.own_board)
                if self.target_board is not None:
                    show_board("Your attacks", self.target_board)
                player_id = self.player_id
            row, col = self.ask_coordinate("\nYOUR TURN - attack row and col: ")
            with self.cv:
                self.error = None
                self.waiting_response = True
            send(self.sock, {"msg_type": "MOVE", "player_id": player_id,
                             "row": row, "col": col})
            if not self.await_event(lambda: not self.waiting_response):
                return
            # On ERROR, it is still your turn. On STATE_UPDATE, turn changed.


def main():
    parser = argparse.ArgumentParser(description="Two-player Battleship TCP client")
    parser.add_argument("-i", "--hostname", required=True,
                        help="Server DNS hostname or IP address")
    parser.add_argument("-p", "--port", required=True, type=valid_port,
                        help="Server TCP port (1024-65535)")
    args = parser.parse_args()
    try:
        server_ip = socket.gethostbyname(args.hostname)
    except socket.gaierror:
        print(f"[ERROR] Unable to resolve DNS hostname '{args.hostname}'.")
        print("Check the hostname or Cisco router DNS configuration (ip dns server / ip host).")
        sys.exit(1)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(10)
            sock.connect((server_ip, args.port))
            sock.settimeout(None)
            print(f"Connected to {args.hostname} ({server_ip}):{args.port}")
            send(sock, {"msg_type": "CONNECT", "player_id": "Unassigned"})
            client = Client(sock)
            try:
                client.run()
            except (KeyboardInterrupt, EOFError):
                print("\nDisconnecting...")
                try:
                    send(sock, {"msg_type": "DISCONNECT",
                                "player_id": client.player_id or "Unassigned"})
                except OSError:
                    pass
    except (OSError, ConnectionError) as exc:
        print(f"[ERROR] Could not connect or communicate with server: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
