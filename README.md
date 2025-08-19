# Sailing Conditions

⛵ A lightweight Python package for quick sailing condition summaries across multiple cities.

## Features
- Pulls forecasts from NWS (grid + marine)
- Simple 1–10 sailing rating
- Outputs to Slack or email
- Extensible city list

## Install
```bash
pip install -e .
cat > sailing-conditions/README.md <<'EOF'
# Sailing Conditions

⛵ A lightweight Python package for quick sailing condition summaries across multiple cities.

## Features
- Pulls forecasts from NWS (grid + marine)
- Simple 1–10 sailing rating
- Outputs to Slack or email
- Extensible city list

## Install
```bash
pip install -e .
python -m sailing_conditions.cli --today --only chicago --slack
