# Privacy Scenario Replication Package

This folder is a standalone replication package for the privacy-aware case study used in the paper currently under revision for the **20th European Conference on Software Architecture (ECSA 2026)**.

The package reproduces the experimental comparison among the three coordination mechanisms discussed in the paper:

- `Centralized`
- `Semi-Decentralized`
- `Decentralized`

The study investigates how privacy-sensitive coordination affects architectural trade-offs in a cyber-physical indoor delivery system. In particular, it evaluates how increasing privacy-related communication overhead changes latency, success rate, expiration rate, and privacy-induced communication cost under different workload conditions.

## Standalone Replication Package

This folder is self-contained and can be moved outside the main repository to reproduce the privacy-aware experiments from the command line.

### Minimal contents

- `run_privacy_scenario.py`: main experiment runner
- `run_privacy_scenario.sh`: shell wrapper
- `sim/`: local copy of the simulator modules required by the runner
- `requirements.txt`: Python dependencies for the replication package
- `configs/`, `raw_logs/`, `results/`, `plots/`: generated artifacts
- `privacy_case_study_section.tex`: LaTeX section used to report the case study in the paper draft

### How to run

```bash
cd Privacy-Scenario
python3 -m pip install -r requirements.txt
python3 run_privacy_scenario.py
```

or equivalently:

```bash
cd Privacy-Scenario
./run_privacy_scenario.sh
```

### Useful options

```bash
python3 run_privacy_scenario.py --repetitions 3
python3 run_privacy_scenario.py --skip-plots
python3 run_privacy_scenario.py --skip-report
```

`--skip-plots` is useful if the goal is only to regenerate CSV results quickly.

## Case Study Summary

This package contains a privacy-aware experimental campaign in which:

- medium- and high-priority items are treated as privacy-sensitive;
- privacy-sensitive items incur additional communication overhead;
- the comparison shows how privacy can reduce the advantage of mechanisms that rely more heavily on coordination exchanges.

## Experimental Setup

- Topology: `mesh25`
- Number of agents: `12`
- Simulation window: `3600 s`
- Repetitions per condition: `5` by default
- Workload: low, medium, high
- Privacy levels: low, medium, high
- Compared architectures:
  - `Centralized`
  - `Semi-Decentralized`
  - `Decentralized`

Privacy overhead is modeled through:

- **Low**: `PRIVACY_COMM_TIME_BONUS = [0, 1, 2]`
- **Medium**: `PRIVACY_COMM_TIME_BONUS = [0, 5, 10]`
- **High**: `PRIVACY_COMM_TIME_BONUS = [0, 20, 40]`

## Produced Outputs

Running the package generates:

- `results/privacy_scenario_raw_runs.csv`: one row per run
- `results/privacy_scenario_summary.csv`: averaged summary by condition
- `results/privacy_scenario_winners.csv`: winning mechanism by condition and metric
- `plots/*.pdf` and `plots/*.png`: paper-ready plots

## Notes

This package is intended to support replication, inspection, and parameter tuning during the revision process. The script can be re-executed after adjusting repetitions or scenario parameters in order to regenerate the reported results.
