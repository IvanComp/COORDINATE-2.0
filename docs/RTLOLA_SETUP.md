# RTLola Integration for Dynamic-Adaptation

## Installation

RTLola is now installed in this project. The installation includes:

- **Rust toolchain**: Installed via rustup
- **RTLola CLI**: Version 0.1.2
- **Location**: `~/.cargo/bin/rtlola-cli`

## Verification

To verify RTLola is installed:

```bash
~/.cargo/bin/rtlola-cli --version
```

Expected output: `rtlola-cli 0.1.2`

## Usage

### Running Simulations with Dynamic-Adaptation

1. **Via UI**: Select "dynamic-adaptation" from the Architecture dropdown
2. **Via CLI**: Use a configuration file with `"ARCHITECTURE": "dynamic-adaptation"`

Example configuration:
```json
{
  "ARCHITECTURE": "dynamic-adaptation",
  "INITIAL_ARCHITECTURE": "semi-decentralized",
  "ADAPTATION_CHECK_INTERVAL": 180.0,
  "LATENCY_THRESHOLD_LOW": 80.0,
  "LATENCY_THRESHOLD_HIGH": 200.0
}
```

### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `INITIAL_ARCHITECTURE` | `semi-decentralized` | Starting architecture |
| `RTLOLA_BINARY_PATH` | `~/.cargo/bin/rtlola-cli` | Path to RTLola CLI |
| `RTLOLA_SPEC_FILE` | `spec2.rtlola` | RTLola specification file |
| `ADAPTATION_CHECK_INTERVAL` | `300.0` | Check metrics every N seconds |
| `LATENCY_THRESHOLD_LOW` | `100.0` | Switch to centralized if latency < this |
| `LATENCY_THRESHOLD_HIGH` | `300.0` | Switch to decentralized if latency > this |

### Architecture Switching Logic

The system monitors delivery latency and switches architectures based on thresholds:

- **Latency > HIGH threshold** → Switch to `decentralized` (reduce coordination overhead)
- **Latency < LOW threshold** → Switch to `centralized-impprox` (optimize task allocation)
- **Latency in middle range** → Switch to `semi-decentralized` (balanced approach)

### Monitoring Architecture Switches

Architecture switches are logged in the CSV output:

```bash
grep "switch_architecture" results/*.csv
```

Example output:
```
180.5,-2,-1,-1,-1,-1,switch_architecture_centralized-impprox
360.2,-2,-1,-1,-1,-1,switch_architecture_decentralized
```

## RTLola Specification

The RTLola specification (`spec2.rtlola`) monitors:

- **Delivery latency**: Time from item creation to delivery
- **Mean latency (1h)**: Rolling average over 1-hour window
- **Failures**: Count of robot failures
- **Robot utilization**: Percentage of busy robots

## Troubleshooting

### RTLola Not Found

If you see:
```
[ERROR] RTLola is required for dynamic-adaptation architecture
```

Reinstall RTLola:
```bash
cargo install rtlola-cli
```

### No Architecture Switches

This is normal if latency remains stable. To trigger switches:
- Increase `FAIL_PROB` to create more variability
- Decrease `ADAPTATION_CHECK_INTERVAL` to check more frequently
- Adjust thresholds to match your simulation's latency range

### Viewing RTLola Output

For debugging, you can manually run RTLola:

```bash
~/.cargo/bin/rtlola-cli monitor --stdin spec2.rtlola --online -v outputs
```

Then pipe simulation events to it.

## Files

- `spec2.rtlola` - RTLola specification
- `rtlola_monitor.py` - Python wrapper for RTLola CLI
- `test_dynamic_config.json` - Example configuration
- `test_long_dynamic.json` - Longer simulation example
