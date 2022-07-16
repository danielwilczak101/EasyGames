from flask import Flask, jsonify, render_template, request
from typing import List

import json

from algorithms.finished_game import FinishedGame
from algorithms.tic_tac_toe import TicTacToe

ttt = TicTacToe()

app = Flask(__name__, static_url_path='/static')


@app.route('/')
def index():
    return render_template('main.html')


@app.route('/game_tree', methods=['GET', 'POST'])
async def parse_request():
    # Grab the state of the map plus the move.
    board = json.loads(request.form['map'])
    indexes = await ttt.move(tuple("-12".index(value) for value in board))
    new_board = [
        "-12"[index]
        for index in indexes
    ]

    try:
        await ttt.move(indexes)
        return jsonify({"status": "continue", "data": new_board})

    except FinishedGame as e:
        if e is FinishedGame.WON:
            return jsonify({"status": "You Win", "data": new_board})
        elif e is FinishedGame.TIED:
            return jsonify({"status": "Tied", "data": new_board})
        else:
            return jsonify({"status": "A.I win's!", "data": new_board})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
