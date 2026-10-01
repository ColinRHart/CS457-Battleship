# Battleship FSM Specification

```mermaid
stateDiagram-v2
    [*] --> INIT

    INIT --> WAITING_FOR_PLAYERS : Server starts

    WAITING_FOR_PLAYERS --> SHIP_PLACEMENT : Players connected

    SHIP_PLACEMENT --> GAME_START : Place valid fleets

    GAME_START --> PLAYER_TURN : Player 1 starts

    PLAYER_TURN --> EVALUATE_MOVE : Player sends MOVE

    EVALUATE_MOVE --> PLAYER_TURN : Valid move, game continues

    EVALUATE_MOVE --> PLAYER_TURN : Invalid move / send ERROR

    EVALUATE_MOVE --> GAME_OVER : All enemy ships sunk

    PLAYER_TURN --> GAME_OVER : Player disconnects / forfeit

    GAME_OVER --> CLEANUP : Winner announced

    CLEANUP --> WAITING_FOR_PLAYERS : Reset for new game

## State Descriptions

- `INIT` - Server starts and prepares the game.
- `WAITING_FOR_PLAYERS` - Server waits until two players connect.
- `SHIP_PLACEMENT` - Both players place their ships.
- `GAME_START` - Server assigns Player 1 and Player 2 and starts the game.
- `PLAYER_TURN` - Server waits for the active player to make a move.
- `EVALUATE_MOVE` - Server checks whether the move is valid, a hit, a miss, or wins the game.
- `GAME_OVER` - Server announces the winner or a win by forfeit.
- `CLEANUP` - Server resets game data and prepares for another game.

## Error Handling

If a player sends an invalid coordinate, repeats an attack, or moves out of turn, the server sends an `ERROR` message and stays in the current turn.

If a player disconnects during the game, the other player wins by forfeit and the server moves to `GAME_OVER`.

If a player disconnects before the game begins, the server returns to `WAITING_FOR_PLAYERS`.
