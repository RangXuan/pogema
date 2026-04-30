import json


class CanvasDrawer:

    def create_animation(self, obstacles, sparse_history, colors, grid_width, grid_height,
                         episode_length, obs_radius, on_target, config, svg_settings):
        data = self._build_data(obstacles, sparse_history, colors, grid_width, grid_height,
                                episode_length, obs_radius, on_target, config, svg_settings)
        data_json = json.dumps(data, separators=(',', ':'))
        return self._render_template(data_json)

    @staticmethod
    def _build_data(obstacles, sparse_history, colors, grid_width, grid_height,
                    episode_length, obs_radius, on_target, config, svg_settings):
        obstacle_list = []
        for r in range(len(obstacles)):
            for c in range(len(obstacles[0])):
                if obstacles[r][c]:
                    obstacle_list.append([r, c])

        agents = []
        for agent_idx, agent_states in enumerate(sparse_history):
            path = []
            for s in agent_states:
                path.append([s.x, s.y, s.tx, s.ty, s.step, 1 if s.active else 0])
            agents.append({
                'color': colors[agent_idx],
                'path': path,
            })

        return {
            'grid': {
                'w': grid_width,
                'h': grid_height,
                'cellSize': svg_settings.scale_size,
                'r': svg_settings.r,
                'rx': svg_settings.rx,
                'obstacleColor': svg_settings.obstacle_color,
                'strokeWidth': svg_settings.stroke_width,
                'obstacles': obstacle_list,
            },
            'agents': agents,
            'totalSteps': episode_length,
            'stepDuration': svg_settings.time_scale,
            'config': {
                'egoIdx': config.egocentric_idx,
                'obsRadius': obs_radius,
                'onTarget': on_target,
                'showGrid': config.show_grid_lines,
                'showAgents': config.show_agents,
                'staticFrame': config.static_frame_idx,
                'egoColor': svg_settings.ego_color,
                'egoOtherColor': svg_settings.ego_other_color,
                'shadedOpacity': svg_settings.shaded_opacity,
                'showControls': config.show_controls,
            },
            'colors': list(svg_settings.colors),
        }

    @staticmethod
    def _render_template(data_json):
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pogema Animation</title>
<style>
:root {{
  --pogema-red: #c1433c;
  --pogema-red-light: #d4635d;
  --pogema-red-dark: #a03530;
  --pogema-teal: #0ea08c;
  --pogema-teal-light: #72D5C8;
  --pogema-grid: #84A1AE;
  --pogema-bg: #fafafa;
  --pogema-surface: #ffffff;
  --pogema-text: #37474f;
  --pogema-text-light: #607d8b;
  --pogema-border: #e0e0e0;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #fff; display: flex;
  flex-direction: column; align-items: center;
  font-family: Roboto, -apple-system, BlinkMacSystemFont,
  "Segoe UI", sans-serif; color: var(--pogema-text);
  min-height: 100vh; padding: 24px 16px; }}
#canvas-container {{ position: relative; overflow: hidden; }}
#canvas-container canvas {{
  position: absolute; top: 0; left: 0; }}
#static-canvas {{ z-index: 1; }}
#dynamic-canvas {{ z-index: 2; }}
#controls {{ display: flex; align-items: center; gap: 10px;
  margin-top: 14px; padding: 10px 16px;
  background: var(--pogema-surface);
  border-radius: 8px; flex-wrap: wrap;
  justify-content: center;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08),
    0 0 0 1px var(--pogema-border); }}
button {{ background: none;
  color: var(--pogema-text); border: 2px solid var(--pogema-border);
  border-radius: 8px; padding: 6px 14px; cursor: pointer;
  font-size: 13px; font-weight: 700;
  transition: background 0.2s, color 0.2s, border-color 0.2s; }}
button:hover {{ border-color: #ffd700;
  background: rgba(255, 215, 0, 0.12); }}
button.active {{ background: var(--pogema-red);
  color: #fff; border-color: var(--pogema-red); }}
button.active:hover {{ background: var(--pogema-red-light);
  border-color: var(--pogema-red-light); }}
#play-btn {{ width: 72px; text-align: center; background: var(--pogema-red);
  color: #fff; border-color: var(--pogema-red); }}
#play-btn:hover {{ background: var(--pogema-red-light);
  border-color: var(--pogema-red-light); }}
#scrubber {{ width: 200px; accent-color: var(--pogema-red);
  height: 4px; }}
#step-label {{ font-size: 12px; min-width: 110px;
  text-align: center; font-variant-numeric: tabular-nums;
  color: var(--pogema-text-light); }}
.speed-group {{ display: flex; gap: 3px; }}
.speed-group button {{ padding: 4px 8px; font-size: 11px; }}
</style>
</head>
<body>

<div id="canvas-container">
  <canvas id="static-canvas"></canvas>
  <canvas id="dynamic-canvas"></canvas>
</div>

<div id="controls">
  <button id="play-btn">Pause</button>
  <input type="range" id="scrubber" min="0" max="100" step="0.1" value="0">
  <span id="step-label">Step 0 / 0</span>
  <div class="speed-group">
    <button data-speed="0.25">0.25x</button>
    <button data-speed="0.5">0.5x</button>
    <button data-speed="1" class="active">1x</button>
    <button data-speed="2">2x</button>
    <button data-speed="4">4x</button>
  </div>
  <button id="loop-btn" class="active">Loop</button>
</div>

<script>
(function() {{
"use strict";

const DATA = {data_json};

const grid = DATA.grid;
const agents = DATA.agents;
const totalSteps = DATA.totalSteps;
const stepDuration = DATA.stepDuration;
const config = DATA.config;
const TAU = Math.PI * 2;

// Logical grid dimensions (in grid-cell units)
const logicalW = grid.h + 1;  // +1 for offset
const logicalH = grid.w + 1;

// Setup canvases — use display-sized pixel buffer, NOT huge logical coords
const container = document.getElementById('canvas-container');
const staticCanvas = document.getElementById('static-canvas');
const dynCanvas = document.getElementById('dynamic-canvas');

const maxLogical = Math.max(logicalW, logicalH);
const displaySize = Math.min(window.innerWidth - 40, window.innerHeight - 120, 800);
const dpr = window.devicePixelRatio || 1;
// Cap DPR to avoid huge buffers on very-high-DPI displays
const effectiveDpr = Math.min(dpr, 2);
const dw = Math.ceil(logicalW / maxLogical * displaySize);
const dh = Math.ceil(logicalH / maxLogical * displaySize);
const pw = Math.ceil(dw * effectiveDpr);
const ph = Math.ceil(dh * effectiveDpr);

// Scale factor: pixels per grid cell
const S = pw / logicalW;
const radius = S * grid.r / grid.cellSize;
const strokeW = Math.max(S * grid.strokeWidth / grid.cellSize, 1);
const gridLineW = Math.max(S * grid.strokeWidth / grid.cellSize, 0.5);
const obsRx = S * grid.rx / grid.cellSize;

container.style.width = dw + 'px';
container.style.height = dh + 'px';

for (const c of [staticCanvas, dynCanvas]) {{
    c.width = pw;
    c.height = ph;
    c.style.width = dw + 'px';
    c.style.height = dh + 'px';
}}

const sCtx = staticCanvas.getContext('2d');
const dCtx = dynCanvas.getContext('2d');

// Coordinate helper: grid cell (row, col) -> pixel center
function cellX(col) {{ return (1 + col) * S; }}
function cellY(row) {{ return (1 + row) * S; }}

// Precompute color->agent index map for batched drawing
const colorBuckets = {{}};
for (let i = 0; i < agents.length; i++) {{
    const c = agents[i].color;
    if (!colorBuckets[c]) colorBuckets[c] = [];
    colorBuckets[c].push(i);
}}

// Precompute agent segment indices for O(1) position lookup
for (const a of agents) {{
    a._si = 0;
}}

// --- Draw static layer ---
function drawStatic() {{
    sCtx.clearRect(0, 0, pw, ph);

    // Grid lines
    if (config.showGrid) {{
        sCtx.strokeStyle = grid.obstacleColor;
        sCtx.lineWidth = gridLineW;
        for (let i = 0; i <= grid.h; i++) {{
            const x = (0.5 + i) * S;
            sCtx.beginPath();
            sCtx.moveTo(x, 0);
            sCtx.lineTo(x, ph);
            sCtx.stroke();
        }}
        for (let i = 0; i <= grid.w; i++) {{
            const y = (0.5 + i) * S;
            sCtx.beginPath();
            sCtx.moveTo(0, y);
            sCtx.lineTo(pw, y);
            sCtx.stroke();
        }}
    }}

    // Obstacles — batch into single path
    sCtx.fillStyle = grid.obstacleColor;
    if (obsRx > 0) {{
        for (const [r, c] of grid.obstacles) {{
            const x = cellX(c) - radius;
            const y = cellY(r) - radius;
            roundRect(sCtx, x, y, radius * 2, radius * 2, obsRx);
            sCtx.fill();
        }}
    }} else {{
        for (const [r, c] of grid.obstacles) {{
            sCtx.fillRect(cellX(c) - radius, cellY(r) - radius,
                          radius * 2, radius * 2);
        }}
    }}
}}

function roundRect(ctx, x, y, w, h, r) {{
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.arcTo(x + w, y, x + w, y + r, r);
    ctx.lineTo(x + w, y + h - r);
    ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
    ctx.lineTo(x + r, y + h);
    ctx.arcTo(x, y + h, x, y + h - r, r);
    ctx.lineTo(x, y + r);
    ctx.arcTo(x, y, x + r, y, r);
    ctx.closePath();
}}

// --- Position lookup ---
function getAgentPos(agent, stepInt, frac) {{
    const path = agent.path;
    // Forward scan from cached index
    while (agent._si < path.length - 1 && path[agent._si + 1][4] <= stepInt) {{
        agent._si++;
    }}
    const cur = path[agent._si];
    // Interpolate to next position if transitioning
    if (agent._si < path.length - 1) {{
        const nxt = path[agent._si + 1];
        const nxtStep = nxt[4];
        if (stepInt === nxtStep - 1 && frac > 0) {{
            return [
                cur[0] + (nxt[0] - cur[0]) * frac,
                cur[1] + (nxt[1] - cur[1]) * frac
            ];
        }}
    }}
    return [cur[0], cur[1]];
}}

function getTargetPos(agent, stepInt) {{
    const path = agent.path;
    // Use the same segment index logic
    let si = 0;
    while (si < path.length - 1 && path[si + 1][4] <= stepInt) {{
        si++;
    }}
    return [path[si][2], path[si][3]];
}}

function isActive(agent, stepInt) {{
    const path = agent.path;
    let si = 0;
    while (si < path.length - 1 && path[si + 1][4] <= stepInt) {{
        si++;
    }}
    return path[si][5] === 1;
}}

// Reset segment indices (needed for scrubbing backward)
function resetSegmentIndices() {{
    for (const a of agents) {{
        a._si = 0;
    }}
}}

// --- Draw dynamic layer ---
function drawFrame(step) {{
    const stepInt = Math.floor(step);
    const frac = step - stepInt;

    dCtx.clearRect(0, 0, pw, ph);

    if (!config.showAgents) return;

    const egoIdx = config.egoIdx;
    const isEgo = egoIdx !== null && egoIdx !== undefined;
    let egoRow, egoCol;
    if (isEgo) {{
        [egoRow, egoCol] = getAgentPos(agents[egoIdx], stepInt, frac);
    }}

    // Draw agents — batched by color (7 fill calls instead of 1000)
    if (isEgo) {{
        // Egocentric mode: batch into ego/other/shaded
        const egoBatch = [];   // ego agent
        const nearBatch = [];  // in-radius others
        const farBatch = [];   // out-of-radius others
        for (let i = 0; i < agents.length; i++) {{
            if (!isActive(agents[i], stepInt) && stepInt > 0) continue;
            const [row, col] = getAgentPos(agents[i], stepInt, frac);
            if (i === egoIdx) {{
                egoBatch.push(cellX(col), cellY(row));
            }} else if (inRadius(row, col, egoRow, egoCol, config.obsRadius)) {{
                nearBatch.push(cellX(col), cellY(row));
            }} else {{
                farBatch.push(cellX(col), cellY(row));
            }}
        }}
        // Draw shaded agents
        if (farBatch.length) {{
            dCtx.globalAlpha = config.shadedOpacity;
            dCtx.fillStyle = config.egoOtherColor;
            dCtx.beginPath();
            for (let j = 0; j < farBatch.length; j += 2) {{
                dCtx.moveTo(farBatch[j] + radius, farBatch[j+1]);
                dCtx.arc(farBatch[j], farBatch[j+1], radius, 0, TAU);
            }}
            dCtx.fill();
        }}
        // Draw near agents
        if (nearBatch.length) {{
            dCtx.globalAlpha = 1.0;
            dCtx.fillStyle = config.egoOtherColor;
            dCtx.beginPath();
            for (let j = 0; j < nearBatch.length; j += 2) {{
                dCtx.moveTo(nearBatch[j] + radius, nearBatch[j+1]);
                dCtx.arc(nearBatch[j], nearBatch[j+1], radius, 0, TAU);
            }}
            dCtx.fill();
        }}
        // Draw ego agent on top
        if (egoBatch.length) {{
            dCtx.globalAlpha = 1.0;
            dCtx.fillStyle = config.egoColor;
            dCtx.beginPath();
            dCtx.moveTo(egoBatch[0] + radius, egoBatch[1]);
            dCtx.arc(egoBatch[0], egoBatch[1], radius, 0, TAU);
            dCtx.fill();
        }}
    }} else {{
        // Normal mode: batch by color
        dCtx.globalAlpha = 1.0;
        for (const color in colorBuckets) {{
            dCtx.fillStyle = color;
            dCtx.beginPath();
            const idxs = colorBuckets[color];
            for (let j = 0; j < idxs.length; j++) {{
                const i = idxs[j];
                if (!isActive(agents[i], stepInt) && stepInt > 0) continue;
                const [row, col] = getAgentPos(agents[i], stepInt, frac);
                const cx = cellX(col);
                const cy = cellY(row);
                dCtx.moveTo(cx + radius, cy);
                dCtx.arc(cx, cy, radius, 0, TAU);
            }}
            dCtx.fill();
        }}
    }}

    // Draw targets — batched by color (on top of agents)
    dCtx.lineWidth = strokeW;
    if (isEgo) {{
        // Egocentric: only draw ego target
        const agent = agents[egoIdx];
        const [tr, tc] = getTargetPos(agent, stepInt);
        const alpha = inRadius(tr, tc, egoRow, egoCol, config.obsRadius)
            ? 1.0 : config.shadedOpacity;
        dCtx.globalAlpha = alpha;
        dCtx.strokeStyle = config.egoColor;
        dCtx.beginPath();
        dCtx.arc(cellX(tc), cellY(tr), radius, 0, TAU);
        dCtx.stroke();
    }} else {{
        // Batch targets by color
        const targetBatch = {{}};
        for (let i = 0; i < agents.length; i++) {{
            if (!isActive(agents[i], stepInt) && stepInt > 0) continue;
            const [tr, tc] = getTargetPos(agents[i], stepInt);
            const c = agents[i].color;
            if (!targetBatch[c]) targetBatch[c] = [];
            targetBatch[c].push(cellX(tc), cellY(tr));
        }}
        dCtx.globalAlpha = 1.0;
        for (const color in targetBatch) {{
            dCtx.strokeStyle = color;
            dCtx.beginPath();
            const pts = targetBatch[color];
            for (let j = 0; j < pts.length; j += 2) {{
                dCtx.moveTo(pts[j] + radius, pts[j+1]);
                dCtx.arc(pts[j], pts[j+1], radius, 0, TAU);
            }}
            dCtx.stroke();
        }}
    }}

    // Egocentric FOV overlay
    if (isEgo) {{
        drawEgoOverlay(egoRow, egoCol);
    }}

    dCtx.globalAlpha = 1.0;
}}

function inRadius(r1, c1, r2, c2, rad) {{
    return r2 - rad <= r1 && r1 <= r2 + rad && c2 - rad <= c1 && c1 <= c2 + rad;
}}

function drawEgoOverlay(egoRow, egoCol) {{
    const ecx = cellX(egoCol);
    const ecy = cellY(egoRow);
    const dr = (config.obsRadius + 1) * S - strokeW * 2;
    const fovX = ecx - dr + radius;
    const fovY = ecy - dr + radius;
    const fovW = 2 * dr - 2 * radius;
    const fovH = 2 * dr - 2 * radius;

    dCtx.globalAlpha = 1.0;
    dCtx.strokeStyle = config.egoColor;
    dCtx.lineWidth = strokeW;
    const dashLen = 25 * S / grid.cellSize;
    dCtx.setLineDash([dashLen, dashLen]);
    roundRect(dCtx, fovX, fovY, fovW, fovH, obsRx);
    dCtx.stroke();
    dCtx.setLineDash([]);
}}

// --- Playback state ---
let playing = true;
let looping = true;
let speed = 1.0;
let currentStep = 0;
let lastTimestamp = null;
const isStatic = config.staticFrame !== null && config.staticFrame !== undefined;

const playBtn = document.getElementById('play-btn');
const scrubber = document.getElementById('scrubber');
const stepLabel = document.getElementById('step-label');
const loopBtn = document.getElementById('loop-btn');

scrubber.max = totalSteps;

if (isStatic) {{
    currentStep = config.staticFrame;
    playing = false;
    playBtn.textContent = 'Play';
    document.getElementById('controls').style.display = 'none';
}}

if (!config.showControls) {{
    document.getElementById('controls').style.display = 'none';
}}

function updateLabel() {{
    stepLabel.textContent = 'Step ' + Math.floor(currentStep) + ' / ' + totalSteps;
    scrubber.value = currentStep;
}}

function animate(timestamp) {{
    if (lastTimestamp === null) lastTimestamp = timestamp;
    const dt = (timestamp - lastTimestamp) / 1000;
    lastTimestamp = timestamp;

    if (playing && !isStatic) {{
        currentStep += speed / stepDuration * dt;
        if (currentStep >= totalSteps) {{
            if (looping) {{
                currentStep = currentStep % totalSteps;
                resetSegmentIndices();
            }} else {{
                currentStep = totalSteps - 0.001;
                playing = false;
                playBtn.textContent = 'Play';
            }}
        }}
    }}

    drawFrame(currentStep);
    updateLabel();
    requestAnimationFrame(animate);
}}

// --- Controls ---
playBtn.addEventListener('click', function() {{
    playing = !playing;
    playBtn.textContent = playing ? 'Pause' : 'Play';
    if (playing && currentStep >= totalSteps - 0.01) {{
        currentStep = 0;
        resetSegmentIndices();
    }}
}});

scrubber.addEventListener('input', function() {{
    const newStep = parseFloat(scrubber.value);
    if (newStep < currentStep) resetSegmentIndices();
    currentStep = newStep;
}});

document.querySelectorAll('.speed-group button').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
        speed = parseFloat(btn.dataset.speed);
        document.querySelectorAll('.speed-group button').forEach(function(b) {{ b.classList.remove('active'); }});
        btn.classList.add('active');
    }});
}});

loopBtn.addEventListener('click', function() {{
    looping = !looping;
    loopBtn.classList.toggle('active');
}});

document.addEventListener('keydown', function(e) {{
    if (e.code === 'Space') {{
        e.preventDefault();
        playBtn.click();
    }}
}});

// --- Init ---
drawStatic();
requestAnimationFrame(animate);

}})();
</script>
</body>
</html>'''
