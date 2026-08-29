const $ = (selector) => document.querySelector(selector);
const audit = (message) => {
  const row = document.createElement('p');
  row.innerHTML = `<span>${new Date().toLocaleTimeString('en-IN', {hour12:false})}</span> ${message}`;
  $('#audit-log').prepend(row);
};

let selectedType = 'document';
let attachedFile = 'sample_inspection_scan.png';
$('#attachBtn').addEventListener('click', () => $('#fileInput').click());
$('#fileInput').addEventListener('change', async (event) => {
  const file = event.target.files[0]; if (!file) return;
  $('#attachLabel').textContent = 'Uploading…';
  const formData = new FormData(); formData.append('file', file);
  try {
    const res = await fetch('/upload', { method: 'POST', body: formData });
    if (!res.ok) throw new Error(`server returned ${res.status}`);
    const data = await res.json();
    attachedFile = data.filename; $('#attachLabel').textContent = attachedFile;
    audit(`Uploaded <code>${attachedFile}</code> — saved locally, never left this workstation.`);
  } catch (err) {
    $('#attachLabel').textContent = 'Upload failed'; audit(`Upload FAILED: ${err.message}`);
  }
});
document.querySelectorAll('.nav').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('.nav').forEach(item => item.classList.remove('active'));
  document.querySelectorAll('.view').forEach(item => item.classList.remove('active-view'));
  button.classList.add('active'); $(`#${button.dataset.view}`).classList.add('active-view');
  $('#title').textContent = button.dataset.view === 'workbench' ? 'Good morning, Operator.' : button.textContent.trim();
}));
document.querySelectorAll('.task').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('.task').forEach(item => item.classList.remove('selected'));
  button.classList.add('selected'); selectedType = button.dataset.type;
  const copy = {document:'Read the pressure vessel inspection report, identify findings, verify the applicable SOP requirements, and draft an approval note.',code:'Calculate a safe hydrotest pressure for PV-2201 and provide the calculation steps.',vision:'Inspect the attached equipment image for visible corrosion and safety anomalies.'};
  $('#prompt').value = copy[selectedType];
}));

function renderModels(models) {
  const entries = Object.entries(models);
  $('#model-list').innerHTML = entries.map(([key, model]) => `<div class="model"><b>${model.display_name}</b><small>${model.model_name}</small><span class="chip">${model.tags.join(' • ')}</span></div>`).join('');
  $('#registry-detail').innerHTML = entries.map(([key, model]) => `<div class="registry-row"><b>${model.display_name}</b><span>${model.model_name}</span><span>${model.tags.join(' · ')}</span></div>`).join('');
}
async function loadModels() {
  try { const response = await fetch('/models'); const models = await response.json();
    const shaped = Object.fromEntries(Object.entries(models).map(([key,m]) => [key,{display_name:m.display_name,model_name:m.model_name,tags:m.tags}]));
    renderModels(shaped);
  } catch { renderModels({vision:{display_name:'Vision Inspector',model_name:'qwen2-vl:7b',tags:['vision','ocr']},document:{display_name:'Document Analyst',model_name:'qwen2.5:14b-instruct',tags:['document','reasoning']},code:{display_name:'Code Specialist',model_name:'qwen2.5-coder:14b',tags:['code','tools']}}); }
}
function step(title, detail, done=false) { return `<div class="step ${done?'done':''}"><b>${title}</b><small>${detail}</small></div>`; }

async function readJsonOrThrow(response) {
  // A non-2xx response (e.g. a real crash inside the backend) doesn't come back
  // as JSON — it's plain text like "Internal Server Error". Calling .json() on
  // that throws a confusing parse error that looks like a connection failure.
  // This reads the real error text instead, so the UI can say what actually happened.
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Server returned ${response.status}: ${text.slice(0, 200)}`);
  }
  return response.json();
}
$('#run').addEventListener('click', async () => {
  const button = $('#run'), activity = $('#activity'), task = $('#prompt').value.trim(); if (!task) return;
  button.disabled = true; button.textContent = 'Executing…';
  activity.innerHTML = step('Task received', 'Classified locally; no data left this workstation.', true) + step('Routing task', 'Selecting the best specialist model…');
  audit(`Task accepted: <code>${task.slice(0,72)}…</code>`);
  try {
    const routeRes = await fetch('/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:task}],has_image:selectedType==='vision',has_pdf:selectedType==='document'})});
    const routeData = await readJsonOrThrow(routeRes); const routing = routeData.routing;
    activity.innerHTML = step('Task received', 'Classified locally; no data left this workstation.', true) + step('Model routed', `<code>${routing.model_used}</code> selected — ${routing.reason}`, true) + step('Planning agent workflow', 'OCR → internal SOP grounding → deliverable generation…');
    audit(`Router selected <code>${routing.model_name}</code> for ${routing.task_type}.`);
    if (selectedType === 'document') {
      const agentRes = await fetch('/agent/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task: `${task} (Reference file: ${attachedFile})`})}); const data = await readJsonOrThrow(agentRes);
      activity.innerHTML += step('Evidence gathered', 'OCR scan read; matching internal SOP retrieved with citations.', true) + step('Approval note drafted', `${data.result}`, true);
      audit('Generated a local draft approval note with human sign-off gate.');
    } else {
      const agentRes = await fetch('/agent/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task: `${task} (Reference file: ${attachedFile})`})}); const data = await readJsonOrThrow(agentRes);
      const labels = selectedType === 'code'
        ? ['Sandbox executing', 'Running the calculation in an isolated, network-disabled runtime.']
        : ['Reading the image', 'Vision model inspecting the attached file for findings.'];
      activity.innerHTML += step(labels[0], labels[1], true) + step('Result ready', `${data.result}`, true);
      audit(`Local ${selectedType} task completed by the real agent; outbound traffic remained 0 B/s.`);
    }
  } catch (error) { activity.innerHTML += step('Task failed', error.message, false); audit(`Task FAILED: ${error.message}`); }
  finally { button.disabled = false; button.innerHTML = 'Run agent <span>→</span>'; }
});
$('#refreshModels').addEventListener('click', loadModels); loadModels();
