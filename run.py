from flask import Flask, jsonify, render_template, request
import json

app = Flask(__name__, static_url_path='/static')


@app.route('/')
def index():
    return render_template('main.html')


@app.route('/game_tree', methods=['GET', 'POST'])
def parse_request():
    # Grab the state of the map plus the move.
    map = json.loads(request.form['map'])

    # A.I changed move
    map[7] = "2"
    print(map)
    return jsonify({"status": "continue", "data": map})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
