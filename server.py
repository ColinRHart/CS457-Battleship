
"""Two-player console Battleship server (TCP / newline-delimited JSON)."""

import argparse
import json
import queue
import select
import socket
import threading
from dataclasses import dataclass, field

BOARD_SIZE = 10
# Standard five-ship Battleship fleet; ship sizes were not fixed in Sprint 1.
SHIPS = {"Carrier": 5, "Battleship": 4, "Cruiser": 3,
         "Submarine": 3, "Destroyer": 2}
MAX_MESSAGE_BYTES = 65536


def valid_port(text):
    """argparse validator: use the project's nonprivileged port range."""
    try:
        port = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1024 and 65535")
    return port


def json_line(message):
    return (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")


@dataclass(eq=False)
class Player:
    sock: socket.socket
    address: tuple
    player_id: str = ""
    ships: dict = field(default_factory=dict)  # name -> set[(row, col)]
    attacks: dict = field(default_factory=dict)  # (row,col) -> hit/miss/sunk
    hits: int = 0
    misses: int = 0
    sunk: int = 0
    wins: int = 0
    outgoing: queue.Queue = field(default_factory=queue.Queue)

    def occupied(self):
        return set().union(*self.ships.values()) if self.ships else set()


class BattleshipServer:
    """All mutable game state is protected by lock; wire sends use queues."""

    def __init__(self, port):
        self.port = port
        self.lock = threading.Lock()
        self.players = []
        self.state = "INIT"
        self.turn = "Player_1"

    def enqueue(self, player, message):
        """Call under lock to preserve outgoing event order."""
        player.outgoing.put(message)

    def announce(self, message):
        for player in self.players:
            self.enqueue(player, message)

    def lobby_message(self, player, text):
        self.enqueue(player, {"msg_type": "LOBBY_WAIT", "message": text,
                              "player_id": player.player_id,
                              "ships_placed": len(player.ships)})

    def error(self, player, code, message):
        self.enqueue(player, {"msg_type": "ERROR", "error_code": code,
                              "message": message})

    def register(self, player):
        with self.lock:
            if len(self.players) >= 2 or self.state not in (
                    "WAITING_FOR_PLAYERS",):
                player.outgoing.put({"msg_type": "ERROR", "error_code": "ROOM_FULL",
                                     "message": "Game is full; try again later."})
                player.outgoing.put(None)
                return False
            self.players.append(player)
            player.player_id = f"Player_{len(self.players)}"
            self.lobby_message(player, "Connected. Waiting for second player..."
                               if len(self.players) == 1 else
                               "Both players connected. Place your five ships.")
            if len(self.players) == 2:
                self.state = "SHIP_PLACEMENT"
                self.lobby_message(self.players[0],
                                   "Both players connected. Place your five ships.")
            print(f"[JOIN] {player.player_id} from {player.address}", flush=True)
            return True

    def is_active(self, player):
        with self.lock:
            return player in self.players

    @staticmethod
    def validate_coordinates(message):
        row, col = message.get("row"), message.get("col")
        if (type(row) is not int or type(col) is not int or
                not (0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE)):
            raise ValueError("row and col must be integers from 0 to 9")
        return row, col

    def place_ship(self, player, message):
        if self.state != "SHIP_PLACEMENT":
            self.error(player, "INVALID_STATE", "Ship placement is not active.")
            return
        try:
            row, col = self.validate_coordinates(message)
        except ValueError as exc:
            self.error(player, "INVALID_PLACEMENT", str(exc))
            return
        ship = message.get("ship")
        direction = message.get("direction")
        if not isinstance(ship, str) or ship not in SHIPS:
            self.error(player, "INVALID_PLACEMENT", "Unknown ship type.")
            return
        if ship in player.ships:
            self.error(player, "INVALID_PLACEMENT", f"{ship} already placed.")
            return
        if direction not in ("horizontal", "vertical"):
            self.error(player, "INVALID_PLACEMENT", "Direction must be horizontal or vertical.")
            return
        length = SHIPS[ship]
        cells = {(row, col + i) if direction == "horizontal"
                 else (row + i, col) for i in range(length)}
        if any(r >= BOARD_SIZE or c >= BOARD_SIZE for r, c in cells):
            self.error(player, "INVALID_PLACEMENT", "Ship goes beyond board boundary.")
            return
        if cells & player.occupied():
            self.error(player, "INVALID_PLACEMENT", "Ships cannot overlap.")
            return
        player.ships[ship] = cells
        self.lobby_message(player, f"Placed {ship} ({len(player.ships)}/5).")
        if all(len(p.ships) == len(SHIPS) for p in self.players):
            self.state = "GAME_START"
            self.announce({"msg_type": "GAME_START", "first_turn": "Player_1"})
            self.state = "PLAYER_TURN"
            self.send_updates(None)
            print("[START] Both fleets placed; Player_1 starts.", flush=True)

    def board_for(self, player):
        """The recipient sees their own fleet and only known enemy attack cells."""
        enemy = next(p for p in self.players if p is not player)
        own = [["."] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        target = [["."] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        for ship in player.ships.values():
            for r, c in ship:
                own[r][c] = "S"
        for (r, c), result in enemy.attacks.items():
            own[r][c] = "X" if result != "miss" else "o"
        for (r, c), result in player.attacks.items():
            target[r][c] = "X" if result != "miss" else "o"
        return own, target

    def send_updates(self, last_move):
        for player in self.players:
            own, target = self.board_for(player)
            self.enqueue(player, {
                "msg_type": "STATE_UPDATE", "active_player": self.turn,
                "last_move": last_move, "hits": player.hits,
                "misses": player.misses, "ships_sunk": player.sunk,
                "own_board": own, "target_board": target,
            })

    def move(self, player, message):
        if self.state != "PLAYER_TURN":
            self.error(player, "INVALID_STATE", "Game is not accepting attacks.")
            return
        if player.player_id != self.turn:
            self.error(player, "OUT_OF_TURN", "It is not your turn.")
            return
        try:
            row, col = self.validate_coordinates(message)
        except ValueError as exc:
            self.error(player, "INVALID_MOVE", str(exc))
            return
        if (row, col) in player.attacks:
            self.error(player, "INVALID_MOVE", "You already attacked that cell.")
            return
        self.state = "EVALUATE_MOVE"
        enemy = next(p for p in self.players if p is not player)
        ship_name = next((name for name, cells in enemy.ships.items()
                          if (row, col) in cells), None)
        if ship_name is None:
            result = "miss"
            player.misses += 1
        else:
            result = "hit"
            player.hits += 1
        player.attacks[(row, col)] = result
        if ship_name is not None:
            cells = enemy.ships[ship_name]
            if all(cell in player.attacks for cell in cells):
                result = "sunk"
                player.attacks[(row, col)] = result
                player.sunk += 1
        last_move = {"player_id": player.player_id, "row": row,
                     "col": col, "result": result}
        if result == "sunk":
            last_move["ship"] = ship_name
        print(f"[MOVE] {player.player_id}: ({row},{col}) {result}", flush=True)
        if player.sunk == len(SHIPS):
            player.wins += 1
            self.finish(player.player_id, "all_ships_sunk")
            return
        self.turn = enemy.player_id
        self.state = "PLAYER_TURN"
        self.send_updates(last_move)

    def finish(self, winner, reason):
        """Queue the terminal result, then release this game's two slots."""
        self.state = "GAME_OVER"
        scores = {p.player_id: {"hits": p.hits, "misses": p.misses,
                                "ships_sunk": p.sunk, "games_won": p.wins}
                  for p in self.players}
        self.announce({"msg_type": "GAME_OVER", "winner": winner,
                       "reason": reason, "final_scores": scores})
        print(f"[OVER] Winner: {winner}; reason: {reason}", flush=True)
        self.state = "CLEANUP"
        for p in self.players:
            p.outgoing.put(None)
        self.players.clear()
        self.turn = "Player_1"
        self.state = "WAITING_FOR_PLAYERS"

    def disconnect(self, player):
        with self.lock:
            if player not in self.players:
                return
            old_state = self.state
            self.players.remove(player)
            player.outgoing.put(None)
            print(f"[LEAVE] {player.player_id}", flush=True)
            if old_state in ("PLAYER_TURN", "EVALUATE_MOVE", "GAME_START"):
                # finish expects the remaining players list.
                if self.players:
                    self.players[0].wins += 1
                    self.finish(self.players[0].player_id, "opponent_disconnected")
                else:
                    self.state = "WAITING_FOR_PLAYERS"
            elif old_state == "SHIP_PLACEMENT":
                for p in self.players:
                    p.ships.clear()
                    p.attacks.clear()
                    p.hits = p.misses = p.sunk = 0
                self.state = "WAITING_FOR_PLAYERS"
                self.reassign_and_notify()
            else:
                self.state = "WAITING_FOR_PLAYERS"
                self.reassign_and_notify()

    def reassign_and_notify(self):
        for i, p in enumerate(self.players, 1):
            p.player_id = f"Player_{i}"
            self.lobby_message(p, "Opponent left. Waiting for another player; fleet reset.")

    def handle_message(self, player, msg):
        with self.lock:
            if player not in self.players:
                return
            if not isinstance(msg, dict):
                self.error(player, "BAD_MESSAGE", "JSON message must be an object.")
                return
            kind = msg.get("msg_type")
            if kind == "DISCONNECT":
                # Do not call disconnect while holding the non-reentrant lock.
                pass
            elif kind == "PLACE_SHIP" or kind == "MOVE":
                if msg.get("player_id") != player.player_id:
                    self.error(player, "INVALID_PLAYER", "Incorrect player_id.")
                elif kind == "PLACE_SHIP":
                    self.place_ship(player, msg)
                else:
                    self.move(player, msg)
            else:
                self.error(player, "UNKNOWN_MESSAGE", "Unknown or unexpected message type.")
        if kind == "DISCONNECT":
            self.disconnect(player)

    def writer(self, player):
        try:
            while True:
                msg = player.outgoing.get()
                if msg is None:
                    break
                player.sock.sendall(json_line(msg))
        except OSError:
            self.disconnect(player)
        finally:
            try:
                player.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            player.sock.close()

    def reader(self, player):
        buffer = bytearray()
        try:
            # The initial handshake identifies the joining client. Player IDs
            # are assigned authoritatively by the server, not by the user.
            while True:
                if not self.is_active(player):
                    break
                readable, _, _ = select.select([player.sock], [], [], 0.5)
                if not readable:
                    continue
                chunk = player.sock.recv(4096)
                if not chunk:
                    break
                buffer.extend(chunk)
                if len(buffer) > MAX_MESSAGE_BYTES and b"\n" not in buffer:
                    with self.lock:
                        if player in self.players:
                            self.error(player, "BAD_MESSAGE", "Message is too large.")
                    break
                while b"\n" in buffer:
                    raw, _, remaining = buffer.partition(b"\n")
                    buffer = bytearray(remaining)
                    if len(raw) > MAX_MESSAGE_BYTES:
                        self.handle_message(player, {})
                        continue
                    try:
                        message = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        with self.lock:
                            if player in self.players:
                                self.error(player, "BAD_MESSAGE", "Invalid JSON.")
                        continue
                    self.handle_message(player, message)
                    if not self.is_active(player):
                        break
        except (OSError, ValueError):
            pass
        finally:
            self.disconnect(player)

    def serve(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("0.0.0.0", self.port))
            listener.listen()
            with self.lock:
                self.state = "WAITING_FOR_PLAYERS"
            print(f"Battleship server listening on 0.0.0.0:{self.port}", flush=True)
            while True:
                sock, address = listener.accept()
                player = Player(sock, address)
                threading.Thread(target=self.writer, args=(player,), daemon=True).start()
                # CONNECT must be the first message, even for a full lobby.
                try:
                    sock.settimeout(10)
                    data = bytearray()
                    while b"\n" not in data and len(data) < MAX_MESSAGE_BYTES:
                        part = sock.recv(4096)
                        if not part:
                            break
                        data.extend(part)
                    sock.settimeout(None)
                    first, _, extra = data.partition(b"\n")
                    obj = json.loads(first.decode("utf-8"))
                    if extra or not isinstance(obj, dict) or obj.get("msg_type") != "CONNECT":
                        raise ValueError("First message must be CONNECT only")
                except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
                    player.outgoing.put({"msg_type": "ERROR", "error_code": "HANDSHAKE",
                                         "message": "First message must be CONNECT."})
                    player.outgoing.put(None)
                    continue
                if self.register(player):
                    threading.Thread(target=self.reader, args=(player,), daemon=True).start()


def main():
    parser = argparse.ArgumentParser(description="Two-player Battleship TCP server")
    parser.add_argument("-p", "--port", required=True, type=valid_port,
                        help="TCP listening port (1024-65535)")
    args = parser.parse_args()
    try:
        BattleshipServer(args.port).serve()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except OSError as exc:
        print(f"[ERROR] Cannot start server: {exc}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
