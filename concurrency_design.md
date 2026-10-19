# Battleship Server Concurrency Design

**Course:** CS 457
**Project:** Battleship
**Sprint:** 2

## 1. Server Concurrency 
-For Battleship, I will use Python multi-threading (`threading.Thread`) to handle both players at the same time.
-Each player will have their own thread connected to the server. This allows both players to send messages without having to wait for the other player's connection.
-The main server will accept connections, while the player threads handle messages and gameplay.

### 1.1 Connection Process
1. The server starts and waits for players to connect.
2. Player 1 connects using a `CONNECT` message.
3. The server saves Player 1's connection and sends `LOBBY_WAIT`.
4. Player 2 connects using `CONNECT`.
5. Once both players connect, they can begin placing their ships.
6. After both players place their five ships, the servr sends `GAME_START`.
7. Player 1 takes the first turn, and the game continues until someone wins or disconnects.
8. After the game ends, the server closes the player connections and resets for another game.

The server will only allow two players in a game. Any extra connections will be rejected.

### 1.2 Handling Messages
-The server will use TCP and JSON messages, following the protocol from Sprint 1.
-Each JSON message ends with `\n` to show where the message ends.
-Since TCP can send messages in pieces or combine multiple messages together, the server will keep reading incoming data until it finds a complete message.
-This prevents the server from trying to process an incomplete message.

## 2. Thread Safety
-Since both players have their own threads, they could try to access the same game information at the same time.
-To prevent problems, I will use Python's `threading.Lock`.
-The lock makes sure only one thread can change important game information at a time.

### 2.1 Shared Game Information
The server will store:
- Both players' connections and IDs.
- Each player's 10x10 Battleship board.
- The ships placed on each board.
- Which player's turn it is.
- The current game state.
- Hits, misses, ships sunk, and wins.
All of this information is stored on the server so neither player can directly change it.

### 2.2 How the Lock Works
Before the server changes the game information, it will acquire the lock.
For example, when a player attacks:
  1. The server locks the shared game information.
  2. It checks if it is the player's turn.
  3. It checks if the attack coordinates are valid.
  4. It checks if that location was already attacked.
  5. If the move is valid, it updates the board and scores.
  6. It checks if the player has won.
  7. If the game is not over, it changes to the next player's turn.
  8. The server releases the lock.
If the move is invalid, the server will send an `ERROR` message without changing the game.
The server will release the lock before sending messages to players so one slow connection does not hold up the whole game.

### 2.3 Preventing Race Conditions
-A race condition happens when two threads try to change the same information at the same time.
-For example, both players might try to attack at nearly the same time.
-Without a lock, the server could process the moves incorrectly or change the turn before finishing the first move.
-Using `threading.Lock` prevents this because only one thread can update the game at a time.

## 3. Turn Synchronization
The server will control whose turn it is. Players cannot change the turn themselves.
Player 1 will always start the game.
When a player sends a `MOVE` message, the server will:
  1. Check that the game has started.
  2. Check that it is the correct player's turn.
  3. Make sure the coordinates are between 0 and 9.
  4. Make sure the location has not already been attacked.
  5. Check whether the attack was a hit or miss.
  6. Update the board and change turns if the game is not over.
  7. Send a `STATE_UPDATE` message to both players.
If a player tries to attack when it is not their turn, the server sends an `ERROR` message.
Invalid moves will not cause a player to lose their turn.

## 4. Board and Score Synchronization

The server will keep track of both players' boards and scores.
For Battleship, I will track:
- Number of hits.
- Number of misses.
- Number of ships sunk.
- Number of games won.

After each valid move, the server will send a `STATE_UPDATE` message to both clients.
-The message will tell the players whose turn it is, the results of the last attack, and the updated game information.
-Each player will be able to see their own board and the locations they have already attacked on the enemy board.
-The server will not show a player's hidden ship locations to their opponent.
-Both players will receive updates from the same server game state. The server will send the updates in the correct order so the clients stay synchronized.
-When a player sinks all five enemy ships, the server will send `GAME_OVER` with the winner and final scores.

## 5. Disconnect Handling
The server needs to handle players leaving the game, whether they quit normally or lose connection.

### 5.1 Normal Disconnect
If a player wants to quit, they send a `DISCONNECT` message.
The server will close their connection and remove them from the game.
If the game has already started, the other player wins by forfeit.

### 5.2 Unexpected Disconnect

A player might also lose connection because of a network problem or because their program crashes.
The server will check for an empty response from `recv()`, which means the connection has closed.
It will also handle socket errors such as `ConnectionResetError` and `BrokenPipeError`.
If this happens during a game, the server will end the match and give the remaining player a win by forfeit.

### 5.3 Server Cleanup

After a game ends, the server will:
  1. Send the final game results when possible.
  2. Close the client sockets.
  3. Remove the players from the game.
  4. Clear the boards and temporary game information.
  5. Return to waiting for two new players.
This allows the server to run another game without needing to restart.

## 6. Connection to Sprint 1
This design will follow the protocol and FSM created in Sprint 1.
The server will continue using:
- TCP sockets.
- JSON messages ending with `\n`.
- The same message types, including `CONNECT`, `PLACE_SHIP`, `MOVE`, `STATE_UPDATE`, `ERROR`, `DISCONNECT`, and `GAME_OVER`.
- The same game states, including `WAITING_FOR_PLAYERS`, `SHIP_PLACEMENT`, `PLAYER_TURN`, `EVALUATE_MOVE`, `GAME_OVER`, and `CLEANUP`.
The main goal of this design is to allow two players to play Battleship at the same time without causing errors in the game state.
The next document, `sequence_diagram.md`, will show how messages move between the two players and the server.
