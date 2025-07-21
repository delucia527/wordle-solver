const gridEl = document.getElementById('grid');\nconst guessLabel = document.getElementById('guessLabel');\nconst entropyLabel = document.getElementById('entropyLabel');\nconst switchBtn = document.getElementById('switchBtn');\nconst remainingCount = document.getElementById('remainingCount');\nconst remainingList = document.getElementById('remainingList');\nconst topRemaining = document.getElementById('topRemaining');\nconst injectInput = document.getElementById('injectInput');\n
let currentRow = 0; // step-1
let gridState = []; // per-row tiles {letter,state}

function createGrid(){\n  gridEl.innerHTML='';\n  gridState=[];\n  for(let r=0;r<6;r++){\n    const row=[];\n    const rowDiv=document.createElement('div');\n    rowDiv.className='grid-row';\n    for(let c=0;c<5;c++){\n      const div=document.createElement('div');\n      div.className='tile';\n      div.textContent='';\n      div.addEventListener('click',()=>{if(r!==currentRow) return; cycleTile(div,r,c);});\n      rowDiv.appendChild(div);\n      row.push({el:div,state:0});\n    }\n    gridEl.appendChild(rowDiv);\n    gridState.push(row);\n  }\n}\n
function cycleTile(div,r,c){\n  const cell=gridState[r][c];\n  cell.state=(cell.state+1)%3;\n  div.classList.remove('yellow','green');\n  if(cell.state===1) div.classList.add('yellow');\n  if(cell.state===2) div.classList.add('green');\n}\n
async function api(url, method='GET', body=null){\n  const res = await fetch(url,{method,headers:{'Content-Type':'application/json'},body: body?JSON.stringify(body):null});\n  if(!res.ok){console.error('API error');}\n  return res.json();\n}\n
function updateUI(data){\n  guessLabel.textContent = 'Guess: '+data.current_guess;\n  entropyLabel.textContent = data.current_entropy+' bits';\n  remainingCount.textContent = data.remaining_count;\n  switchBtn.disabled = data.suggestions.length<=1 || data.step===1;\n  // Fill current row letters\n  currentRow = data.step-1;\n  if(currentRow<6){\n    const guess=data.current_guess;\n    for(let i=0;i<5;i++){\n      const cell=gridState[currentRow][i];\n      cell.el.textContent=guess[i];\n      cell.el.classList.remove('yellow','green');\n      cell.state=0;\n    }\n  }\n  // Remaining list\n  remainingList.innerHTML='';\n  topRemaining.textContent='';\n  if(data.top_remaining){\n    topRemaining.textContent = data.top_remaining.word.toUpperCase()+' - '+data.top_remaining.entropy.toFixed(2);\n    data.remaining_sorted.forEach(w=>{\n      const div=document.createElement('div');\n      div.className='remaining-word';\n      div.textContent=w;\n      div.onclick=()=>{injectInput.value=w;injectWord();};\n      remainingList.appendChild(div);\n    });\n  }\n}

async function newGame(){\n  createGrid();\n  const data = await api('/api/new_game','POST');\n  updateUI(data);\n}

async function switchSuggestion(){\n  const data = await api('/api/switch','POST');\n  updateUI(data);\n}

async function injectWord(){\n  const word = injectInput.value.trim();\n  if(!word) return;\n  const data = await api('/api/inject','POST',{word});\n  injectInput.value='';\n  if(data.ok) updateUI(data);\n}

async function submitFeedback(){\n  if(currentRow>=6) return;\n  const feedback = gridState[currentRow].map(c=>c.state);\n  const data = await api('/api/submit','POST',{feedback});\n  if(data.answer){\n    // solved: place answer in next row if exists\n    if(currentRow+1<6){\n      const ans=data.answer;\n      for(let i=0;i<5;i++){\n        const cell=gridState[currentRow+1][i];\n        cell.el.textContent=ans[i];\n        cell.el.classList.add('green');\n      }\n    }\n  }\n  updateUI(data);\n}

// Event bindings
document.getElementById('newGame').onclick=newGame;\ndocument.getElementById('switchBtn').onclick=switchSuggestion;\ndocument.getElementById('submitBtn').onclick=submitFeedback;\ndocument.getElementById('injectBtn').onclick=injectWord;\ninjectInput.addEventListener('keydown',e=>{if(e.key==='Enter'){injectWord();}});\n
// Initial load
createGrid();\napi('/api/state').then(data=>{if(!data.step)newGame(); else updateUI(data);});\n
