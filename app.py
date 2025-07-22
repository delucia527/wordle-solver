import math, os
from typing import List
from flask import Flask, session, jsonify, request, render_template
from collections import defaultdict

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# --------- Load Word Lists (once at startup) ---------
with open('answers.txt') as f:
    ANSWERS = [w.strip() for w in f if w.strip()]
with open('guesses.txt') as f:
    GUESSES = [w.strip() for w in f if w.strip()]
GUESSES_SET = set(GUESSES)

# --------- Core Logic ---------
def pattern(guess: str, answer: str) -> str:
    res = ['?'] * 5
    used = [False] * 5
    for i, (g, a) in enumerate(zip(guess, answer)):
        if g == a:
            res[i] = '2'
            used[i] = True
    for i, g in enumerate(guess):
        if res[i] == '?':
            for j, a in enumerate(answer):
                if not used[j] and g == a:
                    res[i] = '1'
                    used[j] = True
                    break
            else:
                res[i] = '0'
    return ''.join(res)


def score_guess(guess: str, words: List[str]) -> float:
    if not words:
        return 0.0
    freq = defaultdict(int)
    for w in words:
        p = pattern(guess, w)
        freq[p] += 1
    N = len(words)
    return -sum((count/N) * math.log2(count/N) for count in freq.values())

# --------- Helpers to Rebuild State from History ---------
def compute_possible(history):
    possible = ANSWERS.copy()
    for guess, feedback in history:
        fb_str = ''.join(str(s) for s in feedback)
        possible = [w for w in possible if pattern(guess, w) == fb_str]
    return possible


def recompute_suggestions(state):
    history = state['history']
    possible = compute_possible(history)

    # If only 1 left, that's the answer
    if len(possible) == 1:
        state['suggestions']      = possible.copy()
        state['entropies']        = [0.0]
        state['suggestion_index'] = 0
        return state

    # If exactly 2 left, handle like before
    if len(possible) == 2:
        p, b = possible
        rems = set(possible)
        scores = [(g, score_guess(g, possible)) for g in GUESSES if g not in rems]
        scores.sort(key=lambda x: x[1], reverse=True)
        extras = [w for w,_ in scores[:8]]
        uniq = []
        ent  = []
        for w in [p, b] + extras:
            if w not in uniq:
                uniq.append(w)
                ent.append(score_guess(w, possible))
        state['suggestions']      = uniq
        state['entropies']        = ent
        state['suggestion_index'] = 0
        return state

    # General case: top 10 by entropy
    scores = [(g, score_guess(g, possible)) for g in GUESSES]
    scores.sort(key=lambda x: x[1], reverse=True)
    uniq = []
    ent  = []
    for g, e in scores:
        if g not in uniq:
            uniq.append(g)
            ent.append(e)
        if len(uniq) >= 10:
            break

    state['suggestions']      = uniq
    state['entropies']        = ent
    state['suggestion_index'] = 0
    return state

# --------- Serialization ---------
def serialize_state(state):
    history = state['history']
    possible = compute_possible(history)
    count = len(possible)

    remaining_sorted = []
    top_remaining = None
    if state['step'] >= 2 and 1 <= count <= 50:
        word_entropies = [(w, score_guess(w, possible)) for w in possible]
        word_entropies.sort(key=lambda x: x[1], reverse=True)
        remaining_sorted = [w.upper() for w,_ in word_entropies]
        top_remaining = {
            "word": word_entropies[0][0].upper(),
            "entropy": round(word_entropies[0][1], 2)
        }

    return {
        "step": state['step'],
        "suggestions": state['suggestions'],
        "entropies": [round(e, 2) for e in state['entropies']],
        "suggestion_index": state['suggestion_index'],
        "current_guess": state['suggestions'][state['suggestion_index']].upper(),
        "current_entropy": round(state['entropies'][state['suggestion_index']], 2),
        "remaining_count": count,
        "remaining_sorted": remaining_sorted,
        "top_remaining": top_remaining
    }

# --------- Session State Management ---------
def new_game_state():
    first = "raise"
    return {
        'history': [],
        'step': 1,
        'suggestions': [first],
        'entropies': [score_guess(first, ANSWERS)],
        'suggestion_index': 0
    }


def get_state():
    if 'state' not in session:
        session['state'] = new_game_state()
    return session['state']


def save_state(state):
    session['state'] = state

# --------- Routes ---------
@app.route('/')
def index():
    # Reset history on page load/refresh
    session['state'] = new_game_state()
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
        ent = score_guess(word, compute_possible(state['history']))
        if word not in state['suggestions']:
            state['suggestions'].insert(0, word)
            state['entropies'].insert(0, ent)
            state['suggestions'] = state['suggestions'][:10]
            state['entropies']   = state['entropies'][:10]
        state['suggestion_index'] = 0
        save_state(state)
        return jsonify({"ok": True, **serialize_state(state)})
    return jsonify({"ok": False, "error": "Invalid word"}), 400

@app.route('/api/submit', methods=['POST'])
def api_submit():
    data = request.get_json(force=True)
    feedback = data.get('feedback')
    if not isinstance(feedback, list) or len(feedback) != 5 or any(x not in [0,1,2] for x in feedback):
        return jsonify({"error": "Feedback must be list of 5 digits 0/1/2"}), 400

    state = get_state()
    guess = state['suggestions'][state['suggestion_index']]
    state['history'].append((guess, feedback))

    possible = compute_possible(state['history'])
    if len(possible) == 1:
        state['step'] += 1
        state['suggestions']      = [possible[0]]
        state['entropies']        = [0.0]
        state['suggestion_index'] = 0
        save_state(state)
        return jsonify({"answer": possible[0].upper(), **serialize_state(state)})

    state['step'] = len(state['history']) + 1
    state = recompute_suggestions(state)
    save_state(state)
    return jsonify(serialize_state(state))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
