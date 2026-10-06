(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const state = { schema: null, table: null, page: 1, pageSize: 25, sort: null, direction: 'asc', search: '', pending: false, turns: 0, mapPositions: {} };
  const privacy = {
    schemaOnly: localStorage.getItem('sheet-schema-only') === 'true',
    noRows: localStorage.getItem('sheet-no-result-rows') === 'true'
  };
  const progressNames = { understanding: 'Reading your question', writing: 'Planning the calculation', running: 'Calculating', verifying: 'Preparing your answer' };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  async function request(url, options = {}) {
    const response = await fetch(url, { credentials: 'same-origin', ...options });
    const type = response.headers.get('content-type') || '';
    const body = type.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok) {
      const failure = new Error(body?.error?.message || body?.detail || `Request failed (${response.status}).`);
      failure.code = body?.error?.code || 'request_failed';
      failure.status = response.status;
      throw failure;
    }
    return body;
  }

  function toast(message) {
    const box = $('#toast'); box.textContent = message; box.hidden = false;
    clearTimeout(toast.timer); toast.timer = setTimeout(() => { box.hidden = true; }, 4500);
  }

  function showError(message) {
    const box = $('#global-message'); box.textContent = message; box.hidden = false;
  }

  function hideError() { $('#global-message').hidden = true; }

  function tableByName(name) { return state.schema?.tables.find(table => table.name === name); }

  function displayName(table) { return table?.alias || table?.sheet || table?.name || 'Table'; }
  function displayType(type) { return ({ number: 'Number', currency: 'Currency', percent: 'Percent', date: 'Date', boolean: 'Yes or no', text: 'Text' })[type] || 'Text'; }

  function setView(name) {
    for (const view of ['chat', 'explorer', 'map']) $(`#${view}-view`).hidden = view !== name;
    document.querySelectorAll('.nav-item').forEach(button => button.classList.toggle('active', button.dataset.view === name));
    $('#view-label').textContent = ({ chat: 'Ask', explorer: 'Browse files', map: 'Connections' })[name] || name;
    if (name === 'map') drawMap();
    if (name === 'explorer' && state.table) loadPreview();
  }

  function hydrateSchema(data) {
    state.schema = data;
    const tables = data.tables || [];
    if (!tables.some(table => table.name === state.table)) state.table = tables[0]?.name || null;
    $('#dataset-pill').textContent = `${tables.length} worksheets · ${tables.reduce((sum, table) => sum + table.row_count, 0).toLocaleString()} rows`;
    $('#table-list').replaceChildren();
    for (const table of tables) {
      const button = el('button', 'source-item' + (table.name === state.table ? ' selected' : ''));
      button.type = 'button'; button.dataset.table = table.name;
      button.append(el('span', 'source-icon', '▤'));
      const details = el('span'); details.append(el('strong', '', displayName(table)), el('small', '', `${table.row_count.toLocaleString()} rows · ${table.columns.length} fields`));
      button.append(details); button.addEventListener('click', () => { state.table = table.name; setView('explorer'); hydrateSchema(state.schema); });
      $('#table-list').append(button);
    }
    $('#explorer-table').replaceChildren();
    for (const table of tables) {
      const option = el('option', '', displayName(table)); option.value = table.name;
      $('#explorer-table').append(option);
    }
    if (state.table) $('#explorer-table').value = state.table;
    $('#example-chips').replaceChildren();
    for (const example of (data.examples || []).slice(0, 6)) {
      const button = el('button', 'example-chip'); button.type = 'button'; button.append(el('span', '', example), el('span', '', '↗'));
      button.addEventListener('click', () => submitQuestion(example)); $('#example-chips').append(button);
    }
    if (data.warnings?.length) {
      const warning = el('div', 'warning-strip', data.warnings.join(' · '));
      $('#global-message').replaceChildren(warning); $('#global-message').hidden = false;
    }
    drawMap();
  }

  async function refreshSchema(endpoint = '/api/schema') {
    try { hydrateSchema(await request(endpoint)); hideError(); }
    catch (error) { showError(error.message || 'Could not load spreadsheet data.'); }
  }

  function addQuestion(text) {
    const bubble = el('div', 'question-bubble'); bubble.append(el('span', 'question-avatar', 'You'), el('span', '', text));
    $('#conversation').append(bubble); $('#welcome').hidden = true;
  }

  function setProgress(stage) {
    $('#progress').hidden = false; $('#progress-message').textContent = progressNames[stage] || 'Working';
  }

  function friendlyFailure(error) {
    const messages = {
      missing_key: 'Set up the online answer service in local settings, then restart Insight Flow.',
      invalid_key: 'The online answer service did not accept its key. Check local settings.',
      offline: 'The online answer service could not be reached. Check your connection and try again.',
      quota_exhausted: 'The online answer service is busy. Wait a moment and try again.',
      budget_exhausted: 'You have reached the usage limit for this session.',
      model_not_found: 'The online answer service is unavailable. Check local settings.',
      timeout: 'The answer took too long. Try again.',
      empty_data: 'No files are loaded. Add a workbook or reload your files.',
      query_failed: 'The answer could not be checked. Try another question or browse your files.',
      upstream_error: 'The answer service is temporarily unavailable. Try again shortly.',
      invalid_response: 'The answer could not be prepared. Try a different question.'
    };
    return messages[error.code] || error.message || 'The request could not be completed.';
  }

  async function submitQuestion(question) {
    const text = (question || $('#question').value).trim();
    if (!text || state.pending) return;
    state.pending = true; $('#ask-button').disabled = true; hideError();
    addQuestion(text); $('#question').value = ''; $('#progress').hidden = false; $('#slow-message').textContent = ''; setProgress('understanding');
    let accumulated = '';
    const slowTimer = setTimeout(() => { $('#slow-message').textContent = 'Working on your answer…'; }, 8000);
    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text, schema_only: privacy.schemaOnly, dont_send_result_rows: privacy.noRows })
      });
      if (!response.ok) {
        let info = {}; try { info = await response.json(); } catch (_) {}
        const error = new Error(info.error?.message || `Request failed (${response.status}).`); error.code = info.error?.code; throw error;
      }
      const reader = response.body.getReader(), decoder = new TextDecoder();
      while (true) {
        const { value, done } = await reader.read(); if (done) break;
        accumulated += decoder.decode(value, { stream: true });
        const events = accumulated.split('\n\n'); accumulated = events.pop() || '';
        for (const raw of events) {
          const event = raw.match(/^event:\s*(.+)$/m)?.[1];
          const payload = raw.match(/^data:\s*(.+)$/m)?.[1]; if (!payload) continue;
          const data = JSON.parse(payload);
          if (event === 'progress') setProgress(data.stage);
          else if (event === 'result') renderResponse(data, text);
          else if (event === 'error') { const error = new Error(data.error?.message || 'Request failed'); error.code = data.error?.code; throw error; }
        }
      }
      if (accumulated.trim()) {
        const payload = accumulated.match(/^data:\s*(.+)$/m)?.[1]; if (payload) renderResponse(JSON.parse(payload), text);
      }
      state.turns++;
    } catch (error) {
      renderStatus(friendlyFailure(error), 'error');
    } finally {
      clearTimeout(slowTimer); $('#slow-message').textContent = ''; $('#progress').hidden = true;
      state.pending = false; $('#ask-button').disabled = false; $('#question').focus();
      refreshSchema();
    }
  }

  function renderStatus(message, kind = 'info', options = null) {
    const card = el('section', 'status-card'); card.append(el('h3', '', kind === 'error' ? 'Could not finish' : kind === 'refused' ? 'Files are read-only' : 'Choose an option'));
    card.append(el('p', '', message));
    if (options?.length) {
      const row = el('div', 'clarification-options');
      options.forEach(option => { const button = el('button', '', option); button.type = 'button'; button.addEventListener('click', () => submitQuestion(`${options.question || 'Please answer this question'}: ${option}`)); row.append(button); });
      card.append(row);
    }
    $('#conversation').append(card); card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function safeTable(columns, rows, options = {}) {
    const wrap = el('div', 'table-container'); const table = el('table');
    const thead = el('thead'), header = el('tr');
    columns.forEach((column, index) => {
      const th = el('th'); if (options.sortable) {
        const button = el('button', '', `${column}${options.sort === column ? (options.direction === 'asc' ? ' ↑' : ' ↓') : ''}`);
        button.type = 'button'; if (options.numeric?.includes(index)) th.className = 'numeric';
        button.addEventListener('click', () => options.onSort?.(column)); th.append(button);
      } else { th.textContent = column; if (options.numeric?.includes(index)) th.className = 'numeric'; }
      header.append(th);
    });
    thead.append(header); table.append(thead);
    const body = el('tbody');
    rows.forEach(row => {
      const tr = el('tr');
      columns.forEach((column, index) => {
        const value = Array.isArray(row) ? row[index] : row[column]; const td = el('td', options.numeric?.includes(index) ? 'numeric' : '', value === null || value === undefined ? '-' : typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 4 }) : value);
        tr.append(td);
      }); body.append(tr);
    });
    table.append(body); wrap.append(table); return wrap;
  }

  function makeChart(chart, columns, rows) {
    if (!chart || !rows?.length) return null;
    const labelIndex = columns.indexOf(chart.label_column), valueIndex = columns.indexOf(chart.value_columns?.[0]);
    if (labelIndex < 0 || valueIndex < 0) return null;
    const values = rows.map(row => ({ label: String(row[chart.label_column] ?? ''), value: Number(row[chart.value_columns[0]]) || 0 })).slice(0, 20);
    const max = Math.max(1, ...values.map(item => Math.abs(item.value))), svgNS = 'http://www.w3.org/2000/svg';
    const width = 760, rowHeight = 28, height = chart.type === 'pie' ? 330 : chart.type === 'line' ? 280 : Math.max(90, values.length * rowHeight + 18);
    const svg = document.createElementNS(svgNS, 'svg'); svg.setAttribute('viewBox', `0 0 ${width} ${height}`); svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', 'Results chart');
    const svgText = (x, y, textValue, size = 10) => { const text = document.createElementNS(svgNS, 'text'); text.setAttribute('x', String(x)); text.setAttribute('y', String(y)); text.setAttribute('fill', '#a9bdb0'); text.setAttribute('font-size', String(size)); text.textContent = textValue; svg.append(text); };
    if (chart.type === 'pie') {
      const total = values.reduce((sum, item) => sum + Math.max(0, item.value), 0) || 1; let angle = -Math.PI / 2;
      values.forEach((item, index) => {
        const portion = Math.max(0, item.value) / total, next = angle + portion * Math.PI * 2;
        const cx = 160, cy = 155, radius = 116, x1 = cx + radius * Math.cos(angle), y1 = cy + radius * Math.sin(angle), x2 = cx + radius * Math.cos(next), y2 = cy + radius * Math.sin(next);
        const path = document.createElementNS(svgNS, 'path'); path.setAttribute('d', portion >= .999 ? `M ${cx} ${cy - radius} A ${radius} ${radius} 0 1 1 ${cx} ${cy + radius} A ${radius} ${radius} 0 1 1 ${cx} ${cy - radius}` : `M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 ${portion > .5 ? 1 : 0} 1 ${x2} ${y2} Z`); path.setAttribute('fill', '#83dfae'); path.setAttribute('fill-opacity', String(Math.max(.25, 1 - index * .12))); path.setAttribute('stroke', '#111719'); path.setAttribute('stroke-width', '2'); svg.append(path);
        const y = 42 + index * 25; svgText(330, y, `${item.label.slice(0, 30)} · ${item.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`); angle = next;
      });
    } else if (chart.type === 'line') {
      const x0 = 55, y0 = 220, plotW = 660, plotH = 170; const points = values.map((item, index) => ({ x: x0 + (values.length <= 1 ? plotW / 2 : plotW * index / (values.length - 1)), y: y0 - plotH * item.value / max }));
      const axis = document.createElementNS(svgNS, 'path'); axis.setAttribute('d', `M ${x0} 30 V ${y0} H ${x0 + plotW}`); axis.setAttribute('stroke', '#42534a'); axis.setAttribute('fill', 'none'); svg.append(axis);
      const line = document.createElementNS(svgNS, 'polyline'); line.setAttribute('points', points.map(point => `${point.x},${point.y}`).join(' ')); line.setAttribute('stroke', '#83dfae'); line.setAttribute('stroke-width', '2.5'); line.setAttribute('fill', 'none'); svg.append(line);
      points.forEach((point, index) => { const dot = document.createElementNS(svgNS, 'circle'); dot.setAttribute('cx', String(point.x)); dot.setAttribute('cy', String(point.y)); dot.setAttribute('r', '3.5'); dot.setAttribute('fill', '#a7ebc5'); svg.append(dot); svgText(point.x - 20, 245, values[index].label.slice(0, 10), 9); });
    } else {
      values.forEach((item, index) => {
        const y = 9 + index * rowHeight, label = document.createElementNS(svgNS, 'text'); label.setAttribute('x', '0'); label.setAttribute('y', String(y + 14)); label.setAttribute('fill', '#91a89a'); label.setAttribute('font-size', '10'); label.textContent = item.label.slice(0, 28); svg.append(label);
        const bar = document.createElementNS(svgNS, 'rect'); bar.setAttribute('x', '190'); bar.setAttribute('y', String(y)); bar.setAttribute('height', '18'); bar.setAttribute('width', String(Math.max(2, 470 * Math.abs(item.value) / max))); bar.setAttribute('rx', '3'); bar.setAttribute('fill', '#83dfae'); svg.append(bar);
        svgText(Math.min(700, 197 + 470 * Math.abs(item.value) / max), y + 14, item.value.toLocaleString(undefined, { maximumFractionDigits: 2 }));
      });
    }
    const frame = el('div', 'answer-chart'); frame.append(el('div', 'chart-title', chart.type === 'line' ? 'Trend' : chart.type === 'pie' ? 'Result distribution' : 'Result comparison'), svg); return frame;
  }

  function renderResponse(data, question) {
    if (data.status === 'clarification') { renderStatus(data.answer, 'clarification', Object.assign(data.needs_clarification?.options || [], { question })); return; }
    if (data.status === 'unanswerable' || data.status === 'refused') { renderStatus(data.answer, data.status); return; }
    const card = el('article', 'answer-card');
    const top = el('div', 'answer-top'); const label = el('div', 'answer-label'); label.append(el('span', 'status-dot'), el('span', '', 'ANSWER')); top.append(label, el('div', 'answer-text', data.answer || 'The result is shown below.')); card.append(top);
    const columns = data.columns || [], rows = (data.rows || []).slice(0, 200);
    const indexes = columns.map((_, index) => index).filter(index => rows.some(row => typeof (Array.isArray(row) ? row[index] : row[columns[index]]) === 'number'));
    const arrays = rows.map(row => columns.map(column => Array.isArray(row) ? row[columns.indexOf(column)] : row[column]));
    const chart = makeChart(data.chart, columns, rows.map(row => Array.isArray(row) ? Object.fromEntries(columns.map((column, index) => [column, row[index]])) : row));
    if (chart) card.append(chart);
    if (rows.length) {
      let order = null, direction = 'asc', resultTable;
      const renderResultTable = sorted => {
        resultTable = safeTable(columns, sorted, { numeric: indexes, sortable: true, sort: order, direction, onSort: column => {
          direction = order === column && direction === 'asc' ? 'desc' : 'asc'; order = column;
          const values = [...arrays].sort((a, b) => { const av = a[columns.indexOf(column)], bv = b[columns.indexOf(column)]; const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av ?? '').localeCompare(String(bv ?? ''), undefined, { numeric: true }); return direction === 'asc' ? cmp : -cmp; });
          const previous = resultTable; const replacement = renderResultTable(values); previous.replaceWith(replacement);
        } });
        resultTable.classList.add('answer-table'); return resultTable;
      };
      renderResultTable(arrays);
      card.append(resultTable);
      card.append(el('div', 'table-caption', `${data.total_rows ?? rows.length} rows${rows.length < (data.rows || []).length ? ` · showing first ${rows.length}` : ''}${data.truncated ? ' · showing up to 1,000 results' : ''}`));
    }
    const footer = el('div', 'answer-footer');
    const meta = el('div', 'answer-meta');
    const actions = el('div', 'export-actions');
    if (data.result_id) { const csv = el('button', '', '↓ CSV'); csv.type = 'button'; csv.addEventListener('click', () => { window.location.href = `/api/results/${encodeURIComponent(data.result_id)}/csv`; }); actions.append(csv); }
    const pdf = el('button', '', 'PDF'); pdf.type = 'button'; pdf.addEventListener('click', () => { document.querySelectorAll('.answer-card').forEach(node => node.classList.remove('printing')); card.classList.add('printing'); window.print(); }); actions.append(pdf);
    footer.append(meta, actions); card.append(footer);
    const details = el('details', 'citation'); const summary = el('summary', '', 'Show calculation details'); details.append(summary);
    const content = el('div', 'citation-content');
    content.append(el('h4', '', 'Calculation')); const pre = el('pre', '', data.sql || 'No calculation details available.'); content.append(pre);
    content.append(el('h4', '', 'Worksheets and fields'));
    const tags = el('div', 'source-tags'); (data.sources || []).forEach(source => tags.append(el('span', 'source-tag', `${source.file} · ${source.sheet}${source.columns?.length ? ` · ${source.columns.join(', ')}` : ''}`)));
    if (!data.sources?.length) tags.append(el('span', '', 'No workbook source listed')); content.append(tags);
    if (data.join_keys?.length) { content.append(el('h4', '', 'Matching fields')); data.join_keys.forEach(join => content.append(el('div', '', join))); }
    if (data.assumptions?.length) { content.append(el('h4', '', 'Notes')); data.assumptions.forEach(value => content.append(el('div', '', value))); }
    details.append(content); card.append(details); $('#conversation').append(card); card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  async function loadPreview() {
    const table = state.table; if (!table) return;
    $('#explorer-table').value = table;
    const meta = tableByName(table); if (!meta) return;
    $('#column-cards').replaceChildren();
    for (const column of meta.columns) {
      const item = el('div', 'column-card'); const title = el('strong'); title.append(document.createTextNode(column.original_name || column.name), el('span', 'type-tag', column.type || 'text'));
      title.querySelector('.type-tag').textContent = displayType(column.type);
      const empty = Number(column.null_pct ?? 0);
      const note = column.uncalculated ? ' · Some saved results are missing' : '';
      item.append(title, el('small', '', `${empty}% empty${note}`));
      const values = column.sample_values || column.distinct_values || column.values || [];
      if (values.length) item.append(el('div', 'column-sample', values.slice(0, 5).map(value => String(value).slice(0, 60)).join(' · ')));
      $('#column-cards').append(item);
    }
    try {
      const params = new URLSearchParams({ page: String(state.page), page_size: String(state.pageSize), search: state.search });
      if (state.sort) { params.set('sort', state.sort); params.set('direction', state.direction); }
      const result = await request(`/api/tables/${encodeURIComponent(table)}/preview?${params}`);
      $('#preview-table').replaceChildren(safeTable(result.columns, result.rows, { sortable: true, sort: state.sort, direction: state.direction, onSort: column => {
        state.direction = state.sort === column && state.direction === 'asc' ? 'desc' : 'asc'; state.sort = column; loadPreview();
      } }));
      $('#preview-count').textContent = `${result.total_rows} rows`;
      $('#page-label').textContent = `Page ${result.page} · ${result.page_size} rows`;
      $('#prev-page').disabled = result.page <= 1; $('#next-page').disabled = result.page * result.page_size >= result.total_rows;
    } catch (error) { $('#preview-table').textContent = error.message; }
  }

  function drawMap() {
    const canvas = $('#schema-map'); if (!canvas || !state.schema) return;
    canvas.replaceChildren(); $('#relationship-details').replaceChildren();
    const tables = state.schema.tables || [], relationships = state.schema.relationships || [];
    $('#relationship-count').textContent = `${relationships.length} connections`;
    if (!tables.length) { canvas.append(el('div', 'empty-state', 'Add a workbook to see how its sheets connect.')); return; }
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('class', 'map-svg'); canvas.append(svg);
    const nodes = new Map(); const columns = 3, cellW = Math.max(210, canvas.clientWidth / columns), cellH = 135;
    tables.forEach((table, index) => {
      const defaultX = 22 + (index % columns) * cellW, defaultY = 22 + Math.floor(index / columns) * cellH;
      const position = state.mapPositions[table.name] || { x: defaultX, y: defaultY };
      const node = el('div', 'map-node'); node.dataset.name = table.name; node.setAttribute('draggable', 'true');
      node.append(el('strong', '', displayName(table)), el('small', '', `${table.row_count} rows · ${table.columns.length} fields`));
      const keys = relationships.filter(rel => rel.from_table === table.name || rel.to_table === table.name).map(rel => rel.from_table === table.name ? rel.from_column : rel.to_column);
      node.append(el('div', 'node-keys', keys.length ? `↔ ${[...new Set(keys)].join(' · ')}` : 'No linked sheets'));
      node.addEventListener('click', () => { state.table = table.name; hydrateSchema(state.schema); setView('explorer'); });
      node.style.left = `${position.x}px`; node.style.top = `${position.y}px`;
      node.addEventListener('dragstart', event => { event.dataTransfer.setData('text/plain', table.name); node.classList.add('dragging'); });
      node.addEventListener('dragend', () => { node.classList.remove('dragging'); state.mapPositions[table.name] = { x: parseFloat(node.style.left), y: parseFloat(node.style.top) }; drawMap(); });
      node.addEventListener('dragover', event => event.preventDefault());
      node.addEventListener('drop', event => { event.preventDefault(); const sourceName = event.dataTransfer.getData('text/plain'); const rect = canvas.getBoundingClientRect(); const source = nodes.get(sourceName); const point = { x: Math.max(0, event.clientX - rect.left - 75), y: Math.max(0, event.clientY - rect.top - 25) }; state.mapPositions[sourceName] = point; if (source) { source.style.left = `${point.x}px`; source.style.top = `${point.y}px`; } });
      canvas.append(node); nodes.set(table.name, node);
    });
    requestAnimationFrame(() => {
      const bounds = canvas.getBoundingClientRect();
      for (const rel of relationships) {
        const from = nodes.get(rel.from_table), to = nodes.get(rel.to_table); if (!from || !to) continue;
        const a = from.getBoundingClientRect(), b = to.getBoundingClientRect();
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        const x1 = a.left + a.width / 2 - bounds.left, y1 = a.top + a.height / 2 - bounds.top, x2 = b.left + b.width / 2 - bounds.left, y2 = b.top + b.height / 2 - bounds.top;
        line.setAttribute('d', `M ${x1} ${y1} C ${(x1 + x2) / 2} ${y1}, ${(x1 + x2) / 2} ${y2}, ${x2} ${y2}`); line.setAttribute('stroke', '#52795d'); line.setAttribute('stroke-width', '1.5'); line.setAttribute('fill', 'none'); svg.append(line);
      }
      // Draw edges below nodes while keeping every element inside the canvas.
      canvas.insertBefore(svg, canvas.firstChild);
    });
    for (const rel of relationships) {
      const from = tableByName(rel.from_table), to = tableByName(rel.to_table);
      const fromColumn = from?.columns.find(column => column.name === rel.from_column)?.original_name || rel.from_column;
      const toColumn = to?.columns.find(column => column.name === rel.to_column)?.original_name || rel.to_column;
      const row = el('div', 'relationship-row', `${displayName(from)}: ${fromColumn}  →  ${displayName(to)}: ${toColumn}`);
      row.append(el('span', '', `Matching entries: ${Math.round((rel.confidence || rel.overlap || 0) * 100)}%`)); $('#relationship-details').append(row);
    }
  }

  function xhrUpload(file, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest(), data = new FormData(); data.append('files', file, file.name);
      xhr.open('POST', '/api/upload'); xhr.withCredentials = true;
      xhr.upload.onprogress = event => { if (event.lengthComputable) onProgress(Math.round(event.loaded * 100 / event.total)); };
      xhr.onload = () => {
        let body; try { body = JSON.parse(xhr.responseText); } catch (_) { body = {}; }
        if (xhr.status >= 200 && xhr.status < 300) resolve(body); else reject(new Error(body.error?.message || `Upload failed (${xhr.status}).`));
      };
      xhr.onerror = () => reject(new Error('Upload failed. Check the local server connection.'));
      xhr.send(data);
    });
  }

  async function uploadFiles(fileList) {
    const files = [...fileList]; if (!files.length) return;
    const status = $('#upload-status'); status.replaceChildren();
    for (const file of files) {
      const line = el('div', 'upload-entry'); const label = el('span', '', `${file.name} · queued`); const progress = document.createElement('progress'); progress.max = 100; progress.value = 0; line.append(label, progress); status.append(line);
    }
    for (const [index, file] of files.entries()) {
      const line = status.children[index], label = line.firstChild, progress = line.querySelector('progress');
      label.textContent = `${file.name} · uploading`; $('#upload-button').disabled = true;
      try {
        const result = await xhrUpload(file, percent => { progress.value = percent; });
        const item = result.files?.[0];
        if (item?.status === 'loaded') { label.textContent = `${file.name} · loaded (${item.tables.length} table${item.tables.length === 1 ? '' : 's'})`; progress.value = 100; }
        else { label.textContent = `${file.name} · ${item?.error || 'could not be read'}`; label.classList.add('uncalculated'); }
        if (result.tables) hydrateSchema(result);
      } catch (error) { label.textContent = `${file.name} · ${error.message}`; label.classList.add('uncalculated'); }
    }
    $('#upload-button').disabled = false; toast('Upload processing finished.');
  }

  function openPrivacy() {
    $('#schema-only').checked = privacy.schemaOnly; $('#no-result-rows').checked = privacy.noRows;
    $('#privacy-dialog').showModal();
  }

  async function syncHealth() {
    try {
      const data = await request('/api/health'), badge = $('.cloud-badge');
      const status = data.ai_status || 'offline';
      badge.dataset.state = status;
      const label = status === 'ready' ? 'Ready' : status === 'missing_key' ? 'Setup needed' : 'Unavailable';
      badge.replaceChildren(el('span', `status-dot${status === 'ready' ? '' : ' uncalculated'}`), document.createTextNode(label));
      if (status !== 'ready' && status !== 'missing_key') showError(friendlyFailure({ code: status }));
      else if (status === 'missing_key') showError(friendlyFailure({ code: status }));
    } catch (_) { $('.cloud-badge').textContent = 'Unavailable'; }
  }

  function bind() {
    document.querySelectorAll('.nav-item').forEach(button => button.addEventListener('click', () => setView(button.dataset.view)));
    $('#question-form').addEventListener('submit', event => { event.preventDefault(); submitQuestion(); });
    $('#question').addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); submitQuestion(); } });
    $('#question').addEventListener('input', event => { event.target.style.height = 'auto'; event.target.style.height = `${Math.min(130, event.target.scrollHeight)}px`; });
    $('#explorer-table').addEventListener('change', event => { state.table = event.target.value; state.page = 1; hydrateSchema(state.schema); loadPreview(); });
    $('#preview-search').addEventListener('input', event => { state.search = event.target.value; state.page = 1; clearTimeout(bind.searchTimer); bind.searchTimer = setTimeout(loadPreview, 200); });
    $('#prev-page').addEventListener('click', () => { state.page = Math.max(1, state.page - 1); loadPreview(); });
    $('#next-page').addEventListener('click', () => { state.page++; loadPreview(); });
    $('#reload').addEventListener('click', async () => { $('#reload').disabled = true; try { hydrateSchema(await request('/api/reload', { method: 'POST' })); toast('Source folder reloaded.'); } catch (error) { toast(error.message); } finally { $('#reload').disabled = false; } });
    $('#upload-button').addEventListener('click', () => $('#file-input').click());
    $('#file-input').addEventListener('change', event => { uploadFiles(event.target.files); event.target.value = ''; });
    $('#privacy-button').addEventListener('click', openPrivacy); $('#close-privacy').addEventListener('click', () => $('#privacy-dialog').close());
    $('#schema-only').addEventListener('change', event => { privacy.schemaOnly = event.target.checked; localStorage.setItem('sheet-schema-only', String(privacy.schemaOnly)); });
    $('#no-result-rows').addEventListener('change', event => { privacy.noRows = event.target.checked; localStorage.setItem('sheet-no-result-rows', String(privacy.noRows)); });
    document.addEventListener('dragover', event => { if ([...event.dataTransfer.types].includes('Files')) { event.preventDefault(); $('#drop-overlay').hidden = false; } });
    document.addEventListener('dragleave', event => { if (event.clientX <= 0 || event.clientY <= 0 || event.clientX >= innerWidth || event.clientY >= innerHeight) $('#drop-overlay').hidden = true; });
    document.addEventListener('drop', event => { if ([...event.dataTransfer.types].includes('Files')) { event.preventDefault(); $('#drop-overlay').hidden = true; uploadFiles(event.dataTransfer.files); } });
    window.addEventListener('resize', () => { if (!$('#map-view').hidden) drawMap(); });
  }

  bind();
  refreshSchema();
  syncHealth();
  setInterval(syncHealth, 10000);
})();
