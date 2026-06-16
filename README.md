# COORDINATE 2.0

<p align="center">
<img src="img/readme/logo.png" width="340px" height="210px"/>
</p>

<p align="center">
  <img src="https://img.shields.io/github/license/IvanComp/COORDINATE-2.0">
  <img src="https://img.shields.io/badge/python-3.12+-yellow">
  <a href="https://hub.docker.com/r/ivancompd/coordinate-2.0"><img src="https://img.shields.io/docker/pulls/ivancompd/coordinate-2.0?logo=docker"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Flask-97CAE1?logo=flask&logoColor=white">
  <img src="https://img.shields.io/badge/React-20232A?logo=react&logoColor=61DAFB">
  <img src="https://img.shields.io/badge/Three.js-white?logo=threedotjs&logoColor=000000">
</p>

## Overview

**COORDINATE 2.0** is a highly customizable discrete event simulator for Fault-Tolerant Multi-Agent Systems.

### Key Capabilities

- **Multiple Coordination Architectures**: Compare decentralized, semi-decentralized, and centralized coordination strategies
- **Realistic 3D Visualization**: Interactive environment with smooth animations and camera controls
- **Flexible Topology Support**: Simulate different hospital floor plans (mesh, line, custom layouts including real-world GUH73)
- **Comprehensive Analytics**: Real-time statistics, event logging, and CSV export for detailed analysis
- **Research-Ready**: Command-line batch processing for reproducible experiments

<p align="center">
<img src="img/readme/simulationAd.webp"/>
</p>

---

## Quick Start

### Docker Deployment (Recommended)

The fastest way to get started. Pull and run the pre-built image from Docker Hub:

```bash
docker run -d -p 5002:5002 --name coordinate ivancompd/coordinate-2.0:latest
```

Then open **http://localhost:5002** in your browser.

**Docker Hub Repository:** [ivancompd/coordinate-2.0](https://hub.docker.com/r/ivancompd/coordinate-2.0)

### Local Development

For development or customization:

```bash
# 1. Setup backend
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt

# 2. Start backend (Terminal 1)
python -m backend.app

# 3. Start frontend (Terminal 2)
cd ui
npm install
npm run dev
```

Access the application at **http://localhost:5173**

> **Note:** Backend runs on port 5002, frontend on port 5173

---

## Paper Experiment Campaign

This is the workflow to use on the machines used for the paper experiments.
The repository tracks the compact CSV files needed for campaign resume, paper
tables, and notebook figures. Large raw traces and transient logs are not
tracked.

### First Setup

From the project root, the easiest setup is:

```bash
bash scripts/setup_experiments.sh
source .venv/bin/activate
```

The setup script creates `.venv`, installs the Python dependencies used by the
experiment runners and notebook, and tries to install a machine-compatible
`rtlola-cli` inside the virtual environment. If a compatible bundled binary is
already present in the repository, it is reused; otherwise the installer falls
back to Cargo.

If you prefer a different environment name such as `venv`, the setup script can
reuse or create it directly:

```bash
VENV_DIR=venv bash scripts/setup_experiments.sh
source venv/bin/activate
```

If you already recreated and activated the environment manually, run:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
bash scripts/install_rtlola_venv.sh
python scripts/check_rtlola.py
```

`python scripts/check_rtlola.py` must find a usable `rtlola-cli` before running
Dynamic Adaptation experiments.

### After Pulling Results

After a `git pull`, the compact result CSVs in `Paper Results/RQ*` are available
locally. The runners use those CSVs to resume completed experiments, so already
completed repetitions are skipped automatically.

To extend the current 5-repetition campaign to 10 repetitions, run:

```bash
source .venv/bin/activate
python "Paper Results/run_full_paper_campaign.py"
```

The default campaign is already configured for the paper:

- RQ1 runs `CE`, `SD`, `FD`, and `DA`.
- RQ2 runs `DA`.
- RQ3 runs `CE`, `SD`, `FD`, and `DA`.
- RQ4 runs `CE` and `DA` for the current hardware profile.

On Linux, RQ4 is labeled as `workstation`. On macOS, RQ4 is labeled as `mac`.
Therefore, to complete both RQ4 hardware profiles, run the same command once on
the workstation and once on the Mac.

To leave the campaign running after closing the terminal:

```bash
nohup python -u "Paper Results/run_full_paper_campaign.py" >/dev/null 2>&1 &
```

To check progress:

```bash
tail -f "Paper Results/campaign_status.csv"
```

To regenerate the paper figures from the committed CSVs:

```bash
jupyter notebook "Paper Results/paper_results_plots.ipynb"
```

The notebook writes PDF figures to `Paper Results/paper_figures/`.

---

## Features

### 🎮 Interactive 3D Visualization

- **Realistic Environment**: Rooms, corridors, and transparent glass walls rendered with React Three Fiber
- **Animated Robots**: 3D robot models with smooth movement, pickup/delivery animations, and status indicators
- **Camera Controls**: 
  - Left-click + drag to rotate
  - Right-click + drag to pan
  - Scroll to zoom
- **Playback Controls**: Variable speed (0.1x to 10x), pause, play, reset, and timeline scrubbing

### 🤖 Coordination Architectures

| Architecture | Description |
|--------------|-------------|
| **Decentralized** | Robots make independent decisions without communication |
| **Semi-Decentralized** | Robots share information with nearby peers |
| **Centralized-Proximity** | Central coordinator assigns tasks based on robot-item distance |
| **Centralized-Importance** | Central coordinator prioritizes high-importance items |
| **Centralized-ProxImp** | Proximity-first, then importance tiebreaker |
| **Centralized-ImpProx** | Importance-first, then proximity tiebreaker |
| **Dynamic-Adaptation** | 🆕 **Adaptive coordination that learns online when to switch strategies at runtime** |

#### Dynamic-Adaptation Architecture

The dynamic-adaptation architecture monitors recent runtime indicators and uses
a conservative contextual bandit to learn online which coordination mechanism is
expected to perform best in the current operating context. The default policy
chooses among `centralized-impprox` (CE), `semi-decentralized` (SD), and
`decentralized` (FD) using relative latency, pending tasks, failures,
coordination-message losses, throughput, idle agents, deadline misses, and the
currently active mechanism.

At each adaptation interval, the policy updates the value estimator associated
with the mechanism used in the previous window, then selects the mechanism with
the best estimated reward for the current context. Small exploration, switch
penalties, a minimum switch interval, a persistence condition, and critical
overrides keep switching conservative.

**Configuration Parameters:**
- `INITIAL_ARCHITECTURE`: Starting strategy (default: `semi-decentralized`)
- `ADAPTATION_CHECK_INTERVAL`: How often to check metrics in seconds (default: 300)
- `ADAPTATION_POLICY`: Adaptation policy (default: `contextual-bandit`)
- `BANDIT_EXPLORATION_EPSILON`: Initial online exploration probability (default: 0.08)
- `BANDIT_LEARNING_RATE`: Linear value-estimator update rate (default: 0.05)
- `BANDIT_IMPROVEMENT_MARGIN`: Minimum estimated reward gain before a non-exploratory switch (default: 0.02)
- `BANDIT_SWITCH_PENALTY`: Reward penalty applied to unnecessary switching (default: 0.03)

Architecture switches are logged in the CSV output with event type `switch_architecture_{new_arch}`.

### 📊 Analytics & Export

- **Real-time Statistics**: Track deliveries, failures, and system performance
- **Event Log**: Detailed timeline of all robot actions and item states
- **CSV Export**: Download complete simulation results for external analysis
- **Item Importance Levels**: Low (L), Medium (M), High (H) priority classification

### 🏥 Topology Support

- **Mesh Layouts**: `mesh25`, `mesh16`, `mesh9` - Grid-based hospital floors
- **Linear Layouts**: `line10`, `line5` - Corridor-style environments
- **Custom Layouts**: `GUH73` - Real-world Gent University Hospital floor plan
- **Configurable**: Define custom topologies in `env_maps.py`

---

## Installation & Deployment

### Prerequisites

- **Python** 3.12+
- **Node.js** 14+ (for local frontend development)
- **Docker** (optional, for containerized deployment)
- **Rust & RTLola** (required for Dynamic Adaptation)

### RTLola Setup

Dynamic Adaptation requires the `rtlola-cli` binary because runtime monitoring
is implemented through the RTLola specification in `spec2.rtlola`. The normal
setup path installs RTLola inside the project virtual environment:

```bash
bash scripts/setup_experiments.sh
source .venv/bin/activate
python scripts/check_rtlola.py
```

If the virtual environment already exists, install or repair only RTLola with:

```bash
bash scripts/install_rtlola_venv.sh
python scripts/check_rtlola.py
```

The installer uses Rust/Cargo when needed and installs `rtlola-cli` version
`0.1.2` into `.venv/bin/rtlola-cli`. The checker reports the candidate binaries
considered by the simulator and the selected executable. A working setup should
show:

```bash
rtlola-cli 0.1.2
```

The simulator uses `spec2.rtlola` by default through the `RTLOLA_SPEC_FILE`
configuration parameter. The UI RTLola editor also reads and writes this file
directly, so it does not create timestamped custom specification files.

Useful Dynamic Adaptation parameters are:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RTLOLA_SPEC_FILE` | `spec2.rtlola` | RTLola specification used by the monitor |
| `RTLOLA_BINARY_PATH` | auto-detected | Optional explicit path to `rtlola-cli` |
| `INITIAL_ARCHITECTURE` | `semi-decentralized` | Coordination mechanism active at startup |
| `ADAPTATION_CHECK_INTERVAL` | `300.0` | Simulated seconds between adaptation decisions |
| `ADAPTATION_POLICY` | `contextual-bandit` | Online adaptation policy |

For debugging, the monitor can be invoked manually:

```bash
.venv/bin/rtlola-cli monitor --stdin spec2.rtlola --online -v outputs
```

If Dynamic Adaptation fails with a missing RTLola error, rerun
`bash scripts/install_rtlola_venv.sh` and then `python scripts/check_rtlola.py`.

### Docker Options

**Option 1: Pull from Docker Hub**
```bash
docker pull ivancompd/coordinate-2.0:latest
docker run -p 5002:5002 ivancompd/coordinate-2.0:latest
```

**Option 2: Build Locally**
```bash
docker build -t coordinate-2.0 .
docker run -p 5002:5002 coordinate-2.0
```

**Option 3: Docker Compose (with persistence)**
```bash
docker-compose up -d
```

**Option 4: Custom Volume Mounts**
```bash
docker run -d -p 5002:5002 \
  -v $(pwd)/results:/app/results \
  -v $(pwd)/configuration:/app/configuration \
  --name coordinate \
  ivancompd/coordinate-2.0:latest
```

> **Tip:** Use volume mounts to persist simulation results and configurations between container restarts.

---

## Usage Guide

### Web Interface

1. **Open Configuration**: Click the gear icon in the top-right corner
2. **Select Architecture**: Choose from decentralized, semi-decentralized, or centralized variants
3. **Choose Topology**: Select a hospital floor plan (mesh25, GUH73, etc.)
4. **Configure Parameters**:
   - Number of robots
   - Simulation time
   - Item spawning rate and distribution
   - Failure probabilities
   - Robot timing parameters
5. **Run Simulation**: Click "Run Simulation" and wait for completion
6. **Interact with Visualization**:
   - Use playback controls to adjust speed
   - Navigate the 3D view with mouse controls
   - Monitor real-time statistics in the side panel
   - View detailed event log
7. **Export Results**: Click "Download CSV" to save simulation data

### Command-Line Simulation

#### Method 1: Paper Campaign

Run the current paper campaign through the maintained RQ runners:

```bash
python "Paper Results/run_full_paper_campaign.py"
```

This resumes from the compact CSV files in `Paper Results/RQ*` and skips runs
that are already completed.

#### Method 2: Custom Configuration File

Create a JSON configuration file (e.g., `my_config.json`):

```json
{
  "RESULTS_DIR": "results",
  "SIM_TIME": 3600,
  "ARCHITECTURE": "centralized-impprox",
  "TOPOLOGY_NAME": "mesh25",
  "N_ROOMS": 25,
  "SOURCE": 0,
  "TARGETS": -1,
  "ITEM_SPAWNING_TIME": 120,
  "ITEM_SPAWNING_DISTR": "exponential",
  "IMPORTANCE_PROBABILITIES": [0.5, 0.1, 0.4],
  "EXPIRATION_TIME": [-1, -1, -1],
  "N_ROBOTS": 20,
  "N_MALICIOUS": 0,
  "FAIL_PROB": 0.05,
  "COMM_FAIL_PROB": 0.003,
  "LOAD_TIME": 1.0,
  "MOVEMENT_TIME": 5.0,
  "DROP_TIME": 1.0,
  "COMP_TIME": 0.1,
  "COMM_TIME": 0.03,
  "RECOVERY_TIME": 1800.0
}
```

Run the simulation:
```bash
python -m sim.simulator my_config.json
```

Results are saved as CSV in the `results/` directory.

---

## Configuration Parameters

| Parameter | Description | Example Values |
|-----------|-------------|----------------|
| `SIM_TIME` | Simulation duration (seconds) | `3600` |
| `ARCHITECTURE` | Coordination strategy | `centralized-impprox` |
| `TOPOLOGY_NAME` | Hospital floor plan | `mesh25`, `GUH73` |
| `N_ROBOTS` | Number of robots | `20` |
| `ITEM_SPAWNING_TIME` | Average time between item spawns | `120` |
| `ITEM_SPAWNING_DISTR` | Spawning distribution | `exponential`, `uniform` |
| `IMPORTANCE_PROBABILITIES` | [Low, Medium, High] probabilities | `[0.5, 0.1, 0.4]` |
| `FAIL_PROB` | Robot failure probability | `0.05` |
| `COMM_FAIL_PROB` | Communication failure probability | `0.003` |
| `MOVEMENT_TIME` | Time to move between adjacent rooms | `5.0` |
| `RECOVERY_TIME` | Time to rescue a failed robot | `1800.0` |

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
