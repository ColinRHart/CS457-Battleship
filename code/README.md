Battleship — How to Run
Requires Python 3 and three terminals.
1. Start the server in Terminal 1:
   ex: python server.py -p 8080

2. Connect Player 1 in Terminal 2:
   ex: python client.py -i localhost -p 8080

3. Connect Player 2 in Terminal 3:
   ex: python client.py -i localhost -p 8080

4. Each player places five ships on a 10x10 board. Enter coordinates like 3 5 and use h for horizontal or v for vertical.

5. Players take turns attacking until one player sinks all five enemy ships.
Board Symbols:
S = Ship
X = Hit
o = Miss
. = Empty/Unknown
Press Ctrl+C to quit.
Run all commands from the folder containing server.py and client.py.
