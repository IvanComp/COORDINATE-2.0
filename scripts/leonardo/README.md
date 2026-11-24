# 10-repetition campaign on LEONARDO (CINECA)

Runs every RQ campaign 10 times as a SLURM job array (one array task = one
repetition), then merges the results and runs the statistical analysis.

## Why a sandbox per repetition
The RQ runners write to a single `Paper Results/RQx/runs.csv`. Ten parallel
jobs on the same file would overwrite each other, so `prepare_campaign.sh`
creates `$CAMPAIGN_ROOT/rep_01 ... rep_10`, each with its own copy of the
`Paper Results/*.py` runners and links to `sim/`, `spec2.rtlola`, `.venv`.
`run_one_rep.py` runs only repetition *k* in sandbox *k*.

Seeds are produced by the original runners (`base_seed + condition*1000 + rep`),
so repetition *k* on LEONARDO uses the same seed as repetition *k* of the
original campaign, and all mechanisms in a repetition share it (paired design).

## Steps (on a login node)
```bash
cd $HOME/COORDINATE-2.0            # your checkout on LEONARDO
git pull
bash scripts/leonardo/prepare_campaign.sh    # venv + scipy + rtlola check + sandboxes + dry run
bash scripts/leonardo/submit_10x.sh test     # 2 reps, 2 simulated days, 8 runs per RQ (~10 min)
# check slurm_logs/10x-*.out and Paper Results/leonardo_10x_test/
bash scripts/leonardo/submit_10x.sh full     # 10 reps, full campaign
squeue -u $USER
```
After the array, a dependent job (`merge_10x.slurm`) writes:

- `Paper Results/leonardo_10x/RQx/*.csv` merged results (+ `incomplete_configs.csv`)
- `Paper Results/leonardo_10x/stats/RQx/` statistics (see `Paper Results/stats_analysis.py`)

If some tasks time out, run `submit_10x.sh full` again: each runner skips the
runs already in its sandbox `runs.csv`.

## Settings (`config.sh`, all overridable from the environment)
| Variable | Default | Note |
|---|---|---|
| `SBATCH_ACCOUNT` | `inf26_enesma` | check budget with `saldo -b` |
| `SBATCH_PARTITION` | `dcgp_usr_prod` | CPU nodes; no GPU needed |
| `CPUS_PER_REP` | 32 | one simulation per core |
| `TIME_PER_REP` | 04:00:00 | one rep of RQ1+RQ2+RQ3 is about 20 core-hours |
| `RQS` | `RQ1,RQ2,RQ3` | RQ4 measures timing: use `scripts/rq4_leonardo.slurm` |
| `REPS` | `1-10` | e.g. `REPS=3,7` to redo two repetitions |
| `EXTRA_ARGS` | empty | forwarded to every runner, e.g. `--bandit-objective weighted` |

Example: `CPUS_PER_REP=56 TIME_PER_REP=02:00:00 bash scripts/leonardo/submit_10x.sh full`.

Budget estimate: 10 reps x about 20 core-hours = about 200 core-hours
(plus idle cores while the longest runs finish).

## Notes
- Compute nodes have no internet: `prepare_campaign.sh` must run on a login node.
- The `rtlola-cli` in the repo root is a macOS arm64 binary; on LEONARDO the
  Linux binary in `.venv/bin/rtlola-cli` is used (installed by
  `scripts/install_rtlola_venv.sh` through cargo).
- `$SCRATCH` is purged after 40 days; the merged CSVs are copied into the repo.
