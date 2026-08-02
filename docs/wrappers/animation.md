# Animation

POGEMA can record episodes as SVG, HTML canvas, or MP4 animations and export static TikZ figures. The `AnimationWrapper` is included by default but inactive — it adds zero overhead until enabled.

In POGEMA 2.0, rendering options are passed directly as keyword arguments. The deprecated `AnimationMonitor` wrapper and public `AnimationConfig` API were removed.

## Basic Usage

```python exec="on" source="above"
import re  # markdown-exec: hide
from pogema import pogema_v0, GridConfig

env = pogema_v0(GridConfig(num_agents=4, size=8, seed=42))
env.enable_animation()
obs, info = env.reset()

while True:
    obs, reward, terminated, truncated, info = env.step(env.sample_actions())
    if all(terminated) or all(truncated):
        break

svg = env.render_animation()._repr_html_()  # markdown-exec: hide
svg = re.sub(r'\n\s+', '\n', svg[svg.index('<svg'):])  # markdown-exec: hide
print(f'<div class="pogema-anim">{svg}</div>')  # markdown-exec: hide
```

## Rendering Options

All rendering options are passed directly to the relevant render or save method:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `show_agents` | `bool` | `True` | Render agents on grid |
| `egocentric_idx` | `int \| None` | `None` | Follow specific agent |
| `static_frame_idx` | `int \| None` | `None` | Render single frame instead of animation |
| `show_grid_lines` | `bool` | `True` | Show grid lines |
| `show_controls` | `bool` | `True` | Show playback controls (HTML only) |
| `background_color` | `str \| None` | `None` | Solid `#RRGGBB` drawing background |

```python
from pogema import pogema_v0, GridConfig

env = pogema_v0(GridConfig(num_agents=4, size=8, seed=42))
env.enable_animation()
obs, info = env.reset()

while True:
    obs, reward, terminated, truncated, info = env.step(env.sample_actions())
    if all(terminated) or all(truncated):
        break

# SVG animation
env.save_animation('render.svg', show_grid_lines=False)

# HTML canvas animation (with playback controls)
env.save_html_animation('render.html', show_controls=True)

# Shared by SVG, HTML, MP4, and TikZ
env.save_animation('dark.svg', background_color='#111827')
```

## Video Export

Video export is available as an optional dependency:

```bash
pip install "pogema[video]"
```

```python
env.save_video_animation('render.mp4', fps=30, max_size=800)
```

## TikZ Export

TikZ export is dependency-free and produces a static source fragment of the latest frame for use with `\usepackage{tikz}`:

```python
env.save_tikz('render.tex')
```

## Egocentric View

Follow a specific agent's perspective:

```python exec="on" source="above"
import re  # markdown-exec: hide
from pogema import pogema_v0, GridConfig

env = pogema_v0(GridConfig(num_agents=4, size=8, seed=42, obs_radius=3))
env.enable_animation()
obs, info = env.reset()

while True:
    obs, reward, terminated, truncated, info = env.step(env.sample_actions())
    if all(terminated) or all(truncated):
        break

svg = env.render_animation(egocentric_idx=0)._repr_html_()  # markdown-exec: hide
svg = re.sub(r'\n\s+', '\n', svg[svg.index('<svg'):])  # markdown-exec: hide
print(f'<div class="pogema-anim">{svg}</div>')  # markdown-exec: hide
```

## Static Frame

Render a single timestep instead of an animation:

```python exec="on" source="above"
import re  # markdown-exec: hide
from pogema import pogema_v0, GridConfig

env = pogema_v0(GridConfig(num_agents=4, size=8, seed=42))
env.enable_animation()
obs, info = env.reset()

while True:
    obs, reward, terminated, truncated, info = env.step(env.sample_actions())
    if all(terminated) or all(truncated):
        break

svg = env.render_animation(static_frame_idx=0)._repr_html_()  # markdown-exec: hide
svg = re.sub(r'\n\s+', '\n', svg[svg.index('<svg'):])  # markdown-exec: hide
print(f'<div class="pogema-anim">{svg}</div>')  # markdown-exec: hide
```

## A* Baseline

See agents solving the task optimally:

```python exec="on" source="above"
import re  # markdown-exec: hide
from pogema import pogema_v0, GridConfig, BatchAStarAgent

env = pogema_v0(GridConfig(
    num_agents=4, size=8, seed=42,
    observation_type='POMAPF',
))
env.enable_animation()
agent = BatchAStarAgent()
obs, info = env.reset()

while True:
    obs, reward, terminated, truncated, info = env.step(agent.act(obs))
    if all(terminated) or all(truncated):
        break

agent.reset_states()
svg = env.render_animation()._repr_html_()  # markdown-exec: hide
svg = re.sub(r'\n\s+', '\n', svg[svg.index('<svg'):])  # markdown-exec: hide
print(f'<div class="pogema-anim">{svg}</div>')  # markdown-exec: hide
```

## Enable / Disable

```python
from pogema import pogema_v0, GridConfig

env = pogema_v0(GridConfig(num_agents=2, size=8, seed=42))
env.enable_animation()          # Start recording
assert env.animation_is_active  # Check status (bool)
env.disable_animation()         # Stop recording (zero overhead resumes)
```
