from bisect import bisect_right

import numpy as np


def render_tikz(data):
    config = data['animation_config']
    style = data['animation_style']
    frame = config.static_frame_idx
    if frame is None:
        frame = max(states[-1].step for states in data['shifted_history'])
    if frame < 0:
        raise ValueError("static_frame_idx must be non-negative for TikZ rendering.")

    history = data['shifted_history']
    states = [_state_at(agent_states, frame) for agent_states in history]
    obstacles = data['obstacles']
    rows, cols = data['grid_width'], data['grid_height']
    radius = style.r / style.scale_size
    corner = style.rx / style.scale_size / 2
    line_width = style.stroke_width / style.scale_size / 2

    lines = [
        r'% Requires \usepackage{tikz}',
        r'\begin{tikzpicture}[x=0.5cm,y=-0.5cm]',
        rf'\definecolor{{pogemaObstacle}}{{HTML}}{{{_hex(style.obstacle_color)}}}',
        rf'\definecolor{{pogemaEgo}}{{HTML}}{{{_hex(style.ego_color)}}}',
        rf'\definecolor{{pogemaOther}}{{HTML}}{{{_hex(style.ego_other_color)}}}',
    ]
    for agent_idx, color in data['colors'].items():
        lines.append(rf'\definecolor{{pogemaAgent{agent_idx}}}{{HTML}}{{{_hex(color)}}}')
    if config.background_color is not None:
        lines.append(rf'\definecolor{{pogemaBackground}}{{HTML}}{{{_hex(config.background_color)}}}')

    lines.extend([
        rf'\path[use as bounding box] (0,0) rectangle ({cols + 1},{rows + 1});',
        rf'\clip (0,0) rectangle ({cols + 1},{rows + 1});',
    ])
    if config.background_color is not None:
        lines.append(rf'\fill[pogemaBackground] (0,0) rectangle ({cols + 1},{rows + 1});')
    if config.show_grid_lines:
        for col in range(cols + 1):
            lines.append(_draw_line(col + 0.5, 0, col + 0.5, rows + 1, line_width))
        for row in range(rows + 1):
            lines.append(_draw_line(0, row + 0.5, cols + 1, row + 0.5, line_width))

    ego_idx = config.egocentric_idx
    seen = _seen_obstacles(data, frame) if ego_idx is not None else None
    for row, col in np.argwhere(obstacles):
        opacity = style.shaded_opacity if seen is not None and (row, col) not in seen else 1
        lines.append(
            rf'\fill[pogemaObstacle,opacity={opacity:g},rounded corners={corner:g}cm] '
            rf'({col + 1 - radius:g},{row + 1 - radius:g}) rectangle '
            rf'({col + 1 + radius:g},{row + 1 + radius:g});'
        )

    if config.show_agents:
        ego_state = states[ego_idx] if ego_idx is not None else None
        for agent_idx, state in enumerate(states):
            color = f'pogemaAgent{agent_idx}'
            opacity = 1
            if ego_state is not None:
                color = 'pogemaEgo' if agent_idx == ego_idx else 'pogemaOther'
                if agent_idx != ego_idx and not _in_radius(state, ego_state, data['obs_radius']):
                    opacity = style.shaded_opacity
            lines.append(
                rf'\fill[{color},opacity={opacity:g}] ({state.y + 1},{state.x + 1}) '
                rf'circle[radius={radius / 2:g}cm];'
            )

        target_indices = [ego_idx] if ego_idx is not None else range(len(states))
        for agent_idx in target_indices:
            state = states[agent_idx]
            color = 'pogemaEgo' if ego_idx is not None else f'pogemaAgent{agent_idx}'
            opacity = 1
            if ego_idx is not None and not _target_in_radius(state, states[ego_idx], data['obs_radius']):
                opacity = style.shaded_opacity
            lines.append(
                rf'\draw[{color},opacity={opacity:g},line width={line_width:g}cm] '
                rf'({state.ty + 1},{state.tx + 1}) circle[radius={radius / 2:g}cm];'
            )

    if ego_idx is not None:
        ego = states[ego_idx]
        half_size = data['obs_radius'] + 1 - 2 * style.stroke_width / style.scale_size - radius
        dash = style.stroke_dasharray / style.scale_size / 2
        lines.append(
            rf'\draw[pogemaEgo,line width={line_width:g}cm,rounded corners={corner:g}cm,'
            rf'dash pattern=on {dash:g}cm off {dash:g}cm] '
            rf'({ego.y + 1 - half_size:g},{ego.x + 1 - half_size:g}) rectangle '
            rf'({ego.y + 1 + half_size:g},{ego.x + 1 + half_size:g});'
        )

    lines.append(r'\end{tikzpicture}')
    return '\n'.join(lines)


def _state_at(states, frame):
    return states[bisect_right(states, frame, key=lambda state: state.step) - 1]


def _seen_obstacles(data, frame):
    seen = set()
    radius = data['obs_radius']
    ego_history = data['shifted_history'][data['animation_config'].egocentric_idx]
    for state in ego_history:
        if state.step > frame:
            break
        for row in range(max(0, state.x - radius), min(data['grid_width'], state.x + radius + 1)):
            for col in range(max(0, state.y - radius), min(data['grid_height'], state.y + radius + 1)):
                if data['obstacles'][row][col]:
                    seen.add((row, col))
    return seen


def _in_radius(state, ego, radius):
    return abs(state.x - ego.x) <= radius and abs(state.y - ego.y) <= radius


def _target_in_radius(state, ego, radius):
    return abs(state.tx - ego.x) <= radius and abs(state.ty - ego.y) <= radius


def _draw_line(x1, y1, x2, y2, width):
    return rf'\draw[pogemaObstacle,line width={width:g}cm] ({x1:g},{y1:g}) -- ({x2:g},{y2:g});'


def _hex(color):
    value = color.removeprefix('#')
    if len(value) != 6 or any(char not in '0123456789abcdefABCDEF' for char in value):
        raise ValueError("TikZ colors must use #RRGGBB notation.")
    return value.upper()
