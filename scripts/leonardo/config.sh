#!/usr/bin/env bash
# Shared settings for the 10-repetition LEONARDO campaign.
# Every value can be overridden from the environment, e.g.
#   SBATCH_ACCOUNT=inf26_enesma CPUS_PER_REP=56 bash scripts/leonardo/submit_10x.sh full

# CINECA project account to charge (check with: saldo -b).
SBATCH_ACCOUNT="${SBATCH_ACCOUNT:-inf26_enesma}"
# CPU partition. dcgp_usr_prod = DCGP nodes (112 cores, 512 GB). The simulator
# does not use GPUs, so boost_usr_prod would waste budget.
SBATCH_PARTITION="${SBATCH_PARTITION:-dcgp_usr_prod}"
SBATCH_QOS="${SBATCH_QOS:-normal}"

# Cores per repetition (one array task = one repetition = one sandbox).
# One repetition of RQ1+RQ2+RQ3 is about 20 core-hours, so 32 cores finish in
# roughly 1 h; the longest single run is about 10 min.
CPUS_PER_REP="${CPUS_PER_REP:-32}"
MEM_PER_REP="${MEM_PER_REP:-48G}"
TIME_PER_REP="${TIME_PER_REP:-04:00:00}"

# Repetitions and research questions.
# RQ4 measures wall time and memory, so it is kept out of the packed array
# by default (timings would be taken under contention). Use rq4_leonardo.slurm.
REPS="${REPS:-1-10}"
RQS="${RQS:-RQ1,RQ2,RQ3}"
MACHINE_LABEL="${MACHINE_LABEL:-leonardo}"

# Where sandboxes live. $SCRATCH is fast but purged after 40 days: the merge
# step copies the merged CSVs back into the repository.
CAMPAIGN_NAME="${CAMPAIGN_NAME:-coordinate_10x}"
CAMPAIGN_ROOT="${CAMPAIGN_ROOT:-${SCRATCH:-$HOME/scratch}/$CAMPAIGN_NAME}"

# Merged output inside the repository (does not touch the original results).
MERGED_DIR_NAME="${MERGED_DIR_NAME:-leonardo_10x}"

# Extra arguments forwarded to every RQ runner (e.g. "--sim-days 2 --limit 8").
EXTRA_ARGS="${EXTRA_ARGS:-}"
