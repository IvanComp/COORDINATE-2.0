# Privacy Scenario

This campaign compares the three static coordination mechanisms:

- `CE`: Centralized
- `SD`: Semi-Decentralized
- `FD`: Decentralized

Dynamic Adaptation is excluded. Each mechanism is evaluated under four conditions:

- no privacy technique
- encryption
- data obfuscation
- encryption and data obfuscation together

## Implementation

Encryption uses Fernet from `cryptography` on coordination messages. Data obfuscation uses `msticpy.data.data_obfus.hash_string` on the transmitted destination. The authorized receiver restores the original destination through a run-local mapping.

Every modeled coordination message executes the selected library operations. The simulator adds the measured encryption, decryption, obfuscation, and restoration time to the simulated communication delay. It also adds the transmission cost of payload expansion at the configured `PRIVACY_LINK_BYTES_PER_SECOND`.

The observers are separate:

- the communication observer reads the wire payload and provides `adversary_success_rate` for encryption conditions;
- the data observer reads the decrypted payload before authorized restoration and provides `expected_distance_error` for obfuscation conditions.

Expected Distance Error is measured in shortest-path hops between the estimated and actual destination. When a destination is protected, the observer uses the topology medoid as its prior estimate.

## Install

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Run

The default campaign executes 540 runs: 3 topologies, 3 mechanisms, 4 technique conditions, 3 workloads, and 5 repetitions.

```bash
./Privacy-Scenario/run_privacy_experiments.sh
```

A short validation campaign is available with:

```bash
./Privacy-Scenario/run_privacy_experiments.sh --smoke --fail-fast
```

Useful selections include:

```bash
./Privacy-Scenario/run_privacy_experiments.sh --repetitions 10
./Privacy-Scenario/run_privacy_experiments.sh --topologies ring,star
./Privacy-Scenario/run_privacy_experiments.sh --architectures CE,SD
./Privacy-Scenario/run_privacy_experiments.sh --techniques encryption,combined
./Privacy-Scenario/run_privacy_experiments.sh --workloads medium
```

Completed runs are skipped unless `--force` is supplied. Existing run identifiers without a topology prefix are retained as Mesh results, so extending an earlier Mesh campaign runs only Ring and Star. Seeds are paired across topologies, mechanisms, and technique conditions for each workload and repetition.

## Outputs

Full campaigns write to `Privacy-Scenario/results/`:

- `privacy_runs.csv`: one row per run
- `privacy_summary.csv`: averages by mechanism, technique condition, and workload
- `campaign_metadata.json`: campaign parameters and environment
- `configs/`: exact configuration for each run
- `raw_logs/`: simulator events and per-message privacy measurements

Smoke campaigns use `Privacy-Scenario/results/smoke/` and cannot cause full runs to be skipped.

`regenerate_privacy_plots.ipynb` preserves the existing table and grayscale chart style while comparing `None`, `Encryption`, `Obfuscation`, and `Combined`. It uses full campaign results when available and otherwise falls back to smoke results.

## Leonardo

Create the environment once, then submit from the repository root:

```bash
./scripts/submit_privacy_scenario.sh
```

Additional runner options can be passed after the script name.
