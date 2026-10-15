# Privacy scenario paper handoff

## Experiment design

The campaign compares Centralized (CE), Semi-Decentralized (SD), and Fully Decentralized (FD) coordination without Dynamic Adaptation. Each mechanism was evaluated with no privacy protection, encryption, data obfuscation, and their combination.

The experiment matrix contains 540 successful runs: 3 topologies, 3 coordination mechanisms, 4 privacy conditions, 3 workload levels, and 5 repetitions. The topologies are Mesh, Ring, and Star, each with 25 rooms. Every run uses 12 robots and lasts 3600 simulated seconds. Item inter-arrival times are 180, 90, and 30 seconds for low, medium, and high workload. Item priority probabilities are 40%, 35%, and 25%, with expiration times of 900, 600, and 420 seconds. Paired seeds are 26001-26005, 27001-27005, and 28001-28005 for the three workloads.

Encryption uses per-message X25519 key agreement, HKDF-SHA256, AES-256-GCM, Ed25519 signatures, signing-key rotation every 32 messages, and 8 KiB padded frames. Obfuscation uses MSTICPy with secret, per-message salted pseudonyms, 25 plausible destinations, and fixed-width 256-byte tokens.

The performance metrics are cumulative throughput, cumulative latency, success rate, and expiration rate. Privacy is measured through the adversary's success rate for encrypted communications and expected distance error for obfuscated destinations.

## Main results

Privacy adds about 66.5 ms per encrypted or combined coordination message and 55.6 ms per obfuscated message. For CE, mean latency increases from 23.47 s without privacy to 24.60 s with encryption or the combined condition. For SD, it increases from 27.47 s to 28.30 s. Obfuscation produces a smaller increase. Median throughput differences are zero, while mean throughput changes slightly because delayed messages alter some simulation trajectories.

CE has the lowest latency, a high success rate, and almost no expirations, but its reliance on the central coordinator exposes more communication and makes privacy overhead more visible.

SD maintains competitive throughput and reduces reliance on the central coordinator, but it has higher latency than CE, the lowest success rate, and more expirations. Peer communication still requires protection and introduces overhead.

FD sacrifices coordination speed and has the highest latency, but it keeps throughput and success rate competitive, produces fewer expirations than SD, and removes exposure from coordination messages.

FD is unchanged across privacy conditions because it exchanges no coordination messages. Its privacy metrics are not applicable rather than poor. CE is preferable when latency is the main objective, SD is competitive when throughput matters, and FD is attractive when avoiding communication exposure is the priority.

## Figures

`plots/privacy_results_all_plots.pdf` contains the three radar charts followed by cumulative throughput and cumulative latency. The same figures are also available as individual PDFs. The notebook regenerates both the individual files and the combined document.

## Package contents

- `results/`: campaign metadata, 540 run configurations, raw event logs, per-message privacy measurements, and aggregate CSV files.
- `plots/`: the combined five-page PDF and all individual figures.
- `regenerate_privacy_plots.ipynb`: reproducible figure generation.
- `implementation/`: privacy implementation, campaign runner, requirements, tests, and scenario documentation.

