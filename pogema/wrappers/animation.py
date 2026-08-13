import os
from itertools import cycle

from pogema.wrappers.base import PogemaWrapper
from pogema.wrappers.persistence import AgentState, decompress_history


class SvgAnimation:
    def __init__(self, svg_str):
        self._svg_str = svg_str

    def _repr_html_(self):
        return self._svg_str

    def save(self, path='render.svg'):
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w") as f:
            f.write(self._svg_str)

    def __str__(self):
        return self._svg_str

    def __repr__(self):
        return f"SvgAnimation({len(self._svg_str)} chars)"


class HtmlAnimation:
    def __init__(self, html_str):
        self._html_str = html_str

    def _repr_html_(self):
        return self._html_str

    def save(self, path='render.html'):
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w") as f:
            f.write(self._html_str)

    def __str__(self):
        return self._html_str

    def __repr__(self):
        return f"HtmlAnimation({len(self._html_str)} chars)"


class AnimationWrapper(PogemaWrapper):
    def __init__(self, env):
        super().__init__(env)
        self._active = False
        self._step = None
        self._agent_states = None

    def step(self, action):
        result = self.env.step(action)
        if not self._active:
            return result
        self._step += 1
        for agent_idx in range(self.unwrapped.get_num_agents()):
            agent_state = self._get_agent_state(self.unwrapped.grid, agent_idx)
            if agent_state != self._agent_states[agent_idx][-1]:
                self._agent_states[agent_idx].append(agent_state)

        return result

    def reset(self, **kwargs):
        result = self.env.reset(**kwargs)
        if not self._active:
            return result

        self._step = 0

        self._agent_states = []
        for agent_idx in range(self.unwrapped.get_num_agents()):
            self._agent_states.append([self._get_agent_state(self.unwrapped.grid, agent_idx)])

        return result

    def _get_agent_state(self, grid, agent_idx):
        x, y = grid.positions_xy[agent_idx]
        tx, ty = grid.finishes_xy[agent_idx]
        active = grid.is_active[agent_idx]
        return AgentState(x, y, tx, ty, self._step, active)

    def enable_animation(self):
        self._active = True

    def disable_animation(self):
        self._active = False

    @property
    def animation_is_active(self):
        return self._active

    def _prepare_animation_data(self, **kwargs):
        if not self._active:
            raise RuntimeError(
                "Animation is not active. Call env.enable_animation() and then env.reset() before saving."
            )
        if self._agent_states is None:
            raise RuntimeError(
                "No history recorded. Call env.reset() after enable_animation() before saving."
            )

        from pogema.animation.config import AnimationConfig, AnimationStyle

        animation_config = AnimationConfig(**kwargs)

        radius = self.unwrapped.grid_config.obs_radius
        working_radius = {'none': radius, 'thin': radius - 1, 'full': 0}[animation_config.border]
        if working_radius > 0:
            obstacles = self.unwrapped.get_obstacles(ignore_borders=False)[working_radius:-working_radius,
                        working_radius:-working_radius]
        else:
            obstacles = self.unwrapped.get_obstacles(ignore_borders=False)

        offset = -working_radius
        raw_history = self._agent_states
        shifted_history = []
        for agent_states in raw_history:
            shifted = []
            for s in agent_states:
                if offset != 0:
                    shifted.append(AgentState(s.x + offset, s.y + offset, s.tx + offset, s.ty + offset, s.step, s.active))
                else:
                    shifted.append(s)
            shifted_history.append(shifted)

        animation_style = AnimationStyle()
        if animation_config.colors is not None:
            animation_style.colors = tuple(animation_config.colors)
        if animation_config.speed is not None:
            animation_style.time_scale = animation_config.speed
        colors_cycle = cycle(animation_style.colors)
        agents_colors = {index: next(colors_cycle) for index in range(self.unwrapped.grid_config.num_agents)}

        return {
            'obstacles': obstacles,
            'shifted_history': shifted_history,
            'colors': agents_colors,
            'grid_width': len(obstacles),
            'grid_height': len(obstacles[0]) if len(obstacles) > 0 else 0,
            'obs_radius': self.unwrapped.grid_config.obs_radius,
            'on_target': self.unwrapped.grid_config.on_target,
            'animation_config': animation_config,
            'animation_style': animation_style,
            'num_agents': self.unwrapped.grid_config.num_agents,
        }

    @staticmethod
    def _get_sparse_episode_length(sparse_history, animation_config, on_target):
        max_step = max(states[-1].step for states in sparse_history)
        episode_length = max_step + 1

        if animation_config.egocentric_idx is not None and on_target == 'finish':
            ego_history = sparse_history[animation_config.egocentric_idx]
            for state in reversed(ego_history):
                if state.active:
                    return state.step + 1

        return episode_length

    def _build_svg_string(self, **kwargs):
        from pogema.animation.svg import GridHolder, SvgDrawer

        data = self._prepare_animation_data(**kwargs)
        history = decompress_history(data['shifted_history'])

        for agent_idx in range(data['num_agents']):
            history[agent_idx].append(history[agent_idx][-1])

        episode_length = len(history[0])
        ac = data['animation_config']
        if ac.egocentric_idx is not None and data['on_target'] == 'finish':
            episode_length = history[ac.egocentric_idx][-1].step + 1
            for agent_idx in range(data['num_agents']):
                history[agent_idx] = history[agent_idx][:episode_length]

        grid_holder = GridHolder(
            width=data['grid_width'], height=data['grid_height'],
            obstacles=data['obstacles'],
            episode_length=episode_length,
            history=history,
            obs_radius=data['obs_radius'],
            on_target=data['on_target'],
            colors=data['colors'],
            config=ac,
            style=data['animation_style'],
        )

        animation = SvgDrawer().create_animation(grid_holder)
        return animation.render()

    def _build_html_string(self, **kwargs):
        from pogema.animation.html import HtmlCanvasDrawer

        data = self._prepare_animation_data(**kwargs)
        ac = data['animation_config']
        episode_length = self._get_sparse_episode_length(data['shifted_history'], ac, data['on_target'])

        return HtmlCanvasDrawer().create_animation(
            obstacles=data['obstacles'],
            sparse_history=data['shifted_history'],
            colors=data['colors'],
            grid_width=data['grid_width'],
            grid_height=data['grid_height'],
            episode_length=episode_length,
            obs_radius=data['obs_radius'],
            on_target=data['on_target'],
            config=ac,
            animation_style=data['animation_style'],
        )

    def save_video_animation(self, name='render.mp4', fps=30, max_size=800, **kwargs):
        from pogema.animation.video import save_video

        data = self._prepare_animation_data(**kwargs)
        ac = data['animation_config']
        episode_length = self._get_sparse_episode_length(data['shifted_history'], ac, data['on_target'])

        save_video(
            name=name,
            data=data,
            episode_length=episode_length,
            fps=fps,
            max_size=max_size,
        )

    def render_tikz(self, static_frame_idx=None, **kwargs):
        from pogema.animation.tikz import render_tikz

        data = self._prepare_animation_data(static_frame_idx=static_frame_idx, **kwargs)
        return render_tikz(data)

    def save_tikz(self, name='render.tex', static_frame_idx=None, **kwargs):
        tikz = self.render_tikz(static_frame_idx=static_frame_idx, **kwargs)
        parent = os.path.dirname(name)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(name, 'w') as file:
            file.write(tikz)

    def render_animation(self, **kwargs):
        return SvgAnimation(self._build_svg_string(**kwargs))

    def render_html_animation(self, **kwargs):
        return HtmlAnimation(self._build_html_string(**kwargs))

    def save_animation(self, name='render.svg', **kwargs):
        self.render_animation(**kwargs).save(name)

    def save_html_animation(self, name='render.html', **kwargs):
        self.render_html_animation(**kwargs).save(name)
