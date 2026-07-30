from flask import Flask, render_template, request, redirect, url_for, session
import random
import csv
import os

app = Flask(__name__)
app.secret_key = 'uno_secret_key_2026'

games = {}
PLAYER_FILE = 'uno_players.csv'


def load_player_stats():
    stats = {}
    if os.path.exists(PLAYER_FILE):
        with open(PLAYER_FILE, 'r', newline='') as f:
            for row in csv.DictReader(f):
                stats[row['username']] = {
                    'wins': int(row['wins']),
                    'games_played': int(row['games_played']),
                }
    return stats


def save_player_stats():
    with open(PLAYER_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['username', 'wins', 'games_played'])
        writer.writeheader()
        for username, stats in player_stats.items():
            writer.writerow({
                'username': username,
                'wins': stats['wins'],
                'games_played': stats['games_played'],
            })


# username loaded from CSV at startup
# and saved back to CSV every time it changes, so stats survive restarts
player_stats = load_player_stats()

COLORS = ['red', 'blue', 'green', 'yellow']
NUMBERS = list(range(10))
SPECIALS = ['skip', 'reverse', 'draw2']
WILD = ['wild', 'wild_draw4']

# short labels so cards like "wild_draw4" still fit in a small card box
CARD_LABELS = {
    'wild': 'WILD',
    'wild_draw4': '+4',
    'draw2': '+2',
    'skip': '🚫',
    'reverse': '🔄',
}


@app.template_filter('card_label')
def card_label(value):
    if value in CARD_LABELS:
        return CARD_LABELS[value]
    return value


@app.template_filter('card_image')
def card_image(card):
    # maps a card to its image filename, e.g. red 5 -> Red_5.jpg
    # images live in static/cards/, see the README there for the full list
    if card['value'] == 'wild':
        return 'Wild.jpg'
    if card['value'] == 'wild_draw4':
        return 'Wild_Draw_4.jpg'

    color_part = card['color'].capitalize()

    if card['value'] == 'skip':
        return color_part + '_Skip.jpg'
    if card['value'] == 'reverse':
        return color_part + '_Reverse.jpg'
    if card['value'] == 'draw2':
        return color_part + '_Draw_2.jpg'

    return color_part + '_' + card['value'] + '.jpg'


def create_deck():
    # builds the standard 108-card UNO deck: 19 numbers + 6 action cards
    # per color (25 x 4 = 100), plus 8 wild cards
    deck = []
    for color in COLORS:
        for number in NUMBERS:
            deck.append({'color': color, 'value': str(number), 'type': 'number'})
            if number != 0:
                deck.append({'color': color, 'value': str(number), 'type': 'number'})
        for special in SPECIALS:
            deck.append({'color': color, 'value': special, 'type': 'special'})
            deck.append({'color': color, 'value': special, 'type': 'special'})
    for wild in WILD:
        for i in range(4):
            deck.append({'color': 'wild', 'value': wild, 'type': 'wild'})
    random.shuffle(deck)
    return deck


def can_play(card, current_color, current_value):
    # wilds always work, otherwise needs to match color or number/type
    if card['type'] == 'wild':
        return True
    if card['color'] == current_color:
        return True
    if card['value'] == current_value:
        return True
    return False


def advance_turn(game):
    # moves to the next player, direction handles clockwise/counterclockwise
    total_players = len(game['players'])
    game['current_player_index'] = (game['current_player_index'] + game['direction']) % total_players


def apply_card_effect(game, value):
    # runs after color/value are already set on the game
    if value == 'skip':
        advance_turn(game)  # skip = pass the turn twice
        advance_turn(game)
    elif value == 'reverse':
        game['direction'] = -game['direction']
        advance_turn(game)
    elif value == 'draw2':
        advance_turn(game)
        next_player = game['players'][game['current_player_index']]
        for i in range(2):
            if game['deck']:
                next_player['hand'].append(game['deck'].pop())
        sync_uno_flag(next_player)
        advance_turn(game)  # they draw and lose their turn
    elif value == 'wild_draw4':
        advance_turn(game)
        next_player = game['players'][game['current_player_index']]
        for i in range(4):
            if game['deck']:
                next_player['hand'].append(game['deck'].pop())
        sync_uno_flag(next_player)
        advance_turn(game)
    else:
        advance_turn(game)


def sync_uno_flag(player):
    # called_uno only matters when you're down to 1 card
    if len(player['hand']) != 1:
        player['called_uno'] = False


def reshuffle_if_needed(game):
    # deck's getting low - reshuffle everything except the top discard
    if len(game['deck']) < 10:
        last_card = game['discard_pile'].pop()
        game['deck'] = game['discard_pile']
        random.shuffle(game['deck'])
        game['discard_pile'] = [last_card]


def record_win(game, username):
    # winner gets a win + a game played, everyone else just gets a game played
    if username not in player_stats:
        player_stats[username] = {'wins': 0, 'games_played': 0}
    player_stats[username]['wins'] += 1
    player_stats[username]['games_played'] += 1

    for player in game['players']:
        if player['name'] != username:
            if player['name'] not in player_stats:
                player_stats[player['name']] = {'wins': 0, 'games_played': 0}
            player_stats[player['name']]['games_played'] += 1

    save_player_stats()


@app.route('/')
def index():
    return render_template('index.html', games=games)


@app.route('/lobby', methods=['GET', 'POST'])
def lobby():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        game_id = request.form.get('game_id', '').strip()

        if not username:
            return render_template('lobby.html', error="Please enter a username.", games=games)

        if not game_id:
            # 4-digit room code, re-roll if it collides with an existing room
            game_id = str(random.randint(1000, 9999))
            while game_id in games:
                game_id = str(random.randint(1000, 9999))
            deck = create_deck()
            games[game_id] = {
                'id': game_id,
                'players': [],
                'host': username,
                'status': 'waiting',
                'deck': deck,
                'discard_pile': [],
                'current_color': None,
                'current_value': None,
                'current_player_index': 0,
                'direction': 1,
                'winner': None,
                'awaiting_color': None,
                'pending_wild_value': None,
            }
        elif game_id not in games:
            return render_template('lobby.html', error="Game not found.", games=games)

        game = games[game_id]

        if game['status'] != 'waiting':
            return render_template('lobby.html', error="Game already started.", games=games)

        # seating layout is 3 top + 1 left + 1 right + 3 bottom = 8 seats max
        if len(game['players']) >= 8:
            return render_template('lobby.html', error="Game is full (max 8 players).", games=games)

        username_taken = False
        for p in game['players']:
            if p['name'] == username:
                username_taken = True
        if username_taken:
            return render_template('lobby.html', error="Username already taken.", games=games)

        game['players'].append({'name': username, 'hand': [], 'called_uno': False})
        session['username'] = username
        session['game_id'] = game_id


        return redirect(url_for('lobby'))

    game_id = session.get('game_id')
    username = session.get('username')

    if not game_id or game_id not in games:
        return render_template('lobby.html', error=None, games=games)

    game = games[game_id]

    if game['status'] != 'waiting':
        return redirect(url_for('game'))

    return render_template('lobby.html', game=game, username=username, games=games)


@app.route('/start_game', methods=['POST'])
def start_game():
    game_id = session.get('game_id')
    username = session.get('username')

    if not game_id or game_id not in games:
        return redirect(url_for('index'))

    game = games[game_id]

    if game['host'] != username:
        return redirect(url_for('lobby'))

    if len(game['players']) < 2:
        return redirect(url_for('lobby'))

    deck = game['deck']
    for player in game['players']:
        player['hand'] = [deck.pop() for _ in range(7)]

    # first card can't be a wild, keep drawing till we get a real card
    first_card = deck.pop()
    while first_card['type'] == 'wild':
        deck.append(first_card)
        random.shuffle(deck)
        first_card = deck.pop()

    game['discard_pile'].append(first_card)
    game['current_color'] = first_card['color']
    game['current_value'] = first_card['value']
    game['status'] = 'started'
    game['current_player_index'] = 0
    game['direction'] = 1

    return redirect(url_for('game'))


@app.route('/game')
def game():
    game_id = session.get('game_id')
    username = session.get('username')

    if not game_id or game_id not in games:
        return redirect(url_for('index'))

    game = games[game_id]

    if game['status'] == 'waiting':
        return redirect(url_for('lobby'))

    # work out this player's hand and which cards they're allowed to play
    my_hand = []
    me = None
    for player in game['players']:
        if player['name'] == username:
            me = player
            for index, card in enumerate(player['hand']):
                playable = can_play(card, game['current_color'], game['current_value'])
                my_hand.append({'index': index, 'card': card, 'playable': playable})

    # other players sitting on 1 card who haven't called UNO yet - catchable!
    catchable = []
    for player in game['players']:
        if player['name'] != username and len(player['hand']) == 1 and not player['called_uno']:
            catchable.append(player['name'])

    is_my_turn = False
    if game['status'] == 'started' and not game['awaiting_color']:
        current_player = game['players'][game['current_player_index']]
        if current_player['name'] == username:
            is_my_turn = True

    return render_template(
        'game.html',
        game=game,
        username=username,
        my_hand=my_hand,
        me=me,
        catchable=catchable,
        is_my_turn=is_my_turn,
    )


@app.route('/play_card', methods=['POST'])
def play_card():
    game_id = session.get('game_id')
    username = session.get('username')

    if not game_id or game_id not in games:
        return redirect(url_for('index'))

    game = games[game_id]

    if game['status'] != 'started' or game['awaiting_color']:
        return redirect(url_for('game'))

    current_player = game['players'][game['current_player_index']]
    if current_player['name'] != username:
        return redirect(url_for('game'))

    card_index = int(request.form.get('card_index', -1))
    if card_index < 0 or card_index >= len(current_player['hand']):
        return redirect(url_for('game'))

    card = current_player['hand'][card_index]
    if not can_play(card, game['current_color'], game['current_value']):
        return redirect(url_for('game'))

    played_card = current_player['hand'].pop(card_index)
    game['discard_pile'].append(played_card)
    sync_uno_flag(current_player)

    # an empty hand wins the game right away, even if the last card was a wild
    if len(current_player['hand']) == 0:
        game['status'] = 'ended'
        game['winner'] = username
        record_win(game, username)
        return redirect(url_for('game'))

    if played_card['type'] == 'wild':
        # don't advance the turn yet, wait for the player to pick a color
        game['awaiting_color'] = username
        game['pending_wild_value'] = played_card['value']
        return redirect(url_for('game'))

    game['current_color'] = played_card['color']
    game['current_value'] = played_card['value']

    apply_card_effect(game, played_card['value'])
    reshuffle_if_needed(game)

    return redirect(url_for('game'))


@app.route('/choose_color', methods=['POST'])
def choose_color():
    game_id = session.get('game_id')
    username = session.get('username')

    if not game_id or game_id not in games:
        return redirect(url_for('index'))

    game = games[game_id]

    if game['awaiting_color'] != username:
        return redirect(url_for('game'))

    color = request.form.get('color', '')
    if color not in COLORS:
        color = 'red'

    wild_value = game['pending_wild_value']
    game['current_color'] = color
    game['current_value'] = wild_value
    game['awaiting_color'] = None
    game['pending_wild_value'] = None

    # update the actual played card so its face shows the chosen color
    game['discard_pile'][-1]['color'] = color

    apply_card_effect(game, wild_value)
    reshuffle_if_needed(game)

    return redirect(url_for('game'))


@app.route('/draw_card', methods=['POST'])
def draw_card():
    game_id = session.get('game_id')
    username = session.get('username')

    if not game_id or game_id not in games:
        return redirect(url_for('index'))

    game = games[game_id]

    if game['status'] != 'started' or game['awaiting_color']:
        return redirect(url_for('game'))

    current_player = game['players'][game['current_player_index']]
    if current_player['name'] != username:
        return redirect(url_for('game'))

    if game['deck']:
        card = game['deck'].pop()
        current_player['hand'].append(card)
        sync_uno_flag(current_player)

        # can't use what you drew? turn just passes automatically
        if not can_play(card, game['current_color'], game['current_value']):
            advance_turn(game)

    return redirect(url_for('game'))


@app.route('/call_uno', methods=['POST'])
def call_uno():
    game_id = session.get('game_id')
    username = session.get('username')

    if not game_id or game_id not in games:
        return redirect(url_for('index'))

    game = games[game_id]

    if game['status'] != 'started':
        return redirect(url_for('game'))

    # only counts if you're actually down to your last card
    for player in game['players']:
        if player['name'] == username and len(player['hand']) == 1:
            player['called_uno'] = True

    return redirect(url_for('game'))


@app.route('/catch_uno', methods=['POST'])
def catch_uno():
    game_id = session.get('game_id')
    username = session.get('username')

    if not game_id or game_id not in games:
        return redirect(url_for('index'))

    game = games[game_id]

    if game['status'] != 'started':
        return redirect(url_for('game'))

    target_name = request.form.get('target', '')

    # caught red-handed: 1 card left and never called it, draw 2 as punishment
    for player in game['players']:
        if player['name'] == target_name and player['name'] != username:
            if len(player['hand']) == 1 and not player['called_uno']:
                for i in range(2):
                    if game['deck']:
                        player['hand'].append(game['deck'].pop())
                sync_uno_flag(player)

    return redirect(url_for('game'))


@app.route('/reset_game', methods=['POST'])
def reset_game():
    game_id = session.get('game_id')
    if game_id and game_id in games:
        del games[game_id]
    session.clear()
    return redirect(url_for('index'))


@app.route('/leaderboard')
def leaderboard():
    board = []
    for name, stats in player_stats.items():
        board.append({'username': name, 'wins': stats['wins'], 'games_played': stats['games_played']})
    board.sort(key=lambda p: p['wins'], reverse=True)
    return render_template('leaderboard.html', players=board[:10])


@app.route('/rule')
def rule():
    return render_template('rule.html')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)