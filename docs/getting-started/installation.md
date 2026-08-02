# Installation

## From PyPI

```bash
pip install pogema
```

## From Source (development)

```bash
git clone https://github.com/Cognitive-AI-Systems/pogema.git
cd pogema
uv sync --extra test --extra dev
```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| gymnasium | >= 1.2.3 | Environment interface |
| numpy | >= 2.0 | Grid computations |
| pydantic | >= 2.12.5 | Configuration validation |

## Optional Dependencies

```bash
# For running tests
pip install pogema[test]

# For development (linting)
pip install pogema[dev]

# For official PettingZoo tools and API validation
pip install "pogema[pettingzoo]"

# For MP4 video export
pip install "pogema[video]"
```

## Verify Installation

```python
import pogema
print(pogema.__version__)
```
