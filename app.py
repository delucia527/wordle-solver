import math, os
from flask import Flask, session, jsonify, request, render_template
from collections import defaultdict

# --------- Flask Setup ---------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# --------- Load Word Lists (once at startup) ---------
with open('answers.txt') as f:
    ANSWERS = [w.strip() for w in f if w.strip()]
with open('guesses.txt') as f:
    GUESSES = [w.strip() for w in f if w.strip()]
GUESSES_SET = set(GUESSES)
ANSWERS_SET = set(ANSWERS)

# --------- Core Logic (shared) ---------

def pattern(guess: str, answer: str) -> str:
    res = ['?'] * 5
    used = [False] * 5
    for i, (g, a) in enumerate(zip(guess, answer)):
        if g == a:
            res[i] = '2'; used[i] = True
    for i, g in enumerate(guess):
        if res[i] == '?':
            for j, a in enumerate(answer):
                if not used[j] and g == a:
                    res[i] = '1'; used[j] = True
                    break
            else:
                res[i] = '0'
    return ''.join(res)

def score_guess(guess: str, words: list[str]) -> float:
    if not words:
        return 0.0
    freq = defaultdict(int)
    for w in words:
        p = pattern(guess, w)
        freq[p] += 1
    N = len(words)
    return -sum((count/N) * math.log2(count/N) for count in freq.values())

# --------- Session State Helpers ---------

def new_game_state():
    first = "raise"
    possible = ANSWERS.copy()
    ent = score_guess(first, possible)
    return {
        "possible": possible,
        "step": 1,
        "suggestions": [first],
        "entropies": [ent],
        "suggestion_index": 0
    }

def get_state():
    if "game" not in session:
        session["game"] = new_game_state()
    return session["game"]

def save_state(state):
    session["game"] = state

# --------- State Serialization ---------

def serialize_state(state):
    # compute remaining words list + top entropy word list when threshold passed
    possible = state['possible']
    count = len(possible)
    remaining_sorted = []
    top_remaining = None
    if state['step'] >= 2 and 1 <= count <= 50:
        word_entropies = [(w, score_guess(w, possible)) for w in possible]
        word_entropies.sort(key=lambda x: x[1], reverse=True)
        remaining_sorted = [w for w,_ in word_entropies]
        top_remaining = {"word": word_entropies[0][0], "entropy": round(word_entropies[0][1], 2)}
    return {
        "step": state['step'],
        "suggestions": state['suggestions'],
        "entropies": state['entropies'],
        "suggestion_index": state['suggestion_index'],
        "current_guess": state['suggestions'][state['suggestion_index']].upper(),
        "current_entropy": round(state['entropies'][state['suggestion_index']], 2),
        "remaining_count": count,
        "remaining_sorted": [w.upper() for w in remaining_sorted],
        "top_remaining": top_remaining
    }

# --------- Suggestion Recalculation ---------

def recompute_suggestions(state):
    possible = state['possible']
    if len(possible) == 1:
        ans = possible[0]
        state['suggestions'] = [ans]
        state['entropies'] = [0.0]
        state['suggestion_index'] = 0
        return state
    if len(possible) == 2:
        p,b = possible
        rems = set(possible)
        scores = [(g, score_guess(g, possible)) for g in GUESSES if g not in rems]
        scores.sort(key=lambda x: x[1], reverse=True)
        extras = [w for w,_ in scores[:8]]
        state['suggestions'] = [p,b] + extras
        state['entropies'] = [score_guess(p,possible), score_guess(b,possible)] + [s for _,s in scores[:8]]
        state['suggestion_index'] = 0
        return state
    # General case
    scores = [(g, score_guess(g, possible)) for g in GUESSES]
    scores.sort(key=lambda x: x[1], reverse=True)
    top = scores[:10]
    state['suggestions'] = [g for g,_ in top]
    state['entropies'] = [e for _,e in top]
    state['suggestion_index'] = 0
    return state

# --------- Routes ---------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/new_game', methods=['POST'])
def api_new_game():
    state = new_game_state()
    save_state(state)
    return jsonify(serialize_state(state))

@app.route('/api/state', methods=['GET'])
def api_state():
    return jsonify(serialize_state(get_state()))

@app.route('/api/switch', methods=['POST'])
def api_switch():
    state = get_state()
    if len(state['suggestions']) > 1:
        state['suggestion_index'] = (state['suggestion_index'] + 1) % len(state['suggestions'])
        save_state(state)
    return jsonify(serialize_state(state))

@app.route('/api/inject', methods=['POST'])
def api_inject():
    data = request.get_json(force=True)
    word = (data.get('word') or '').strip().lower()
    state = get_state()
    if len(word) == 5 and word in GUESSES_SET:
        ent = score_guess(word, state['possible'])
        if word not in state['suggestions']:
            state['suggestions'].insert(0, word)
            state['entropies'].insert(0, ent)
            state['suggestions'] = state['suggestions'][:10]
            state['entropies'] = state['entropies'][:10]
        state['suggestion_index'] = 0
        save_state(state)
        return jsonify({"ok": True, **serialize_state(state)})
    return jsonify({"ok": False, "error": "Invalid word"}), 400

@app.route('/api/submit', methods=['POST'])
def api_submit():
    data = request.get_json(force=True)
    feedback = data.get('feedback')  # e.g. [0,2,1,0,2]
    if not isinstance(feedback, list) or len(feedback) != 5 or any(x not in [0,1,2] for x in feedback):
        return jsonify({"error": "Feedback must be list of 5 digits 0/1/2"}), 400
    state = get_state()
    guess = state['suggestions'][state['suggestion_index']]
    fb_str = ''.join(str(s) for s in feedback)
    state['possible'] = [w for w in state['possible'] if pattern(guess, w) == fb_str]
    if len(state['possible']) == 1:
        # Final answer row artificially increment step for UI parity
        state['step'] += 1
        state['suggestions'] = [state['possible'][0]]
        state['entropies'] = [0.0]
        state['suggestion_index'] = 0
        save_state(state)
        return jsonify({"answer": state['possible'][0].upper(), **serialize_state(state)})
    # Not solved: compute next suggestions
    state['step'] += 1
    state = recompute_suggestions(state)
    save_state(state)
    return jsonify(serialize_state(state))

# Render requires a callable named "app".
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
