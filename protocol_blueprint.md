
# Battleship Protocol Blueprint

## Transport

- Protocol: TCP
- Format: JSON
- Framing: Each JSON message ends with `\n`

TCP sends data as a stream, so messages may arrive together or in pieces. The receiver will keep reading until it finds `\n`, then it will parse that message as JSON.

---

## Message Types
1. `CONNECT`
2. `LOBBY_WAIT`
3. `GAME_START`
4. `PLACE_SHIP`
5. `MOVE`
6. `STATE_UPDATE`
7. `ERROR`
8. `DISCONNECT`
9. `GAME_OVER`

### CONNECT
Client -> Server
Used when a player joins the game.
**Fields:**
- `msg_type` - String
- `player_id` - String
Used when a player joins the game.

**Example:**
```json
  {
  "msg_type": "CONNECT",
  "player_id": "Player_1"
  }
```

### LOBBY_WAIT
Server -> Client
Tells a player to wait for another player.
**Fields:**
- `msg_type` - String
- `message` - String

### GAME_START
Server -> Clients
Sent after both players finish placing their ships.
**Fields:**
- `msg_type` - String
- `first_turn` - String

### PLACE_SHIP
Client -> Server
Used to place a ship.
**Fields:**
- `msg_type` - String
- `player_id` - String
- `ship` - String
- `row` - Integer (0-9)
- `col` - Integer (0-9)
- `direction` - String (horizontal or vertical)

The server checks ship length, boundaries, and overlapping ships. Invalid placements return `ERROR` without changing the board.

### MOVE
Client -> Server
Used to attack an opponent's board.
**Fields:**
- `msg_type` - String
- `player_id` - String
- `row` - Integer (0-9)
- `col` - Integer (0-9)

Invalid coordinates, repeated attacks, or attacking out of turn return `ERROR`. Invalid moves do not change turns.

### STATE_UPDATE
Server -> Clients
Sent after each valid move.
**Fields:**
- `msg_type` - String
- `active_player` - String
- `last_move` - Object (row, col, hit or miss)
- `hits` - Integer
- `misses` - Integer
- `ships_sunk` - Integer

The server does not reveal the opponent's hidden ships.

### ERROR
Server -> Client
Sent when a message or action is invalid.
**Fields:**
- `msg_type` - String
- `error_code` - String
- `message` - String

Errors include invalid placement, invalid move, out-of-turn move, and missing message fields.

### DISCONNECT
Client -> Server
Sent when a player leaves the game.
**Fields:**
- `msg_type` - String
- `player_id` - String

The server also detects unexpected disconnects when `recv()` returns `b""` or a socket error occurs.

### GAME_OVER
Server -> Clients
Sent when the game ends.
**Fields:**
- `msg_type` - String
- `winner` - String
- `reason` - String
- `final_scores` - Object

## Disconnect Handling

- In the lobby, the server removes the disconnected player and continues waiting.
- During ship placement, the server clears the boards and returns the remaining player to the lobby.
- During gameplay, the remaining player wins by forfeit.
- After the game ends, the server closes connections and resets for another game.

