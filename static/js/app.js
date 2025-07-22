const gridEl = document.getElementById('grid');
const guessLabel = document.getElementById('guessLabel');
const entropyLabel = document.getElementById('entropyLabel');
const switchBtn = document.getElementById('switchBtn');
const remainingCount = document.getElementById('remainingCount');
const remainingList = document.getElementById('remainingList');
const topRemaining = document.getElementById('topRemaining');
const injectInput = document.getElementById('injectInput');
const submitBtn = document.getElementById('submitBtn');
const spinner = document.getElementById('spinner');

let currentRow = 0; // step - 1
let gridState = []; // per-row tiles { el, state }

/* ---------- Grid Setup ---------- */
function createGrid() {
  gridEl.innerHTML = '';
  gridState = [];
  for (let r = 0; r < 6; r++) {
    const row = [];
    const rowDiv = document.createElement('div');
    rowDiv.className = 'grid-row';
    for (let c = 0; c < 5; c++) {
      const div = document.createElement('div');
      div.className = 'tile';
      div.textContent = '';
      div.addEventListener('click', () => {
        if (r !== currentRow) return;
        cycleTile(div, r, c);
      });
      rowDiv.appendChild(div);
      row.push({ el: div, state: 0 });
    }
    gridEl.appendChild(rowDiv);
    gridState.push(row);
  }
}

function cycleTile(div, r, c) {
  const cell = gridState[r][c];
  cell.state = (cell.state + 1) % 3;
  div.classList.remove('yellow', 'green');
  if (cell.state === 1) div.classList.add('yellow');
  if (cell.state === 2) div.classList.add('green');
}

/* ---------- API Helper ---------- */
async function api(url, method = 'GET', body = null) {
  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : null
  });
  return res.json();
}

/* ---------- UI Update ---------- */
function updateUI(data) {
  guessLabel.textContent = 'Guess: ' + data.current_guess;
  entropyLabel.textContent = data.current_entropy + ' bits';
  remainingCount.textContent = data.remaining_count;
  switchBtn.disabled = data.suggestions.length <= 1 || data.step === 1;

  currentRow = data.step - 1;
  if (currentRow < 6) {
    const guess = data.current_guess;
    for (let i = 0; i < 5; i++) {
      const cell = gridState[currentRow][i];
      cell.el.textContent = guess[i];
      cell.el.classList.remove('yellow', 'green');
      cell.state = 0;
    }
  }

  remainingList.innerHTML = '';
  topRemaining.textContent = '';
  if (data.top_remaining) {
    topRemaining.textContent =
      data.top_remaining.word.toUpperCase() +
      ' - ' +
      data.top_remaining.entropy.toFixed(2);
    data.remaining_sorted.forEach(w => {
      const div = document.createElement('div');
      div.className = 'remaining-word';
      div.textContent = w;
      div.onclick = () => {
        injectInput.value = w;
        injectWord();
      };
      remainingList.appendChild(div);
    });
  }
}

/* ---------- Game Actions ---------- */
async function newGame() {
  createGrid();
  submitBtn.disabled = false;
  spinner.classList.add('hidden');
  const data = await api('/api/new_game', 'POST');
  updateUI(data);
}

async function switchSuggestion() {
  const data = await api('/api/switch', 'POST');
  updateUI(data);
}

async function injectWord() {
  const word = injectInput.value.trim();
  if (!word) return;
  const data = await api('/api/inject', 'POST', { word });
  injectInput.value = '';
  if (data.ok) updateUI(data);
}

async function submitFeedback() {
  if (currentRow >= 6) return;
  if (submitBtn.disabled) return;

  submitBtn.disabled = true;
  spinner.classList.remove('hidden');

  const feedback = gridState[currentRow].map(c => c.state);
  try {
    const data = await api('/api/submit', 'POST', { feedback });
    if (data.answer) {
      if (currentRow + 1 < 6) {
        const ans = data.answer;
        for (let i = 0; i < 5; i++) {
          const cell = gridState[currentRow + 1][i];
          cell.el.textContent = ans[i];
          cell.el.classList.add('green');
        }
      }
    }
    updateUI(data);
  } finally {
    spinner.classList.add('hidden');
    submitBtn.disabled = false;
  }
}

/* ---------- Event Bindings ---------- */
document.getElementById('newGame').onclick = newGame;
document.getElementById('switchBtn').onclick = switchSuggestion;
document.getElementById('submitBtn').onclick = submitFeedback;
document.getElementById('injectBtn').onclick = injectWord;
injectInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    injectWord();
  }
});

/* ---------- Initial Load ---------- */
createGrid();
// Because the index route already resets the game, just fetch state.
api('/api/state')
  .then(data => updateUI(data))
  .catch(() => newGame());
