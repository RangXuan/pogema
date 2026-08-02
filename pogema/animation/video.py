import math
from bisect import bisect_right
from itertools import repeat
from pathlib import Path

import numpy as np

try:
    import imageio.v2 as imageio
    from PIL import Image, ImageColor, ImageDraw
except ImportError as exc:
    raise ImportError(
        "Video animation export requires optional dependencies. "
        "Install them with `pip install \"pogema[video]\"`."
    ) from exc


_ANTIALIAS_SCALE = 3


def save_video(name, data, episode_length, fps=30, max_size=800):
    path = Path(name)
    if path.suffix.lower() != '.mp4':
        raise ValueError("Only .mp4 video animation export is supported.")
    if fps <= 0:
        raise ValueError("fps must be positive.")
    if max_size <= 0:
        raise ValueError("max_size must be positive.")

    path.parent.mkdir(parents=True, exist_ok=True)
    renderer = _VideoRenderer(data, max_size)
    frame_steps = _frame_steps(
        episode_length,
        data['animation_config'].static_frame_idx,
        data['animation_style'].time_scale,
        fps,
    )

    with imageio.get_writer(
        str(path),
        fps=fps,
        codec='libx264',
        pixelformat='yuv420p',
        macro_block_size=2,
        quality=9,
    ) as writer:
        for step in frame_steps:
            writer.append_data(renderer.render(step))


def _frame_steps(episode_length, static_frame_idx, step_duration, fps):
    if static_frame_idx is not None:
        return repeat(float(static_frame_idx), max(1, int(round(fps))))

    duration = max(episode_length * step_duration, 1 / fps)
    frame_count = max(1, math.ceil(duration * fps))
    max_step = max(episode_length - 0.001, 0)
    return (min(frame_idx / fps / step_duration, max_step) for frame_idx in range(frame_count))


def _even_size(value):
    return max(2, int(value) // 2 * 2)


def _in_radius(row, col, ego_row, ego_col, radius):
    return ego_row - radius <= row <= ego_row + radius and ego_col - radius <= col <= ego_col + radius


def _with_alpha(color, opacity):
    return (*ImageColor.getrgb(color)[:3], round(255 * opacity))


def _draw_dashed_rounded_rectangle(draw, bounds, radius, dash_length, fill, width):
    x0, y0, x1, y1 = bounds
    radius = min(radius, (x1 - x0) / 2, (y1 - y0) / 2)
    horizontal = max(x1 - x0 - 2 * radius, 0)
    vertical = max(y1 - y0 - 2 * radius, 0)
    points = []

    def add_path(length, point_at):
        count = max(1, math.ceil(length))
        points.extend(point_at(idx / count) for idx in range(count))

    add_path(horizontal, lambda t: (x0 + radius + horizontal * t, y0))
    add_path(math.pi * radius / 2, lambda t: (
        x1 - radius + radius * math.cos(-math.pi / 2 + math.pi * t / 2),
        y0 + radius + radius * math.sin(-math.pi / 2 + math.pi * t / 2),
    ))
    add_path(vertical, lambda t: (x1, y0 + radius + vertical * t))
    add_path(math.pi * radius / 2, lambda t: (
        x1 - radius + radius * math.cos(math.pi * t / 2),
        y1 - radius + radius * math.sin(math.pi * t / 2),
    ))
    add_path(horizontal, lambda t: (x1 - radius - horizontal * t, y1))
    add_path(math.pi * radius / 2, lambda t: (
        x0 + radius + radius * math.cos(math.pi / 2 + math.pi * t / 2),
        y1 - radius + radius * math.sin(math.pi / 2 + math.pi * t / 2),
    ))
    add_path(vertical, lambda t: (x0, y1 - radius - vertical * t))
    add_path(math.pi * radius / 2, lambda t: (
        x0 + radius + radius * math.cos(math.pi + math.pi * t / 2),
        y0 + radius + radius * math.sin(math.pi + math.pi * t / 2),
    ))
    points.append(points[0])

    dash = max(round(dash_length), 1)
    for start in range(0, len(points) - 1, dash * 2):
        segment = points[start:min(start + dash + 1, len(points))]
        if len(segment) > 1:
            draw.line(segment, fill=fill, width=width, joint='curve')


class _VideoRenderer:
    def __init__(self, data, max_size):
        self.obstacles = data['obstacles']
        self.history = data['shifted_history']
        self.colors = data['colors']
        self.grid_width = data['grid_width']
        self.grid_height = data['grid_height']
        self.obs_radius = data['obs_radius']
        self.config = data['animation_config']
        self.style = data['animation_style']

        logical_width = self.grid_height + 1
        logical_height = self.grid_width + 1
        scale = max_size / max(logical_width, logical_height)
        self.output_size = (
            _even_size(logical_width * scale),
            _even_size(logical_height * scale),
        )
        self.pixel_size = tuple(size * _ANTIALIAS_SCALE for size in self.output_size)
        self.cell_size = min(
            self.pixel_size[0] / logical_width,
            self.pixel_size[1] / logical_height,
        )
        self.radius = self.cell_size * self.style.r / self.style.scale_size
        self.stroke_width = max(round(self.cell_size * self.style.stroke_width / self.style.scale_size), 1)
        self.corner_radius = self.cell_size * self.style.rx / self.style.scale_size
        self.obstacle_positions = [tuple(map(int, position)) for position in np.argwhere(self.obstacles)]
        self.shaded_other_color = _with_alpha(self.style.ego_other_color, self.style.shaded_opacity)
        self.shaded_ego_color = _with_alpha(self.style.ego_color, self.style.shaded_opacity)
        self.obstacle_seen_at = {}
        if self.config.egocentric_idx is not None:
            for state in self.history[self.config.egocentric_idx]:
                for row in range(max(0, state.x - self.obs_radius),
                                 min(self.grid_width, state.x + self.obs_radius + 1)):
                    for col in range(max(0, state.y - self.obs_radius),
                                     min(self.grid_height, state.y + self.obs_radius + 1)):
                        if self.obstacles[row][col]:
                            self.obstacle_seen_at.setdefault((row, col), state.step)

        self.grid_background = Image.new('RGB', self.pixel_size, self.config.background_color or '#ffffff')
        self._draw_grid(ImageDraw.Draw(self.grid_background, 'RGBA'))
        self.background = self.grid_background.copy()
        self._draw_obstacles(ImageDraw.Draw(self.background, 'RGBA'))

    def render(self, step):
        step_int = int(step)
        fraction = step - step_int
        snapshots = [self._snapshot(states, step_int, fraction) for states in self.history]
        ego_idx = self.config.egocentric_idx

        image = self.grid_background.copy() if ego_idx is not None else self.background.copy()
        draw = ImageDraw.Draw(image, 'RGBA')
        if ego_idx is not None:
            self._draw_obstacles(draw, step)
        if self.config.show_agents:
            self._draw_dynamic(draw, snapshots, step_int)
        if ego_idx is not None:
            _, ego_row, ego_col = snapshots[ego_idx]
            self._draw_egocentric_view(draw, ego_row, ego_col)
        image = image.resize(self.output_size, Image.Resampling.LANCZOS)
        return np.asarray(image.convert('RGB'))

    def _draw_grid(self, draw):
        if self.config.show_grid_lines:
            for col in range(self.grid_height + 1):
                x = (0.5 + col) * self.cell_size
                draw.line([(x, 0), (x, self.pixel_size[1])],
                          fill=self.style.obstacle_color, width=self.stroke_width)
            for row in range(self.grid_width + 1):
                y = (0.5 + row) * self.cell_size
                draw.line([(0, y), (self.pixel_size[0], y)],
                          fill=self.style.obstacle_color, width=self.stroke_width)

    def _draw_obstacles(self, draw, step=None):
        for row, col in self.obstacle_positions:
            color = self.style.obstacle_color
            if step is not None and self.style.egocentric_shaded:
                seen_at = self.obstacle_seen_at.get((row, col))
                progress = 0 if seen_at is None else min(max(step - seen_at + 1, 0), 1)
                opacity = self.style.shaded_opacity + (1 - self.style.shaded_opacity) * progress
                color = _with_alpha(color, opacity)
            bounds = self._circle_bounds(row, col)
            if self.corner_radius:
                draw.rounded_rectangle(
                    bounds,
                    radius=self.corner_radius,
                    fill=color,
                )
            else:
                draw.rectangle(bounds, fill=color)

    def _draw_dynamic(self, draw, snapshots, step_int):
        ego_idx = self.config.egocentric_idx

        if ego_idx is not None:
            _, ego_row, ego_col = snapshots[ego_idx]
            self._draw_egocentric_agents(draw, snapshots, step_int, ego_row, ego_col)
            self._draw_egocentric_target(draw, snapshots[ego_idx][0], ego_row, ego_col)
            return

        for agent_idx, (state, row, col) in enumerate(snapshots):
            if not state.active and step_int > 0:
                continue
            draw.ellipse(self._circle_bounds(row, col), fill=self.colors[agent_idx])

        for agent_idx, (state, _, _) in enumerate(snapshots):
            if not state.active and step_int > 0:
                continue
            draw.ellipse(
                self._circle_bounds(state.tx, state.ty),
                outline=self.colors[agent_idx],
                width=self.stroke_width,
            )

    def _draw_egocentric_agents(self, draw, snapshots, step_int, ego_row, ego_col):
        for agent_idx, (state, row, col) in enumerate(snapshots):
            if not state.active and step_int > 0:
                continue
            if agent_idx == self.config.egocentric_idx:
                color = self.style.ego_color
            elif _in_radius(row, col, ego_row, ego_col, self.obs_radius):
                color = self.style.ego_other_color
            else:
                color = self.shaded_other_color
            draw.ellipse(self._circle_bounds(row, col), fill=color)

    def _draw_egocentric_target(self, draw, state, ego_row, ego_col):
        color = self.style.ego_color
        if not _in_radius(state.tx, state.ty, ego_row, ego_col, self.obs_radius):
            color = self.shaded_ego_color
        draw.ellipse(
            self._circle_bounds(state.tx, state.ty),
            outline=color,
            width=self.stroke_width,
        )

    def _draw_egocentric_view(self, draw, ego_row, ego_col):
        center_x, center_y = self._cell_center(ego_row, ego_col)
        view_radius = (self.obs_radius + 1) * self.cell_size - self.stroke_width * 2
        bounds = (
            center_x - view_radius + self.radius,
            center_y - view_radius + self.radius,
            center_x + view_radius - self.radius,
            center_y + view_radius - self.radius,
        )
        dash_length = self.cell_size * self.style.stroke_dasharray / self.style.scale_size
        _draw_dashed_rounded_rectangle(
            draw,
            bounds,
            radius=self.corner_radius,
            dash_length=dash_length,
            fill=self.style.ego_color,
            width=self.stroke_width,
        )

    @staticmethod
    def _snapshot(states, step_int, fraction):
        state_idx = bisect_right(states, step_int, key=lambda state: state.step) - 1
        state = states[state_idx]
        row, col = state.x, state.y
        if state_idx < len(states) - 1:
            next_state = states[state_idx + 1]
            if step_int == next_state.step - 1 and fraction > 0:
                row += (next_state.x - row) * fraction
                col += (next_state.y - col) * fraction
        return state, row, col

    def _circle_bounds(self, row, col):
        center_x, center_y = self._cell_center(row, col)
        return (
            center_x - self.radius,
            center_y - self.radius,
            center_x + self.radius,
            center_y + self.radius,
        )

    def _cell_center(self, row, col):
        return (1 + col) * self.cell_size, (1 + row) * self.cell_size
