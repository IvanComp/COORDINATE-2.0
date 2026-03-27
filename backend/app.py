import csv
import importlib.util
import json
import os
from statistics import mean

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from sim.ant_simulator import run as run_ant_simulation
from sim.env_maps import topologyName_dict

PRODUCTION = os.environ.get("FLASK_ENV") != "development"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_FOLDER = os.path.join(BASE_DIR, "ui", "dist") if PRODUCTION else None
RESULTS_DIR = os.path.join(BASE_DIR, "results")

os.makedirs(RESULTS_DIR, exist_ok=True)

app = Flask(__name__, static_folder=STATIC_FOLDER)
CORS(app)


def _summarize_log_csv(path):
    summary = {
        "births": 0,
        "deaths": 0,
        "matings": 0,
        "meals": 0,
        "drinks": 0,
        "naps": 0,
        "moves": 0,
        "lastSimTime": 0.0,
    }

    with open(path, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            sim_time = float(row.get("simTime", 0) or 0)
            event = row.get("event", "")
            summary["lastSimTime"] = max(summary["lastSimTime"], sim_time)
            if event == "birth":
                summary["births"] += 1
            elif event == "death":
                summary["deaths"] += 1
            elif event == "mate":
                summary["matings"] += 1
            elif event == "eat":
                summary["meals"] += 1
            elif event == "drink":
                summary["drinks"] += 1
            elif event == "nap_start":
                summary["naps"] += 1
            elif event == "move":
                summary["moves"] += 1

    return summary


def _write_aggregate_csv(run_rows, aggregate_filename):
    path = os.path.join(RESULTS_DIR, aggregate_filename)
    fieldnames = [
        "run",
        "births",
        "deaths",
        "matings",
        "meals",
        "drinks",
        "naps",
        "moves",
        "lastSimTime",
        "wallTime",
        "eventCount",
    ]

    average_row = {
        "run": "AVG",
        "births": mean([row["births"] for row in run_rows]) if run_rows else 0.0,
        "deaths": mean([row["deaths"] for row in run_rows]) if run_rows else 0.0,
        "matings": mean([row["matings"] for row in run_rows]) if run_rows else 0.0,
        "meals": mean([row["meals"] for row in run_rows]) if run_rows else 0.0,
        "drinks": mean([row["drinks"] for row in run_rows]) if run_rows else 0.0,
        "naps": mean([row["naps"] for row in run_rows]) if run_rows else 0.0,
        "moves": mean([row["moves"] for row in run_rows]) if run_rows else 0.0,
        "lastSimTime": mean([row["lastSimTime"] for row in run_rows]) if run_rows else 0.0,
        "wallTime": mean([row["wallTime"] for row in run_rows]) if run_rows else 0.0,
        "eventCount": mean([row["eventCount"] for row in run_rows]) if run_rows else 0.0,
    }

    with open(path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in run_rows:
            writer.writerow(row)
        writer.writerow(average_row)

    return path


def _load_table(path):
    if importlib.util.find_spec("pandas") is not None:
        try:
            import pandas as pd

            return pd.read_csv(path).to_dict(orient="records")
        except Exception:
            pass

    with open(path, newline="") as csvfile:
        return list(csv.DictReader(csvfile))


@app.route("/api/topologies", methods=["GET"])
def get_topologies():
    return jsonify(list(topologyName_dict.keys()))


@app.route("/api/topology/<name>", methods=["GET"])
def get_topology(name):
    if name not in topologyName_dict and name in ["mesh", "ring", "tree"]:
        n_rooms = request.args.get("n_rooms", type=int)
        if n_rooms is not None:
            candidate = f"{name}{n_rooms}"
            if candidate in topologyName_dict:
                name = candidate

    if name not in topologyName_dict:
        return jsonify({"error": "Topology not found"}), 404

    topo = topologyName_dict[name]
    nodes = [{"id": idx, "label": f"Chamber {idx}"} for idx in topo.keys()]
    edges = []
    seen = set()
    for src, adjacents in topo.items():
        for dst in adjacents:
            edge = tuple(sorted((src, dst)))
            if edge in seen:
                continue
            seen.add(edge)
            edges.append({"source": src, "target": dst})
    return jsonify({"nodes": nodes, "edges": edges})


@app.route("/api/run", methods=["POST"])
def run_simulation():
    try:
        config = dict(request.json or {})
        repetitions = max(1, int(config.get("N_REPETITIONS", 1) or 1))
        run_rows = []
        last_result = None

        for run_idx in range(repetitions):
            result = run_ant_simulation(config, run_idx=run_idx)
            last_result = result
            summary = _summarize_log_csv(result["logfile"])
            run_rows.append(
                {
                    "run": run_idx + 1,
                    **summary,
                    "wallTime": result["wall_time"],
                    "eventCount": result["event_count"],
                }
            )

        aggregate_filename = f"aggregate_{last_result['run_stamp']}.csv"
        aggregate_path = _write_aggregate_csv(run_rows, aggregate_filename)

        return jsonify(
            {
                "success": True,
                "logfile": os.path.basename(last_result["logfile"]),
                "lineageFile": os.path.basename(last_result["lineage_file"]),
                "aggregateLogfile": os.path.basename(aggregate_path),
                "wallTime": mean([row["wallTime"] for row in run_rows]) if run_rows else 0.0,
                "eventCount": mean([row["eventCount"] for row in run_rows]) if run_rows else 0.0,
                "repetitions": repetitions,
            }
        )
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/log/<filename>", methods=["GET"])
def get_log(filename):
    path = os.path.join(RESULTS_DIR, filename)
    if not os.path.exists(path):
        return jsonify({"error": "Log file not found"}), 404
    try:
        return jsonify(_load_table(path))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/download/<filename>", methods=["GET"])
def download_log(filename):
    path = os.path.join(RESULTS_DIR, filename)
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404
    download_name = request.args.get("name", filename)
    return send_file(path, as_attachment=True, download_name=download_name)


@app.route("/api/ant/<lineage_file>/<int:ant_id>", methods=["GET"])
def get_ant_profile(lineage_file, ant_id):
    path = os.path.join(RESULTS_DIR, lineage_file)
    if not os.path.exists(path):
        return jsonify({"error": "Lineage file not found"}), 404

    try:
        with open(path, "r") as handle:
            data = json.load(handle)
        ants = data.get("ants", {})
        profile = ants.get(str(ant_id))
        if profile is None:
            return jsonify({"error": f"Ant {ant_id} not found"}), 404
        return jsonify({"profile": profile, "colony": data.get("colony", {})})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if PRODUCTION:
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path):
        candidate = os.path.join(app.static_folder, path) if path else ""
        if path and os.path.exists(candidate):
            return send_file(candidate)
        return send_file(os.path.join(app.static_folder, "index.html"))


if __name__ == "__main__":
    app.run(debug=not PRODUCTION, host="0.0.0.0", port=5002)
