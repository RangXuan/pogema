from dataclasses import dataclass


@dataclass
class AnimationConfig:
    """Internal render options shared by animation exporters."""

    show_agents: bool = True
    egocentric_idx: int | None = None
    static_frame_idx: int | None = None
    show_grid_lines: bool = True
    show_controls: bool = True
    colors: tuple | list | None = None
    speed: float | None = None
    background_color: str | None = None

    def __post_init__(self):
        if self.speed is not None and self.speed <= 0:
            raise ValueError("speed must be positive.")
        if self.colors is not None and not self.colors:
            raise ValueError("colors must not be empty.")
        if self.background_color is not None:
            color = self.background_color
            if (not isinstance(color, str) or len(color) != 7 or not color.startswith('#')
                    or any(char not in '0123456789abcdefABCDEF' for char in color[1:])):
                raise ValueError("background_color must use #RRGGBB notation.")


@dataclass
class AnimationStyle:
    r: int = 35
    stroke_width: int = 10
    scale_size: int = 100
    time_scale: float = 0.25
    draw_start: int = 100
    rx: int = 15

    obstacle_color: str = '#84A1AE'
    ego_color: str = '#c1433c'
    ego_other_color: str = '#6e81af'
    shaded_opacity: float = 0.2
    egocentric_shaded: bool = True
    stroke_dasharray: int = 25

    colors: tuple = (
        '#c1433c',
        '#2e6f9e',
        '#6e81af',
        '#00b9c8',
        '#72D5C8',
        '#0ea08c',
        '#8F7B66',
    )
