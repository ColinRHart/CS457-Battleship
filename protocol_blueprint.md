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
