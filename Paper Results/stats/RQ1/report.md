# Statistical analysis: RQ1

Input: `Paper Results/RQ1/runs.csv`  
Configurations: 125; mechanisms: CE, SD, FD, DA; repetitions per cell: min 10, max 10; ok runs: 5000.  
Configuration keys: topology, n_rooms, item_spawning_time, n_robots, n_malicious, fail_prob, msg_loss.  
Pairing check: every (configuration, repetition) uses one seed for all mechanisms.

## Headline (all configurations)

| Metric | Comparison | Δ (abs) | 95% CI | Rel. % | 95% CI | W/T/L (BH) | global p |
|---|---|---|---|---|---|---|---|
| Completion rate (%) | DA_vs_CE | -0.378 | [-0.888, +0.100] | -0.41 | [-0.97, +0.11] | 26/86/13 | 0.67 |
| Completion rate (%) | DA_vs_SD | -3.115 | [-4.502, -1.746] | -3.27 | [-4.77, -1.82] | 47/18/60 | 0.00034 |
| Completion rate (%) | DA_vs_FD | +10.747 | [+7.603, +14.054] | +13.22 | [+8.82, +18.50] | 41/15/69 | 0.03 |
| Completion rate (%) | DA_vs_best_static | -3.953 | [-5.231, -2.806] | -4.12 | [-5.50, -2.89] | 1/4/120 | 1.8e-21 |
| Completion rate (%) | DA_vs_oracle_static | -3.974 | [-5.192, -2.788] | -4.14 | [-5.47, -2.88] | 0/4/121 | 3e-22 |
| Completion rate (%) | DA_vs_mean_static | +2.418 | [+1.646, +3.246] | +2.70 | [+1.80, +3.72] | 23/100/2 | 3e-09 |
| Expiration rate (%) | DA_vs_CE | +0.375 | [-0.082, +0.886] | +4.97 | [-1.19, +11.80] | 28/86/11 | 0.64 |
| Expiration rate (%) | DA_vs_SD | +3.104 | [+1.767, +4.443] | +64.68 | [+38.31, +98.12] | 48/16/61 | 0.00031 |
| Expiration rate (%) | DA_vs_FD | -10.714 | [-14.154, -7.538] | -57.55 | [-62.89, -51.72] | 41/15/69 | 0.025 |
| Expiration rate (%) | DA_vs_best_static | +3.935 | [+2.783, +5.192] | +99.16 | [+70.55, +146.93] | 1/4/120 | 3.7e-21 |
| Expiration rate (%) | DA_vs_oracle_static | +3.955 | [+2.818, +5.239] | +100.19 | [+70.79, +148.18] | 0/5/120 | 6.3e-22 |
| Expiration rate (%) | DA_vs_mean_static | -2.412 | [-3.258, -1.636] | -23.38 | [-29.59, -17.67] | 19/105/1 | 2.6e-09 |
| Relative latency (min) | DA_vs_CE | +1.944 | [-0.086, +4.145] | +5.25 | [-0.22, +11.05] | 41/48/36 | 0.83 |
| Relative latency (min) | DA_vs_SD | +3.077 | [+0.428, +5.689] | +8.57 | [+1.13, +17.03] | 54/12/59 | 0.01 |
| Relative latency (min) | DA_vs_FD | +1.680 | [-1.482, +4.876] | +4.50 | [-3.77, +13.49] | 23/23/79 | 0.002 |
| Relative latency (min) | DA_vs_best_static | +13.983 | [+11.780, +16.500] | +55.91 | [+48.32, +65.10] | 0/1/124 | 3e-22 |
| Relative latency (min) | DA_vs_oracle_static | +14.018 | [+11.739, +16.451] | +56.14 | [+48.81, +65.28] | 0/1/124 | 3e-22 |
| Relative latency (min) | DA_vs_mean_static | +2.233 | [+1.090, +3.383] | +6.08 | [+3.19, +8.54] | 0/105/20 | 0.0029 |
| Latency (min) | DA_vs_CE | +1.946 | [-0.044, +4.099] | +5.20 | [-0.10, +10.90] | 41/48/36 | 0.83 |
| Latency (min) | DA_vs_SD | +3.080 | [+0.321, +5.750] | +8.48 | [+0.87, +16.97] | 54/12/59 | 0.0099 |
| Latency (min) | DA_vs_FD | +1.678 | [-1.495, +4.894] | +4.45 | [-3.78, +13.64] | 23/23/79 | 0.002 |
| Latency (min) | DA_vs_best_static | +13.985 | [+11.625, +16.423] | +55.05 | [+48.05, +63.91] | 0/1/124 | 3e-22 |
| Latency (min) | DA_vs_oracle_static | +14.021 | [+11.752, +16.547] | +55.27 | [+48.03, +64.05] | 0/1/124 | 3e-22 |
| Latency (min) | DA_vs_mean_static | +2.234 | [+1.127, +3.375] | +6.01 | [+3.31, +8.50] | 0/105/20 | 0.0029 |
| P95 latency (min) | DA_vs_CE | -1.303 | [-7.270, +4.937] | -0.71 | [-4.10, +2.70] | 41/54/30 | 0.18 |
| P95 latency (min) | DA_vs_SD | +9.077 | [-4.019, +21.973] | +5.27 | [-2.28, +13.22] | 50/13/62 | 0.046 |
| P95 latency (min) | DA_vs_FD | +11.710 | [-0.248, +23.853] | +6.90 | [-0.14, +15.27] | 22/39/64 | 0.0015 |
| P95 latency (min) | DA_vs_best_static | +55.819 | [+46.802, +64.753] | +44.44 | [+34.96, +56.10] | 0/1/124 | 3.8e-22 |
| P95 latency (min) | DA_vs_oracle_static | +56.864 | [+47.941, +66.147] | +45.66 | [+36.20, +58.22] | 0/1/124 | 3e-22 |
| P95 latency (min) | DA_vs_mean_static | +6.495 | [+2.305, +10.945] | +3.71 | [+1.40, +6.05] | 3/98/24 | 0.0049 |
| Throughput (tasks/h) | DA_vs_CE | -0.155 | [-0.359, +0.024] | -0.50 | [-1.15, +0.08] | 0/125/0 | 0.97 |
| Throughput (tasks/h) | DA_vs_SD | -1.181 | [-1.707, -0.708] | -3.68 | [-5.33, -2.21] | 14/70/41 | 1.2e-05 |
| Throughput (tasks/h) | DA_vs_FD | +3.936 | [+2.759, +5.209] | +14.59 | [+9.66, +20.64] | 41/74/10 | 0.0034 |
| Throughput (tasks/h) | DA_vs_best_static | -1.443 | [-1.936, -1.008] | -4.46 | [-6.00, -3.10] | 0/74/51 | 6.7e-20 |
| Throughput (tasks/h) | DA_vs_oracle_static | -1.485 | [-1.960, -1.049] | -4.58 | [-6.10, -3.24] | 0/48/77 | 3e-22 |
| Throughput (tasks/h) | DA_vs_mean_static | +0.867 | [+0.579, +1.183] | +2.88 | [+1.89, +4.03] | 18/107/0 | 1.7e-08 |
| Pending at end (tasks) | DA_vs_CE | +2.950 | [+0.480, +5.402] | +8.05 | [+1.32, +14.94] | 0/125/0 | 0.0027 |
| Pending at end (tasks) | DA_vs_SD | +8.854 | [+4.493, +13.456] | +28.77 | [+14.47, +45.24] | 8/110/7 | 0.001 |
| Pending at end (tasks) | DA_vs_FD | -25.825 | [-33.432, -18.813] | -39.46 | [-45.50, -33.55] | 41/76/8 | 0.0014 |
| Pending at end (tasks) | DA_vs_best_static | +14.293 | [+10.859, +17.975] | +56.42 | [+40.65, +79.55] | 0/125/0 | 2.7e-20 |
| Pending at end (tasks) | DA_vs_oracle_static | +15.808 | [+12.275, +19.666] | +66.38 | [+49.58, +92.54] | 0/113/12 | 1.4e-21 |
| Pending at end (tasks) | DA_vs_mean_static | -4.674 | [-6.960, -2.356] | -10.55 | [-15.86, -5.55] | 0/125/0 | 3.6e-05 |

Rates are in percentage points (Δ); Rel. % = mean Δ / mean baseline over configurations; latencies in minutes. Positive Δ means DA has the larger value; check the metric direction (completion: higher is better; expiration and latency: lower is better).

## Configurations where DA is significantly worse (BH, α=0.05)

| Metric | Comparison | Configuration | Δ | 95% CI |
|---|---|---|---|---|
| Latency (min) | DA_vs_CE | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=0, fail_prob=0.09, msg_loss=0.03 | +9.304 | [+1.919, +16.689] |
| Latency (min) | DA_vs_CE | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.01, msg_loss=0.03 | +0.134 | [+0.089, +0.178] |
| Latency (min) | DA_vs_CE | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=70, n_malicious=42, fail_prob=0.09, msg_loss=0.03 | +1.630 | [+0.245, +3.016] |
| Latency (min) | DA_vs_CE | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=80, n_malicious=48, fail_prob=0.09, msg_loss=0.03 | +1.663 | [+0.527, +2.799] |
| Latency (min) | DA_vs_CE | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=90, n_malicious=54, fail_prob=0.09, msg_loss=0.03 | +2.945 | [+2.287, +3.603] |
| Latency (min) | DA_vs_CE | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=100, n_malicious=60, fail_prob=0.09, msg_loss=0.03 | +3.553 | [+2.449, +4.657] |
| Latency (min) | DA_vs_CE | topology=mesh25, n_rooms=25, item_spawning_time=300, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.03 | +3.611 | [+1.911, +5.312] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=10, n_malicious=6, fail_prob=0.09, msg_loss=0.03 | +2.123 | [+0.565, +3.680] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=0, fail_prob=0.09, msg_loss=0.03 | +60.834 | [+47.907, +73.761] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=4, fail_prob=0.09, msg_loss=0.03 | +33.215 | [+26.854, +39.577] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=8, fail_prob=0.09, msg_loss=0.03 | +22.146 | [+17.873, +26.419] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.08, msg_loss=0.03 | +11.342 | [+6.443, +16.241] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.01 | +23.724 | [+19.080, +28.368] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.02 | +20.715 | [+15.236, +26.194] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.03 | +19.070 | [+14.709, +23.431] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.04 | +22.450 | [+16.810, +28.090] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.05 | +19.286 | [+16.113, +22.459] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.06 | +19.233 | [+13.178, +25.287] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.07 | +20.505 | [+17.064, +23.945] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.08 | +22.176 | [+15.975, +28.377] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.09 | +21.218 | [+18.660, +23.777] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.1 | +23.433 | [+16.851, +30.014] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.1, msg_loss=0.03 | +22.537 | [+18.760, +26.314] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=16, fail_prob=0.09, msg_loss=0.03 | +22.276 | [+17.451, +27.101] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=20, fail_prob=0.09, msg_loss=0.03 | +18.007 | [+15.217, +20.796] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=150, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.03 | +11.076 | [+6.943, +15.208] |
| Latency (min) | DA_vs_CE | topology=ring25, n_rooms=25, item_spawning_time=180, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.03 | +6.351 | [+1.775, +10.928] |
| Latency (min) | DA_vs_CE | topology=ring36, n_rooms=36, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.03 | +21.096 | [+18.296, +23.897] |
| Latency (min) | DA_vs_CE | topology=ring49, n_rooms=49, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.03 | +7.752 | [+4.526, +10.978] |
| Latency (min) | DA_vs_CE | topology=tree25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=0, fail_prob=0.09, msg_loss=0.03 | +10.899 | [+2.938, +18.859] |
| Latency (min) | DA_vs_CE | topology=tree25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.01, msg_loss=0.03 | +0.083 | [+0.050, +0.117] |
| Latency (min) | DA_vs_CE | topology=tree25, n_rooms=25, item_spawning_time=120, n_robots=50, n_malicious=30, fail_prob=0.09, msg_loss=0.03 | +0.754 | [-0.003, +1.512] |
| Latency (min) | DA_vs_CE | topology=tree25, n_rooms=25, item_spawning_time=120, n_robots=60, n_malicious=36, fail_prob=0.09, msg_loss=0.03 | +1.701 | [+1.090, +2.311] |
| Latency (min) | DA_vs_CE | topology=tree25, n_rooms=25, item_spawning_time=120, n_robots=70, n_malicious=42, fail_prob=0.09, msg_loss=0.03 | +1.131 | [+0.263, +1.998] |
| Latency (min) | DA_vs_CE | topology=tree25, n_rooms=25, item_spawning_time=120, n_robots=80, n_malicious=48, fail_prob=0.09, msg_loss=0.03 | +1.520 | [+0.817, +2.223] |
| Latency (min) | DA_vs_CE | topology=tree25, n_rooms=25, item_spawning_time=120, n_robots=90, n_malicious=54, fail_prob=0.09, msg_loss=0.03 | +1.056 | [+0.484, +1.628] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=90, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.03 | +51.412 | [+39.190, +63.634] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=10, n_malicious=6, fail_prob=0.09, msg_loss=0.03 | +48.190 | [+38.470, +57.911] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.01, msg_loss=0.03 | +0.164 | [+0.121, +0.208] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.02, msg_loss=0.03 | +0.513 | [+0.408, +0.617] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.03, msg_loss=0.03 | +0.898 | [+0.770, +1.026] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.04, msg_loss=0.03 | +1.730 | [+1.435, +2.026] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.05, msg_loss=0.03 | +2.020 | [+1.512, +2.527] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=20, n_malicious=12, fail_prob=0.06, msg_loss=0.03 | +2.612 | [+1.587, +3.638] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=30, n_malicious=18, fail_prob=0.09, msg_loss=0.03 | +4.866 | [+3.707, +6.026] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=40, n_malicious=24, fail_prob=0.09, msg_loss=0.03 | +5.197 | [+4.090, +6.303] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=50, n_malicious=30, fail_prob=0.09, msg_loss=0.03 | +3.998 | [+2.649, +5.347] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=60, n_malicious=36, fail_prob=0.09, msg_loss=0.03 | +3.046 | [+2.167, +3.924] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=70, n_malicious=42, fail_prob=0.09, msg_loss=0.03 | +3.215 | [+1.839, +4.590] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=80, n_malicious=48, fail_prob=0.09, msg_loss=0.03 | +2.907 | [+1.771, +4.044] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=90, n_malicious=54, fail_prob=0.09, msg_loss=0.03 | +4.030 | [+3.378, +4.681] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=120, n_robots=100, n_malicious=60, fail_prob=0.09, msg_loss=0.03 | +4.581 | [+3.473, +5.690] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=150, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.03 | +3.148 | [+0.620, +5.676] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=180, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.03 | +5.428 | [+2.960, +7.895] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=210, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.03 | +7.650 | [+5.176, +10.125] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=240, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.03 | +7.472 | [+5.346, +9.598] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=270, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.03 | +8.402 | [+6.668, +10.136] |
| Latency (min) | DA_vs_FD | topology=mesh25, n_rooms=25, item_spawning_time=300, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.03 | +11.412 | [+9.682, +13.142] |
| Latency (min) | DA_vs_FD | topology=ring25, n_rooms=25, item_spawning_time=90, n_robots=20, n_malicious=12, fail_prob=0.09, msg_loss=0.03 | +63.520 | [+51.213, +75.826] |
| Latency (min) | DA_vs_FD | topology=ring25, n_rooms=25, item_spawning_time=120, n_robots=10, n_malicious=6, fail_prob=0.09, msg_loss=0.03 | +16.970 | [+14.364, +19.576] |
| … | 2225 more rows in da_worse.csv | | | |

## Power note

With n = 10 paired repetitions, the smallest two-sided p-value an exact Wilcoxon signed-rank test can return is 0.0020. A Holm correction over 125 configurations requires p < 0.00040 for the first rejection, so per-configuration Holm-significant differences are impossible by construction. For this reason the per-configuration outcomes use Benjamini–Hochberg (false discovery rate), Holm-adjusted values are reported in paired.csv for completeness, and headline claims rest on the aggregate CI and on the global test over configurations.

## Methods paragraph (draft for the paper)

Each configuration was simulated 10 times per mechanism. Repetition $r$ of a configuration uses the same random seed for all mechanisms, so DA and each static mechanism form paired samples. For every mean we report a 95% confidence interval based on the Student t distribution. For each configuration we test the paired differences between DA and each baseline with a two-sided Wilcoxon signed-rank test, correct p-values across configurations with the Benjamini–Hochberg procedure (α = 0.05), and report the Vargha–Delaney A12 effect size. Besides the individual static mechanisms, DA is compared with the best static mechanism of each configuration (selected on the same data, which favours the baseline) and with a per-seed hindsight oracle that picks the best static mechanism for every repetition. Aggregate improvements are the mean of per-configuration differences, expressed in percentage points for rates, and as relative change (mean difference divided by the mean baseline value over configurations); their 95% confidence intervals come from a two-stage bootstrap (5000 resamples) that resamples configurations and then repetitions within each configuration. Differences between all mechanisms within a configuration are additionally tested with the Friedman test.
