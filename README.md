# UNO-GAME
## What our project does
This is an online website where users can play the UNO card game with their friends. It accepts 2-8 players to play at a time. Users can either create a game or join a game. Upon the creation of a game, a random code is generated, and users must enter in the code, along with a username, to join the game lobby. Once the game is started, the game will go on in a turn-based manner until one player reaches zero cards, or wins. When games are finished, users can view their win percentage and the number of games that they have played through the leaderboard button.
## How to run it locally
1. Make sure you have Python 3 installed.
2. Install Flask.
 `pip install Flask`
3. Download all the files in zip.
4. From the project folder, run:
  	`python app.py`
Open [http://localhost:5001](url) in your browser. To play with others on the same network, they can visit [http://<your-computer's-IP>:5001](url).
5. You need at least 2 players to start a game. You can create a room and let them join the same room to start the game.
## Point Requirements
### 1. POST usage
- POST `/play_card` in app.py  validates the card is legal, updates the discard pile, applies card effects (skip/reverse/draw2/wild), advances the turn, ends the game on a win
- POST `/draw_card` in app.py  draws a card and passes the turn if it's unplayable
- POST `/choose_color` in app.py  finalizes a wild card's color and resolves its effect
- POST `/call_uno` in app.py  marks that a player at 1 card has called UNO
- POST `/catch_uno` in app.py  catches a player who forgot to call UNO, penalizing them 2 cards
- POST `/start_game` in app.py  deals 7 cards to every player and flips the first discard card
### 2. Persistent data store
- Win/loss stats are stored in `uno_players.csv`, handled by `load_player_stats()` and `save_player_stats()` in `app.py`.
- Stats load from the CSV at startup and get written back to it every time a game ends.
## Limitations
- The card images were taken from Kaggle, and therefore are not the best quality. The +2 cards in particular are a little bit hard to read since the “+2” text is somewhat pixelated.
- The game keeps going endlessly as long as no one wins.
- The game runs locally only.
