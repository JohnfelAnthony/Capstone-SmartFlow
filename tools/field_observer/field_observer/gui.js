'use strict';
const $ = id => document.getElementById(id);
const canvas = $('canvas');
const ctx = canvas.getContext('2d');
const player = $('player');
let state = {};
let config = null;
let points = [];
let reference = new Image();
let events = [];
let proposals = [];
let page = 0;
let selected = null;
let lastVersion = -1;
let lastProject = null;
let replayProject = null;
let activeImage = 0;
let acceptConfig = false;
const busyStatuses = new Set(['uploading', 'indexing', 'loading', 'analyzing', 'stopping', 'exporting']);
const phaseLabels = {
  empty: 'No recording open', uploading: 'Saving recording', indexing: 'Indexing frames',
  ready: 'Recording ready', loading: 'Preparing analysis', analyzing: 'Analyzing video',
  stopping: 'Stopping analysis', cancelled: 'Analysis stopped', complete: 'Review ready',
  exporting: 'Preparing export', error: 'Operation failed'
};
const videoFormats = 'MP4, MOV, MKV, AVI, WebM, M4V, MTS';
let clientTask = null;
let connected = true;
let refreshQueue = Promise.resolve();
const busy = () => Boolean(clientTask) || busyStatuses.has(state.status);
const locked = () => busy() || !connected;
const hasReplay = () => state.has_replay || (state.status === 'exporting' && replayProject === state.project_id);
const canDraw = () => Boolean(config) && !locked() && !hasReplay();
const text = (id, value) => { if ($(id).textContent !== value) $(id).textContent = value; };

function error(message) {
  text('error', message);
  $('error').hidden = !message;
  if (message) {
    const bounds = $('error').getBoundingClientRect();
    if (bounds.top < 80 || bounds.bottom > innerHeight) $('error').scrollIntoView({block: 'center'});
  }
}

async function readResponse(response) {
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'The local request failed.');
  return result;
}

async function get(path) { return readResponse(await fetch(path, {cache: 'no-store'})); }
async function post(path, data) {
  const response = await fetch(path, {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-Observer-Token': token}, body: JSON.stringify(data)
  });
  return readResponse(response);
}

function action(id, fn) {
  $(id).onclick = async () => {
    error('');
    try { await fn(); }
    catch (exc) { error(exc.message); }
  };
}

function updateOperation() {
  const processing = state.status === 'analyzing';
  const percent = processing && state.duration > 0 ? Math.min(100, 100 * state.seconds / state.duration) : null;
  const waiting = busy();
  const nextManualStep = mcView && state.status === 'ready' && /^(Draw a counting line|Saved recording opened)/.test(state.message);
  const title = connected ? (clientTask?.label || phaseLabels[state.status] || phaseLabels.empty) : 'Disconnected';
  const message = connected
    ? (clientTask?.message || (nextManualStep ? 'Choose a road to start a pass.' : state.message) || 'Choose a video or open a saved recording.')
    : 'Keep the Field Observer launcher open. The page will reconnect automatically.';
  const detail = clientTask?.detail || (processing ? `${state.frame_number.toLocaleString()} frames · ${Math.floor(percent || 0)}%` : '');
  text('operationLabel', title);
  text('status', message);
  text('operationDetail', detail);
  $('operationDetail').hidden = !detail || !connected;
  const progress = $('progress');
  const value = clientTask ? clientTask.progress : percent;
  progress.hidden = !waiting || !connected;
  if (value == null) progress.removeAttribute('value');
  else progress.value = value;
}

function updateControls() {
  const active = locked();
  for (const id of ['videoFile', 'mcFile', 'demo', 'saved', 'mcSaved', 'mcSite', 'mcCountSite', 'mcMode']) $(id).disabled = active;
  $('upload').disabled = active || !$('videoFile').files.length;
  $('mcLoad').disabled = active || !$('mcFile').files.length || !$('mcSite').value;
  $('openSaved').disabled = active || !$('saved').value;
  $('mcOpen').disabled = active || !$('mcSaved').value;
  const analyzing = ['loading', 'analyzing', 'stopping'].includes(state.status);
  $('stop').hidden = !analyzing;
  $('stop').disabled = !connected || Boolean(clientTask) || state.status === 'stopping';
  $('analyze').disabled = !canDraw() || !config?.lines.length;
  $('addLine').disabled = !canDraw() || points.length !== 2;
  $('clearPoints').disabled = !canDraw() || !points.length;
  $('rotation').disabled = !canDraw() || ['cancelled', 'error'].includes(state.status);
  for (const id of ['lineId', 'lineType', 'location', 'place', 'direction', 'confidence']) $(id).disabled = !canDraw();
  for (const button of $('lineList').querySelectorAll('button')) {
    button.hidden = hasReplay();
    button.disabled = !canDraw();
  }
  for (const id of ['addMissed', 'saveReview', 'saveCoverage', 'saveQueue', 'savePair', 'export']) {
    $(id).disabled = active || state.status !== 'complete';
  }
  $('mcExport').disabled = active || isRoadTotals() || !mc?.can_export;
  const pedestrianDisabled = active || !isRoadTotals() || !mc?.recording || mcPedestrianSaving;
  $('mcPedestrianTotal').disabled = pedestrianDisabled;
  $('mcSavePedestrian').disabled = pedestrianDisabled || !mcPedestrianDirty;
  $('mcRoadDownload').hidden = active || !isRoadTotals() || !mc?.can_export || mcPedestrianDirty || mcPedestrianSaving;
  text('mcPedestrianStatus', mcPedestrianSaving ? 'Saving pedestrian total…'
    : mcPedestrianDirty ? 'Save the pedestrian total to include your changes in the CSV.'
    : mc?.pedestrian_total == null ? '' : `Saved for this video: ${mc.pedestrian_total} pedestrians.`);
  $('mcUndo').disabled = !canCount() || !currentPass()?.count;
  for (const button of $('mcGrid').querySelectorAll('button')) button.disabled = !canCount();
  for (const button of $('mcPasses').querySelectorAll('button')) button.disabled = active || button.dataset.canComplete === 'false';
  updateOperation();
}

async function runTask(label, message, work, changingRecording = false) {
  if (locked()) return;
  clientTask = {label, message};
  updateControls();
  try {
    if (changingRecording) {
      player.pause();
      mcVideo.pause();
      await mcFlush();
    }
    await work();
    await refreshState();
  } finally {
    clientTask = null;
    updateControls();
  }
}

function fileSize(bytes) {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GiB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MiB`;
  return `${Math.max(1, Math.round(bytes / 1024)).toLocaleString()} KiB`;
}

function uploadVideo(file, metadata) {
  if (!file?.size || file.size > 8 * 1024 ** 3) throw Error('Choose a video file up to 8 GiB.');
  if (!/\.(mp4|mov|mkv|avi|webm|m4v|mts)$/i.test(file.name)) throw Error(`Choose a supported video file (${videoFormats}).`);
  const params = new URLSearchParams({name: file.name, ...metadata});
  return runTask('Copying video', file.name, () => new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open('POST', '/api/upload?' + params);
    request.responseType = 'json';
    request.setRequestHeader('X-Observer-Token', token);
    request.setRequestHeader('Content-Type', 'application/octet-stream');
    request.upload.onprogress = event => {
      clientTask.progress = Math.min(100, 100 * event.loaded / file.size);
      clientTask.detail = `${fileSize(event.loaded)} / ${fileSize(file.size)}`;
      updateOperation();
    };
    request.upload.onload = () => {
      clientTask.progress = 100;
      clientTask.detail = `${fileSize(file.size)} transferred`;
      updateOperation();
    };
    request.onload = () => {
      if (request.status >= 200 && request.status < 300 && request.response?.ok) resolve();
      else reject(Error(request.response?.error || 'The local tool could not save this video.'));
    };
    request.onerror = () => reject(Error('The copy was interrupted. Keep the launcher open, then try loading the video again.'));
    request.onabort = () => reject(Error('The copy was interrupted.'));
    request.send(file);
  }), true);
}
function lineDraw(line, color) {
  const {a, b} = line;
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = Math.max(2, config.width / 350);
  ctx.beginPath();
  ctx.moveTo(...a);
  ctx.lineTo(...b);
  ctx.stroke();
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const length = Math.hypot(dx, dy);
  if (!length) return;
  const sign = line.direction === 'positive_to_negative' ? -1 : 1;
  const arrowLength = Math.max(16, config.width / 35);
  const arrowX = -dy * sign * arrowLength / length;
  const arrowY = dx * sign * arrowLength / length;
  const midX = (a[0] + b[0]) / 2;
  const midY = (a[1] + b[1]) / 2;
  const tipX = midX + arrowX;
  const tipY = midY + arrowY;
  ctx.beginPath();
  ctx.moveTo(midX - arrowX, midY - arrowY);
  ctx.lineTo(tipX, tipY);
  ctx.moveTo(tipX - arrowX / 2 - arrowY / 3, tipY - arrowY / 2 + arrowX / 3);
  ctx.lineTo(tipX, tipY);
  ctx.lineTo(tipX - arrowX / 2 + arrowY / 3, tipY - arrowY / 2 - arrowX / 3);
  ctx.stroke();
  ctx.font = `bold ${Math.max(14, config.width / 45)}px system-ui`;
  ctx.fillText(line.id, a[0], Math.max(20, a[1] - 9));
}

function draw() {
  if (!config || !reference.complete || !reference.naturalWidth) return;
  canvas.width = config.width;
  canvas.height = config.height;
  ctx.drawImage(reference, 0, 0, config.width, config.height);
  if (!['ready', 'cancelled', 'error'].includes(state.status)) return;
  for (const line of config.lines) lineDraw(line, '#3cffad');
  if (points.length === 2) {
    lineDraw({a: points[0], b: points[1], direction: $('direction').value, id: 'Pending'}, '#ffcf56');
  } else if (points.length === 1) {
    ctx.fillStyle = '#ffcf56';
    ctx.beginPath();
    ctx.arc(...points[0], 8, 0, Math.PI * 2);
    ctx.fill();
  }
}
function lineList() {
  const lines = config?.lines || [];
  const list = $('lineList');
  list.hidden = !lines.length;
  list.replaceChildren();
  for (const line of lines) {
    const item = document.createElement('li');
    const button = document.createElement('button');
    item.textContent = `${line.id} · ${line.event_type.replaceAll('_', ' ')} `;
    button.textContent = 'Remove';
    button.className = 'secondary';
    button.setAttribute('aria-label', `Remove ${line.id}`);
    button.onclick = () => {
      config.lines = config.lines.filter(row => row.id !== line.id);
      lineList();
      draw();
    };
    item.append(button);
    list.append(item);
  }
  for (const id of ['eventLine', 'coverageLine']) {
    const field = $(id);
    const previous = field.value;
    field.replaceChildren(...lines.map(line => new Option(line.id, line.id)));
    if (lines.some(line => line.id === previous)) field.value = previous;
  }
  updateControls();
}
canvas.onclick = event => {
  if (!canDraw()) return;
  const bounds = canvas.getBoundingClientRect();
  if (points.length === 2) points = [];
  points.push([
    Math.max(0, Math.min(config.width - 1, Math.round((event.clientX - bounds.left) * config.width / bounds.width))),
    Math.max(0, Math.min(config.height - 1, Math.round((event.clientY - bounds.top) * config.height / bounds.height)))
  ]);
  updateControls();
  draw();
};
$('direction').onchange=draw;
action('clearPoints',async()=>{points=[];updateControls();draw();});
action('addLine', () => {
  if (!canDraw() || points.length !== 2) throw Error('Click two endpoints first.');
  const id = $('lineId').value.trim();
  const location = $('location').value.trim();
  const place = $('place').value.trim();
  const kind = $('lineType').value;
  if (![id, location, place].every(value => /^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$/.test(value))) {
    throw Error('IDs need 1–80 letters, digits, underscores or hyphens.');
  }
  if (config.lines.some(line => line.id === id)) throw Error('Choose a different line ID.');
  const [a, b] = points;
  if (Math.hypot(b[0] - a[0], b[1] - a[1]) <= config.deadband_px * 2) throw Error('The counting line is too short.');
  const vehicle = kind.startsWith('vehicle_');
  config.lines.push({id, event_type: kind, location_id: location, approach_id: vehicle ? place : '',
    crossing_id: vehicle ? '' : place, a, b, direction: $('direction').value});
  points = [];
  lineList();
  draw();
});
$('videoFile').onchange = () => {
  const file = $('videoFile').files[0];
  text('chosenFile', file ? `${file.name} · ${fileSize(file.size)}` : `${videoFormats} · up to 8 GiB`);
  updateControls();
};
action('upload', () => {
  const collector = $('researcher').value.trim();
  if (!collector) {
    $('researcher').focus();
    throw Error('Enter the researcher name.');
  }
  return uploadVideo($('videoFile').files[0], {
    survey_id: $('survey').value.trim(), intersection_id: $('intersection').value.trim(), collector,
    source_kind: $('sourceKind').value, start: $('startTime').value.trim(), clock_note: $('clockNote').value.trim()
  });
});
action('demo', () => runTask('Loading demo', 'Preparing a scripted recording.', async () => {
  await post('/api/demo', {});
  if (!$('researcher').value) $('researcher').value = 'Demo reviewer';
}, true));
$('rotation').onchange = async () => {
  const previous = config.rotation_clockwise;
  try {
    if (config.lines.length && !confirm('Rotating clears the current counting lines. Continue?')) {
      $('rotation').value = previous;
      return;
    }
    await runTask('Rotating preview', '', async () => {
      await post('/api/rotate', {rotation: Number($('rotation').value)});
      acceptConfig = true;
    });
  } catch (exc) {
    $('rotation').value = previous;
    error(exc.message);
  }
};
action('analyze', () => runTask('Starting analysis', 'Checking the counting lines.', () => post('/api/analyze', {
  config, confidence: Number($('confidence').value)
})));
action('stop', async () => { await post('/api/stop', {}); await refreshState(); });

async function saved() {
  const rows = await get('/api/saved');
  for (const id of ['saved', 'mcSaved']) {
    const field = $(id);
    const selection = field.value;
    field.replaceChildren(new Option(rows.length ? 'Choose a saved recording' : 'No saved recordings', ''),
      ...rows.map(row => new Option(row.name + (row.demo ? ' (scripted)' : ''), row.id)));
    field.value = rows.some(row => row.id === selection) ? selection : state.project_id || '';
    if (field.selectedIndex < 0) field.value = '';
  }
  updateControls();
}

function openRecording(field) {
  const id = $(field).value;
  const name = $(field).selectedOptions[0]?.text;
  return runTask('Opening recording', name, async () => {
    await post('/api/open', {id});
    acceptConfig = true;
  }, true);
}
$('saved').onchange = updateControls;
$('mcSaved').onchange = updateControls;
action('openSaved', () => openRecording('saved'));
function counts(rows){const totals={vehicle_arrival:0,vehicle_discharge:0,pedestrian_start:0,pedestrian_complete:0};$('countsBody').replaceChildren();for(const row of rows){totals[row.kind]=(totals[row.kind]||0)+row.count;const tr=document.createElement('tr');for(const text of [row.line,row.class,row.count]){const td=document.createElement('td');td.textContent=text;tr.append(td);}$('countsBody').append(tr);}$('arrivals').textContent=totals.vehicle_arrival;$('discharges').textContent=totals.vehicle_discharge;$('starts').textContent=totals.pedestrian_start;$('completions').textContent=totals.pedestrian_complete;}
function playbackCounts(){if(player.hidden)return;const grouped=new Map();for(const event of proposals){if(Number(event.time_s)>player.currentTime+0.001)continue;const key=event.line_id+'|'+event.event_type+'|'+event.detected_class;if(!grouped.has(key))grouped.set(key,{line:event.line_id,kind:event.event_type,class:event.detected_class,count:0});grouped.get(key).count++;}counts([...grouped.values()]);$('timing').textContent=`Playback ${player.currentTime.toFixed(2)} / ${state.duration.toFixed(2)} seconds · automatic proposals`;}
player.ontimeupdate=playbackCounts;player.onloadedmetadata=playbackCounts;
async function loadEvents() {
  const data = await get('/api/events');
  events = data.events;
  proposals = data.proposals;
  text('coverageList', data.coverage.map(row => `${row.location_id}: ${row.start_s}–${row.end_s} s, ${row.visibility}`).join(' · ')
    || 'No reviewed coverage recorded yet.');
  renderEvents();
}

function renderEvents() {
  const filter = $('reviewFilter').value;
  const pending = events.filter(event => event.review_status === 'proposed').length;
  const filtered = events.filter(event => filter === 'all' || (event.review_status === 'proposed') === (filter === 'proposed'));
  const pageCount = Math.ceil(filtered.length / 20);
  page = Math.max(0, Math.min(page, pageCount - 1));
  $('eventsBody').replaceChildren();
  const suggestions = new Map(proposals.map(event => [event.event_id, event.detected_class]));
  for (const event of filtered.slice(page * 20, (page + 1) * 20)) {
    const tr = $('eventsBody').insertRow();
    const reviewedClass = event.reviewed_class + (event.vehicle_subtype ? ` · ${event.vehicle_subtype}` : '');
    for (const value of [`${Number(event.time_s).toFixed(2)} s`, `${event.event_type.replaceAll('_', ' ')} · ${event.location_id}`,
      suggestions.get(event.event_id) || 'Manual addition', reviewedClass, event.review_status]) {
      tr.insertCell().textContent = value;
    }
    const button = document.createElement('button');
    button.textContent = 'Review';
    button.className = 'secondary';
    button.onclick = () => edit(event);
    tr.insertCell().append(button);
  }
  text('reviewSummary', `${pending} need review · ${events.length - pending} reviewed`);
  text('pageLabel', pageCount ? `${page + 1} / ${pageCount} · ${filtered.length} events` : 'No matching events');
  $('prev').disabled = page === 0;
  $('next').disabled = page + 1 >= pageCount;
}
$('reviewFilter').onchange = () => { page = 0; renderEvents(); };
action('prev',async()=>{page--;renderEvents();});action('next',async()=>{page++;renderEvents();});
function edit(event) {
  selected = event;
  $('reviewEditor').hidden = false;
  text('reviewTitle', event ? `Review ${event.event_id}` : 'Add a missed event');
  $('eventLine').disabled = Boolean(event);
  $('eventTime').value = event ? event.time_s : player.currentTime.toFixed(3);
  $('eventClass').value = event?.reviewed_class || (event?.event_type.startsWith('pedestrian_') ? 'person' : 'unknown');
  $('subtype').value = event?.vehicle_subtype || '';
  $('decision').value = event && event.review_status !== 'proposed' ? event.review_status : 'accepted';
  $('episode').value = event?.episode_id || '';
  $('reviewNote').value = event?.note || '';
  $('eventExit').replaceChildren(new Option('Not observed', ''), ...(config?.lines || [])
    .filter(line => line.event_type === 'vehicle_discharge').map(line => new Option(line.id, line.id)));
  $('eventExit').value = event?.exit_id || '';
  if (event && !player.hidden) {
    player.pause();
    player.currentTime = Number(event.time_s);
  }
  $('reviewEditor').scrollIntoView({block: 'nearest'});
}
action('addMissed',async()=>edit(null));
action('closeReview', () => { $('reviewEditor').hidden = true; });
action('queuePlayhead', () => { $('queueTime').value = player.currentTime.toFixed(3); });
$('subtype').onchange=()=>{if($('subtype').value)$('eventClass').value='tricycle';};
$('eventClass').onchange=()=>{if($('eventClass').value!=='tricycle')$('subtype').value='';};
action('saveReview',async()=>{await post('/api/review',{event_id:selected?.event_id||'',line_id:$('eventLine').value,time_s:Number($('eventTime').value),reviewed_class:$('eventClass').value,vehicle_subtype:$('subtype').value,review_status:$('decision').value,episode_id:$('episode').value,exit_id:$('eventExit').value,reviewer:$('researcher').value,note:$('reviewNote').value});$('reviewEditor').hidden=true;await loadEvents();});
action('saveCoverage',async()=>{await post('/api/coverage',{line_id:$('coverageLine').value,start_s:Number($('coverageStart').value),end_s:Number($('coverageEnd').value),visibility:$('visibility').value,full_pass:$('fullPass').checked,reviewer:$('researcher').value,note:$('coverageNote').value});await loadEvents();});
action('saveQueue',async()=>{const visibility=$('queueVisibility').value,count=$('queueCount').value;if(visibility!=='unknown'&&count==='')throw Error('Enter the queue count.');await post('/api/queue',{time_s:Number($('queueTime').value),approach_id:$('queueApproach').value,queue_count:visibility==='unknown'?null:Number(count),visibility,reviewer:$('researcher').value,note:$('queueNote').value});});
action('savePair',async()=>{const value=id=>$(id).value===''?null:Number($(id).value);await post('/api/priority_pair',{movement_a:$('pairMovementA').value,movement_b:$('pairMovementB').value,priority_time_a_s:value('pairPriorityA'),priority_time_b_s:value('pairPriorityB'),entry_time_a_s:value('pairEntryA'),entry_time_b_s:value('pairEntryB'),readiness_of_earlier:$('pairReadiness').value,blocked_reason:$('pairReason').value,visibility:$('pairVisibility').value,reviewer:$('researcher').value,note:$('pairNote').value});});
$('queueVisibility').onchange=()=>{$('queueCount').disabled=$('queueVisibility').value==='unknown';if($('queueCount').disabled)$('queueCount').value='';};
function refreshQueueApproaches(){const select=$('queueApproach'),previous=select.value;select.replaceChildren();for(const approach of new Set((config?.lines||[]).map(line=>line.approach_id).filter(Boolean))){const option=document.createElement('option');option.value=option.textContent=approach;select.append(option);}if([...select.options].some(option=>option.value===previous))select.value=previous;}
action('export', () => runTask('Preparing export', 'Checking the reviewed observations.', () => post('/api/export', {
  reviewer: $('researcher').value, note: $('exportNote').value
})));

function mediaMessage(id, message) {
  text(id, message);
  $(id).hidden = !message;
}

function trackVideoLoading(video, messageId, label) {
  video.addEventListener('loadstart', () => mediaMessage(messageId, `Loading ${label}…`));
  video.addEventListener('waiting', () => {
    if (video.getAttribute('src')) mediaMessage(messageId, 'Buffering video…');
  });
  for (const event of ['loadeddata', 'canplay', 'playing', 'emptied']) {
    video.addEventListener(event, () => mediaMessage(messageId, ''));
  }
  video.addEventListener('error', () => {
    if (video.getAttribute('src')) {
      mediaMessage(messageId, 'This video could not play in the browser. Open the original in a local player to check the file and its format.');
    }
  });
}

function seek(video, seconds) {
  if (Number.isFinite(video.duration)) video.currentTime = Math.max(0, Math.min(video.duration, video.currentTime + seconds));
}
for (const button of document.querySelectorAll('[data-seek]')) {
  button.onclick = () => seek($(button.dataset.video), Number(button.dataset.seek));
}
$('replayRate').onchange = () => { player.playbackRate = Number($('replayRate').value); };
player.addEventListener('loadedmetadata', () => { player.playbackRate = Number($('replayRate').value); });
trackVideoLoading(player, 'replayMessage', 'annotated playback');

function renderPreview() {
  const replay = hasReplay();
  const imageReady = Boolean(config && reference.naturalWidth);
  const working = ['loading', 'analyzing', 'stopping'].includes(state.status);
  $('demoBanner').hidden = !state.demo;
  text('currentName', state.name || 'Recording preview');
  text('mode', replay ? 'Annotated playback' : working ? 'Analysis preview' : 'Source frame');
  $('mode').hidden = !config;
  $('lineFields').hidden = !config || replay;
  $('analysisControls').hidden = $('lineFields').hidden;
  text('outputPath', state.output_folder || '');
  $('outputPath').hidden = !state.output_folder;
  $('empty').hidden = imageReady || replay;
  canvas.hidden = !imageReady || replay;
  player.hidden = !replay;
  text('previewTitle', busy() || config ? 'Preparing preview' : 'No video loaded');
  text('previewHint', busy() ? 'The preview appears when the recording is ready.' : config
    ? 'Loading the first decoded frame.' : 'Load a video or choose a saved recording.');
  $('detectVideoBar').hidden = !config;
  $('original').hidden = !config;
  $('replayControls').hidden = !replay;
  $('metrics').hidden = !(replay || working || state.status === 'cancelled');
  $('proposalDetails').hidden = $('metrics').hidden;
  $('reviewSection').hidden = !replay;
  $('download').hidden = !state.has_export || busy();
  $('mcDownload').hidden = !state.has_export || busy();
  text('lineHint', replay ? 'The saved analysis fixes these lines for this recording.' : config
    ? `${config.lines.length} counting ${config.lines.length === 1 ? 'line' : 'lines'}` : 'Load a recording to draw counting lines.');
  if (!replay && config) {
    text('timing', working || state.status === 'cancelled'
      ? `${state.seconds.toFixed(2)} / ${state.duration.toFixed(2)} s`
      : `${config.width} × ${config.height} · ${state.duration.toFixed(2)} s`);
  }
}

async function syncState() {
  const next = await get('/api/state');
  const changedProject = next.project_id !== lastProject;
  const changedStatus = next.status !== state.status;
  const changedVersion = next.version !== lastVersion;
  state = next;
  connected = true;
  if (changedProject) {
    player.pause();
    player.removeAttribute('src');
    player.load();
    mediaMessage('replayMessage', '');
    lastProject = state.project_id;
    replayProject = null;
    reference = new Image();
    activeImage++;
    config = null;
    points = [];
    events = [];
    proposals = [];
    page = 0;
    $('reviewFilter').value = 'all';
    $('reviewEditor').hidden = true;
    lineList();
    renderEvents();
    mcProjectChanged();
  }
  if (state.config && (!config || acceptConfig)) {
    config = structuredClone(state.config);
    acceptConfig = false;
    points = [];
    $('rotation').value = config.rotation_clockwise;
    $('coverageEnd').value = state.duration;
    lineList();
    refreshQueueApproaches();
  }
  if (!hasReplay() && changedVersion) {
    counts(state.counts);
    if (config) {
      const imageVersion = ++activeImage;
      const image = new Image();
      image.onload = () => {
        if (imageVersion !== activeImage) return;
        reference = image;
        draw();
        renderPreview();
      };
      image.onerror = () => {
        if (imageVersion === activeImage) text('previewHint', 'The first frame could not load. Reopen the recording to retry.');
      };
      image.src = '/api/image?v=' + state.version;
    }
  }
  if (state.has_replay && replayProject !== state.project_id) {
    await loadEvents();
    replayProject = state.project_id;
    player.src = '/api/replay?v=' + state.version;
  }
  renderPreview();
  updateControls();
  if (lastVersion < 0 || (changedProject || changedStatus) && ['ready', 'complete'].includes(state.status)) {
    await saved();
  }
  if (mcView && (changedProject || changedStatus)) {
    mcProjectCheck();
    await mcLoad().catch(exc => error(exc.message));
  }
  lastVersion = state.version;
}

function refreshState() {
  const next = refreshQueue.then(syncState);
  refreshQueue = next.catch(() => {});
  return next;
}

async function poll() {
  try { await refreshState(); }
  catch {
    connected = false;
    updateControls();
  }
  finally { setTimeout(poll, 500); }
}

// Manual counting
const MC_KEYS = ['qwert', 'asdfg', 'zxcvb'];
const MC_LABEL = {car: 'Car', motorcycle: 'Motorcycle', tricycle: 'Tricycle', bus: 'Bus', truck: 'Truck'};
const mcVideo = $('mcVideo');
const SVG_NS = 'http://www.w3.org/2000/svg';
const MOVEMENT_HASH = '#manual-movements';
let mcMode = location.hash === MOVEMENT_HASH ? 'movements' : 'road_totals';
let mc = null;
let mcApproach = null;
let mcProject = null;
let mcView = false;
let mcWatch = null;
let mcWrites = Promise.resolve();
let mcPedestrianDirty = false;
let mcPedestrianSaving = false;

const capitalized = name => name[0].toUpperCase() + name.slice(1);
const shortStreet = street => street.replace('Davao-Agusan National Highway', 'National Highway')
  .replace('Capitol Circumferential Road', 'Capitol Circ. Rd').replace(/ Road$/, ' Rd').replace(/ Street$/, ' St');
const isRoadTotals = () => mcMode === 'road_totals';
const movementReviewBlocked = () => !isRoadTotals() && hasReplay();
const mcExits = () => mc?.site?.approaches.filter(approach => approach.id !== mcApproach) || [];
const currentPass = () => mc?.passes?.find(pass => pass.approach === mcApproach);
const canCount = () => Boolean(mc?.site && mcApproach && !currentPass()?.complete &&
  Number.isFinite(mcVideo.duration) && !locked() && !movementReviewBlocked());

function mcAction(fn) {
  return async (...args) => {
    error('');
    try { await fn(...args); }
    catch (exc) { error(exc.message); }
  };
}

async function readManualMode(mode) {
  const manual = await get('/api/manual?mode=' + mode);
  if (manual.mode !== mode) throw Error('Close and restart Field Observer to load the updated Manual count tool.');
  return manual;
}

async function mcLoad() {
  const project = state.project_id;
  const mode = mcMode;
  const manual = await readManualMode(mode);
  if (project !== state.project_id || mode !== mcMode) return;
  mc = manual;
  mcRender();
}

function updateManualHash() {
  const hash = isRoadTotals() ? '#manual' : MOVEMENT_HASH;
  history.replaceState(null, '', mcView ? hash : location.pathname + location.search);
}

async function mcShow(on) {
  mcView = on;
  $('detectView').hidden = on;
  $('manualView').hidden = !on;
  for (const [id, selected] of [['tabDetect', !on], ['tabManual', on]]) {
    $(id).classList.toggle('on', selected);
    $(id).setAttribute('aria-pressed', String(selected));
  }
  updateManualHash();
  updateOperation();
  if (on) {
    player.pause();
    mcProjectCheck();
    await mcLoad();
  } else {
    mcVideo.pause();
    await mcFlush();
  }
}

function mcProjectCheck() {
  const ready = Boolean(state.config) && ['ready', 'complete', 'exporting'].includes(state.status);
  $('mcNone').hidden = ready;
  mcVideo.hidden = !ready;
  $('mcVideoBar').hidden = !ready;
  $('mcShortcuts').hidden = !ready;
  text('mcName', state.name || 'Recording preview');
  text('mcPreviewTitle', busy() ? 'Preparing video' : 'No video loaded');
  text('mcPreviewHint', busy() ? 'The video will appear when its frames are indexed.'
    : 'Choose a study site and load a video, or open a saved recording.');
  if (ready && mcProject !== state.project_id) {
    mcProject = state.project_id;
    mcVideo.src = '/api/original?v=' + state.project_id;
  }
}

function mcProjectChanged() {
  mcWatch = null;
  mcApproach = null;
  mcProject = null;
  mc = null;
  mcPedestrianDirty = false;
  $('mcPedestrianTotal').value = '';
  mcVideo.pause();
  mcVideo.removeAttribute('src');
  mcVideo.load();
  mediaMessage('mcVideoMessage', '');
  mcRender();
}

function svgElement(tag, attributes, content) {
  const element = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value);
  if (content) element.textContent = content;
  return element;
}

function mcArm(approach, index) {
  const center = 180, roadWidth = 56, length = center - roadWidth / 2;
  const [x, y, width, height, vertical] = {
    north: [length, 0, roadWidth, length, true],
    south: [length, center + roadWidth / 2, roadWidth, length, true],
    west: [0, length, length, roadWidth, false],
    east: [center + roadWidth / 2, length, length, roadWidth, false]
  }[approach.id];
  const pass = mc.passes.find(item => item.approach === approach.id);
  const selected = approach.id === mcApproach;
  const status = pass.complete && pass.spans_video ? ' done' : pass.count ? ' some' : '';
  const label = isRoadTotals() ? 'Count vehicles going ' + approach.id : 'Count the ' + approach.id + ' approach';
  const arm = svgElement('g', {
    class: 'arm' + (selected ? ' sel' : '') + status,
    tabindex: 0, role: 'button', 'aria-pressed': selected, 'data-approach': approach.id,
    'aria-label': label + ', ' + approach.street
  });
  arm.append(svgElement('rect', {class: 'road', x, y, width, height}));
  for (let stripe = 0; stripe < 5; stripe++) {
    const offset = stripe * 10.4 + 2.4;
    const rect = vertical
      ? {x: x + offset, y: approach.id === 'north' ? height - 26 : y + 4, width: 6, height: 22}
      : {x: approach.id === 'west' ? width - 26 : x + 4, y: y + offset, width: 22, height: 6};
    arm.append(svgElement('rect', {class: 'zebra', ...rect}));
  }
  const labelX = vertical ? center + roadWidth / 2 + 10 : x + width / 2 + (approach.id === 'west' ? -14 : 14);
  const labelY = vertical ? (approach.id === 'north' ? 40 : y + height - 64) : center - 12;
  if (vertical) arm.append(svgElement('rect', {class: 'hit', x: length, y, width: roadWidth + 152, height}));
  const labels = [index + 1 + ' · ' + capitalized(approach.id), shortStreet(approach.street), pass.count + ' counted'];
  labels.forEach((label, i) => arm.append(svgElement('text', {
    class: vertical ? 'out' : '', x: labelX, y: labelY + 13 * i
  }, label)));
  arm.onclick = () => mcSelect(approach.id);
  arm.onkeydown = event => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      event.stopPropagation();
      mcSelect(approach.id);
    }
  };
  return arm;
}

function mcSelect(id) {
  if (locked() || movementReviewBlocked() || mcApproach === id) return;
  if (isRoadTotals()) mcVideo.pause();
  reportManualSave(mcFlush());
  mcApproach = id;
  const pass = currentPass();
  if (isRoadTotals() && Number.isFinite(mcVideo.duration) && !pass?.count && !pass?.watched_s) {
    mcVideo.currentTime = 0;
  }
  if (!mcVideo.paused && !mcVideo.seeking) mcTrack();
  mcRender();
}

function mcRender() {
  const recording = Boolean(mc?.recording && state.config);
  const roadTotals = isRoadTotals();
  const hasSite = Boolean(recording && mc.site && !movementReviewBlocked());
  const siteField = $('mcSite');
  const pendingSite = siteField.value;
  if (mc) {
    const options = () => [new Option('Choose a study site', ''),
      ...mc.sites.map(site => new Option(site.label, site.id))];
    siteField.replaceChildren(...options());
    siteField.value = pendingSite || mc.site_id || '';
    $('mcCountSite').replaceChildren(...options());
  }
  $('mcMode').value = mcMode;
  text('mcModeHint', roadTotals ? 'Choose the road vehicles are going into. Count each vehicle by type as it enters that road.'
    : 'Choose where vehicles come from, then record the exit and vehicle type for each one.');
  text('mcToolsTitle', roadTotals ? 'Road and count' : 'Approach and count');
  text('mcPassHeading', roadTotals ? 'Going toward' : 'Approach');
  text('mcPassHint', `Play the entire video for each ${roadTotals ? 'road' : 'approach'}, then mark that pass complete.`);
  $('mcTotalsExport').hidden = !roadTotals;
  if (roadTotals && !mcPedestrianDirty) $('mcPedestrianTotal').value = mc?.pedestrian_total ?? '';
  $('mcMovementExport').hidden = roadTotals;
  $('mcAssignSite').hidden = !recording || hasSite || movementReviewBlocked();
  $('mcMap').toggleAttribute('hidden', !hasSite);
  $('mcExportCard').hidden = !hasSite;
  $('mcGrid').hidden = !hasSite || !mcApproach;
  $('mcTally').hidden = $('mcGrid').hidden;
  $('mcBadge').hidden = !hasSite;
  for (const id of ['mcPasses', 'mcMap', 'mcGrid', 'mcRecent']) $(id).replaceChildren();
  if (!hasSite) {
    text('mcPick', movementReviewBlocked() ? 'This recording has a detector review. You can still use Road totals for this video.'
      : recording ? 'Assign a study site to this recording, then choose a road.' : 'Load a recording to start a pass.');
    updateControls();
    return;
  }
  const pass = currentPass();
  const approach = mc.site.approaches.find(item => item.id === mcApproach);
  const focused = document.activeElement?.dataset;
  const direction = roadTotals ? 'Going toward ' : 'Incoming from ';
  text('mcPick', approach ? direction + capitalized(approach.id) + ' · ' + approach.street
    : roadTotals ? 'Choose the road vehicles are going into on the map.' : 'Choose an incoming approach on the map.');
  $('mcMap').append(svgElement('rect', {class: 'core', x: 152, y: 152, width: 56, height: 56}),
    ...mc.site.approaches.map(mcArm));
  if (pass) renderCountGrid(pass);
  for (const item of mc.passes) {
    const done = item.complete && item.spans_video;
    const row = $('mcPasses').insertRow();
    row.insertCell().textContent = capitalized(item.approach);
    row.insertCell().textContent = item.count;
    row.insertCell().textContent = Math.min(100, Math.round(100 * item.watched_s / mc.duration)) + '%' +
      (item.spans_video ? ' · no gaps' : '');
    const status = row.insertCell();
    status.textContent = done ? 'Complete' : item.count || item.watched_s ? 'In progress' : 'Not started';
    if (done) status.className = 'mcdone';
    const button = document.createElement('button');
    button.className = 'secondary';
    button.textContent = item.complete ? 'Reopen' : 'Mark complete';
    button.dataset.canComplete = String(item.spans_video || item.complete);
    button.onclick = mcAction(async () => {
      if (item.approach === mcApproach) mcVideo.pause();
      await mcPost('/api/manual/complete', {approach: item.approach, complete: !item.complete});
    });
    row.insertCell().append(button);
  }
  text('mcBadge', mc.passes.filter(item => item.complete && item.spans_video).length + ' / ' + mc.passes.length + ' passes complete');
  const focusKey = focused?.approach ? 'approach' : 'countKey';
  const currentFocus = [...$('mcTools').querySelectorAll('[data-approach], [data-count-key]')]
    .find(element => focused?.[focusKey] && element.dataset[focusKey] === focused[focusKey]);
  currentFocus?.focus({preventScroll: true});
  updateControls();
}

function renderCountGrid(pass) {
  const grid = $('mcGrid');
  const roadTotals = isRoadTotals();
  grid.classList.toggle('road-totals', roadTotals);
  if (!roadTotals) {
    grid.append(document.createElement('span'));
    for (const category of mc.site.classes) {
      grid.append(Object.assign(document.createElement('div'), {className: 'h', textContent: MC_LABEL[category]}));
    }
  }
  const rows = roadTotals ? [null] : mcExits();
  rows.forEach((exit, row) => {
    if (exit) {
      grid.append(Object.assign(document.createElement('div'), {
        className: 'r', textContent: '→ ' + capitalized(exit.id) + ' · ' + shortStreet(exit.street)
      }));
    }
    mc.site.classes.forEach((category, column) => {
      const key = MC_KEYS[row][column];
      const tally = pass.tally[exit ? exit.id + '|' + category : category] || 0;
      const button = document.createElement('button');
      button.dataset.countKey = key;
      button.title = MC_LABEL[category] + ' going ' + (exit?.id || mcApproach);
      button.setAttribute('aria-label', button.title + ', ' + tally + ' counted, shortcut ' + key);
      button.disabled = !canCount();
      button.onmousedown = event => event.preventDefault();
      const hint = Object.assign(document.createElement('kbd'), {textContent: key.toUpperCase()});
      if (roadTotals) {
        const label = Object.assign(document.createElement('span'), {textContent: MC_LABEL[category]});
        const count = Object.assign(document.createElement('strong'), {textContent: String(tally)});
        button.append(label, count, hint);
      } else button.append(hint, String(tally));
      button.onclick = () => mcClick(exit?.id, category, key);
      grid.append(button);
    });
  });
  $('mcUndo').disabled = !pass.count || !canCount();
  const unit = pass.count === 1 ? ' vehicle' : ' vehicles';
  text('mcTotal', pass.count + unit + (roadTotals ? ' going ' + capitalized(mcApproach) : ' in this pass') + (pass.complete ? ' · complete' : ''));
  for (const click of pass.recent) {
    $('mcRecent').append(Object.assign(document.createElement('li'), {
      textContent: click.time_s.toFixed(2) + ' s · ' + MC_LABEL[click.class] + (click.exit ? ' → ' + click.exit : '')
    }));
  }
}

function queueManualWrite(route, data) {
  const project = state.project_id;
  const mode = mcMode;
  const write = mcWrites.then(async () => {
    if (project !== state.project_id) return;
    const result = await post(route, {...data, mode});
    if (project === state.project_id && mode === mcMode && result.manual) {
      mc = result.manual;
      if (mcView) mcRender();
    }
  });
  mcWrites = write.catch(() => {});
  return write;
}

function mcFlush() {
  const interval = mcWatch;
  mcWatch = null;
  if (!interval || interval.end <= interval.start) return mcWrites;
  return queueManualWrite('/api/manual/watched', interval);
}

function reportManualSave(write) {
  write.catch(exc => error(exc.message));
}

async function mcPost(route, data) {
  const watched = mcFlush();
  const write = queueManualWrite(route, data);
  await Promise.all([watched, write]);
}

const mcClick = mcAction(async (exit, category, key) => {
  if (!canCount()) return;
  const data = {approach: mcApproach, class: category, time_s: mcVideo.currentTime};
  if (exit) data.exit = exit;
  await mcPost('/api/manual/click', data);
  const button = $('mcGrid').querySelector('[data-count-key="' + key + '"]');
  if (button) {
    button.classList.add('hit');
    setTimeout(() => button.classList.remove('hit'), 150);
  }
});
const mcUndo = mcAction(async () => {
  if (canCount() && currentPass()?.count) await mcPost('/api/manual/undo', {approach: mcApproach});
});
$('mcUndo').onclick = mcUndo;
$('mcPedestrianTotal').oninput = () => {
  mcPedestrianDirty = true;
  updateControls();
};
action('mcSavePedestrian', async () => {
  const input = $('mcPedestrianTotal');
  const count = input.value === '' ? null : input.valueAsNumber;
  if (!input.validity.valid || (count !== null && !Number.isSafeInteger(count))) {
    throw Error('Enter a nonnegative whole number for pedestrians, or leave it blank.');
  }
  mcPedestrianSaving = true;
  updateControls();
  try {
    await queueManualWrite('/api/manual/pedestrians', {count});
    mcPedestrianDirty = false;
  } finally {
    mcPedestrianSaving = false;
    mcRender();
  }
});
$('mcSite').onchange = updateControls;
$('mcFile').onchange = updateControls;
$('mcCountSite').onchange = mcAction(async () => {
  if ($('mcCountSite').value) await mcPost('/api/manual/site', {site: $('mcCountSite').value});
});
$('mcMode').onchange = mcAction(async () => {
  const mode = $('mcMode').value;
  if (mode === mcMode) return;
  try {
    await runTask('Opening count mode', 'Restoring saved passes.', async () => {
      mcVideo.pause();
      await mcFlush();
      const manual = await readManualMode(mode);
      mcMode = mode;
      mc = manual;
      mcApproach = null;
      updateManualHash();
      mcRender();
    });
  } finally {
    $('mcMode').value = mcMode;
  }
});
$('mcRate').onchange = () => { mcVideo.playbackRate = Number($('mcRate').value); };
mcVideo.addEventListener('loadedmetadata', () => {
  mcVideo.playbackRate = Number($('mcRate').value);
  if (mcView) mcRender();
});
trackVideoLoading(mcVideo, 'mcVideoMessage', 'original video');
action('mcExport', () => runTask('Preparing export', 'Checking all four approach passes.', async () => {
  mcVideo.pause();
  await mcFlush();
  await post('/api/manual/export', {mode: mcMode, note: $('mcNote').value});
}));
action('mcLoad', () => uploadVideo($('mcFile').files[0], {site: $('mcSite').value}));
action('mcOpen', () => openRecording('mcSaved'));
action('tabDetect', () => mcShow(false));
action('tabManual', () => mcShow(true));

function mcTrack() {
  if (!mcView || !canCount()) return;
  const time = mcVideo.currentTime;
  if (mcWatch?.approach === mcApproach && time >= mcWatch.end && time - mcWatch.end <= 1) {
    mcWatch.end = time;
  } else {
    reportManualSave(mcFlush());
    mcWatch = {approach: mcApproach, start: time, end: time};
  }
}
mcVideo.ontimeupdate = () => {
  text('mcTime', mcVideo.currentTime.toFixed(2) + ' s');
  if (!mcVideo.paused && !mcVideo.seeking) mcTrack();
};
mcVideo.onplay = mcTrack;
mcVideo.onpause = () => {
  if (!mcVideo.seeking && mcWatch) {
    if (mcVideo.ended) mcWatch.end = mcVideo.duration;
    else mcTrack();
  }
  reportManualSave(mcFlush());
};
mcVideo.onseeking = () => reportManualSave(mcFlush());
mcVideo.onended = () => {
  if (mcWatch) mcWatch.end = mcVideo.duration;
  reportManualSave(mcFlush());
};
setInterval(() => {
  if (mcWatch && !mcVideo.paused) {
    const time = mcVideo.currentTime;
    const approach = mcWatch.approach;
    reportManualSave(mcFlush());
    mcWatch = {approach, start: time, end: time};
  }
}, 3000);

document.addEventListener('keydown', event => {
  if (!mcView || !mcProject || locked() || event.altKey || event.metaKey ||
      event.target.closest('input, select, textarea, video, [contenteditable]')) return;
  const key = event.key.toLowerCase();
  if (key === ' ' && !event.target.closest('button, a, summary')) {
    if (mcVideo.paused) mcVideo.play().catch(exc => error(exc.message));
    else mcVideo.pause();
  } else if (key === 'backspace' || (event.ctrlKey && key === 'z')) mcUndo();
  else if (key === 'arrowleft') seek(mcVideo, -2);
  else if (key === 'arrowright') seek(mcVideo, 2);
  else if (/^[1-4]$/.test(key) && mc?.site) mcSelect(mc.site.approaches[Number(key) - 1].id);
  else if (!event.ctrlKey && !event.repeat && canCount()) {
    const row = MC_KEYS.findIndex(keys => keys.includes(key));
    if (row < 0 || row >= (isRoadTotals() ? 1 : mcExits().length)) return;
    const exit = isRoadTotals() ? undefined : mcExits()[row].id;
    mcClick(exit, mc.site.classes[MC_KEYS[row].indexOf(key)], key);
  } else return;
  event.preventDefault();
});

if (location.hash === '#manual' || location.hash === MOVEMENT_HASH) mcShow(true).catch(exc => error(exc.message));
updateControls();
poll();
