# Battleship FSM Specification

```mermaid
stateDiagram-v2
    [*] --> INIT

    INIT --> WAITING_FOR_PLAYERS : Server starts

    WAITING_FOR_PLAYERS --> SHIP_PLACEMENT : Two players connected

    SHIP_PLACEMENT --> GAME_START : Both players place valid fleets

    GAME_START --> PLAYER_TURN : Player 1 starts

    PLAYER_TURN --> EVALUATE_MOVE : Player sends MOVE

    EVALUATE_MOVE --> PLAYER_TURN : Valid move, game continues

    EVALUATE_MOVE --> PLAYER_TURN : Invalid move / send ERROR

    EVALUATE_MOVE --> GAME_OVER : All enemy ships sunk

    PLAYER_TURN --> GAME_OVER : Player disconnects / forfeit

    GAME_OVER --> CLEANUP : Winner announced

    CLEANUP --> WAITING_FOR_PLAYERS : Reset for new game
