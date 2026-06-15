import os
import json
import sys
import csv
import time
import tempfile
from statistics import mean
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS

# Import simulator and env_maps
from sim import simulator
from sim.env_maps import topologyName_dict

# Check if running in production (Docker) or development mode
PRODUCTION = os.environ.get('FLASK_ENV') != 'development'
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_FOLDER = os.path.join(BASE_DIR, 'ui', 'dist') if PRODUCTION else None

app = Flask(__name__, static_folder=STATIC_FOLDER)
CORS(app)

RESULTS_DIR = os.path.join(BASE_DIR, 'results')
os.makedirs(RESULTS_DIR, exist_ok=True)


def _summarize_log_csv(path):
    created = 0
    delivered = 0
    expired = 0
    failed = 0
    recovered = 0
    delivery_latencies = []
    create_times = {}
    last_sim_time = 0.0

    with open(path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            sim_time = float(row.get('simTime', 0) or 0)
            item_id = int(row.get('itemId', -1) or -1)
            event = row.get('event', '')
            last_sim_time = max(last_sim_time, sim_time)

            if event == 'create':
                created += 1
                if item_id >= 0:
                    create_times[item_id] = sim_time
            elif event == 'deliver':
                delivered += 1
                if item_id in create_times:
                    delivery_latencies.append(sim_time - create_times[item_id])
            elif event == 'expire':
                expired += 1
            elif event == 'fail':
                failed += 1
            elif event in ('recover', 'recovery'):
                recovered += 1

    avg_latency = mean(delivery_latencies) if delivery_latencies else 0.0
    success_rate = (delivered / created) if created > 0 else 0.0
    return {
        'created': created,
        'delivered': delivered,
        'expired': expired,
        'failed': failed,
        'recovered': recovered,
        'avgDeliveryLatency': avg_latency,
        'successRate': success_rate,
        'lastSimTime': last_sim_time,
    }


def _write_aggregate_csv(run_rows, aggregate_filename):
    path = os.path.join(RESULTS_DIR, aggregate_filename)
    fieldnames = [
        'run',
        'created',
        'delivered',
        'expired',
        'failed',
        'recovered',
        'avgDeliveryLatency',
        'successRate',
        'lastSimTime',
        'wallTime',
        'eventCount',
    ]

    avg_row = {
        'run': 'AVG',
        'created': mean([r['created'] for r in run_rows]) if run_rows else 0.0,
        'delivered': mean([r['delivered'] for r in run_rows]) if run_rows else 0.0,
        'expired': mean([r['expired'] for r in run_rows]) if run_rows else 0.0,
        'failed': mean([r['failed'] for r in run_rows]) if run_rows else 0.0,
        'recovered': mean([r['recovered'] for r in run_rows]) if run_rows else 0.0,
        'avgDeliveryLatency': mean([r['avgDeliveryLatency'] for r in run_rows]) if run_rows else 0.0,
        'successRate': mean([r['successRate'] for r in run_rows]) if run_rows else 0.0,
        'lastSimTime': mean([r['lastSimTime'] for r in run_rows]) if run_rows else 0.0,
        'wallTime': mean([r['wallTime'] for r in run_rows]) if run_rows else 0.0,
        'eventCount': mean([r['eventCount'] for r in run_rows]) if run_rows else 0.0,
    }

    with open(path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in run_rows:
            writer.writerow(row)
        writer.writerow(avg_row)

    return path

@app.route('/api/topologies', methods=['GET'])
def get_topologies():
    return jsonify(list(topologyName_dict.keys()))

@app.route('/api/topology/<name>', methods=['GET'])
def get_topology(name):
    if name not in topologyName_dict and name in ['mesh', 'ring', 'tree', 'line', 'star', 'fully_connected', 'fullyconnected', 'bus']:
        if name == 'fullyconnected':
            name = 'fully_connected'
        n_rooms = request.args.get('n_rooms', type=int)
        if n_rooms is not None:
            candidate = f'{name}{n_rooms}'
            if candidate in topologyName_dict:
                name = candidate

    if name not in topologyName_dict:
        return jsonify({'error': 'Topology not found'}), 404
    
    topo = topologyName_dict[name]
    # Convert to a list of nodes and edges for easier frontend consumption
    nodes = [{'id': i, 'label': f'Room {i}'} for i in topo.keys()]
    edges = []
    seen_edges = set()
    
    for src, adj in topo.items():
        for dst in adj:
            # Undirected graph, store canonical edge to avoid duplicates
            e = tuple(sorted((src, dst)))
            if e not in seen_edges:
                edges.append({'source': src, 'target': dst})
                seen_edges.add(e)
                
    return jsonify({'nodes': nodes, 'edges': edges})

@app.route('/api/run', methods=['POST'])
def run_simulation():
    config_path = None
    try:
        config = dict(request.json or {})
        repetitions = max(1, int(config.get('N_REPETITIONS', 1) or 1))

        # Save config to a temp file (unique per request to avoid races)
        os.makedirs('configuration', exist_ok=True)
        timestamp = int(time.time() * 1000)
        run_rows = []
        last_logfile = None

        for run_idx in range(repetitions):
            run_config = dict(config)
            run_config['LOGFILE'] = os.path.join(
                RESULTS_DIR,
                f'run_{timestamp}_{run_idx + 1}.csv'
            )

            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.json',
                prefix='run_',
                dir='configuration',
                delete=False
            ) as f:
                config_path = f.name
                json.dump(run_config, f, indent=2)

            logfile, wall_time, event_count = simulator.run(config_path)
            last_logfile = logfile
            summary = _summarize_log_csv(logfile)
            run_rows.append({
                'run': run_idx + 1,
                **summary,
                'wallTime': wall_time,
                'eventCount': event_count,
            })

            if config_path and os.path.exists(config_path):
                try:
                    os.remove(config_path)
                except OSError:
                    pass
                config_path = None

        aggregate_filename = f'aggregate_{timestamp}.csv'
        aggregate_path = _write_aggregate_csv(run_rows, aggregate_filename)

        return jsonify({
            'success': True,
            'logfile': os.path.basename(last_logfile) if last_logfile else None,
            'aggregateLogfile': os.path.basename(aggregate_path),
            'wallTime': mean([r['wallTime'] for r in run_rows]) if run_rows else 0.0,
            'eventCount': mean([r['eventCount'] for r in run_rows]) if run_rows else 0.0,
            'repetitions': repetitions
        })
    except Exception as e:
        print(e)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if config_path and os.path.exists(config_path):
            try:
                os.remove(config_path)
            except OSError:
                pass


@app.route('/api/log/<filename>', methods=['GET'])
def get_log(filename):
    path = os.path.join(RESULTS_DIR, filename)
    if not os.path.exists(path):
        return jsonify({'error': 'Log file not found'}), 404

    try:
        # Try using pandas if available
        import importlib
        pandas_spec = importlib.util.find_spec('pandas')
        if pandas_spec is not None:
            import pandas as pd
            df = pd.read_csv(path)
            data = df.to_dict(orient='records')
            return jsonify(data)
    except Exception:
        pass
    # Fallback to csv module
    try:
        with open(path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            data = list(reader)
            return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<filename>', methods=['GET'])
def download_log(filename):
    path = os.path.join(RESULTS_DIR, filename)
    if not os.path.exists(path):
        return jsonify({'error': 'File not found'}), 404
    
    download_name = request.args.get('name', filename)
    return send_file(path, as_attachment=True, download_name=download_name)

@app.route('/api/rtlola/spec', methods=['GET'])
def get_rtlola_spec():
    """Get the current RTLola specification content."""
    default_spec = os.path.join(BASE_DIR, 'spec2.rtlola')
    
    if not os.path.exists(default_spec):
        return jsonify({'error': 'RTLola spec file not found'}), 404
    
    try:
        with open(default_spec, 'r') as f:
            content = f.read()
        return jsonify({'content': content, 'path': 'spec2.rtlola'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rtlola/spec', methods=['POST'])
def save_rtlola_spec():
    """Save the active RTLola specification without creating per-run copies."""
    try:
        data = request.json
        content = data.get('content', '')
        
        if not content:
            return jsonify({'error': 'No content provided'}), 400

        spec_path = os.path.join(BASE_DIR, 'spec2.rtlola')
        with open(spec_path, 'w') as f:
            f.write(content)
        
        return jsonify({'success': True, 'specFile': 'spec2.rtlola'})
    except Exception as e:
        print(f"Error saving RTLola spec: {e}")
        return jsonify({'error': str(e)}), 500

# Serve React frontend in production mode
if PRODUCTION and STATIC_FOLDER and os.path.exists(STATIC_FOLDER):
    @app.route('/')
    def serve_frontend():
        return send_from_directory(STATIC_FOLDER, 'index.html')
    
    @app.route('/<path:path>')
    def serve_static(path):
        # Serve static files if they exist, otherwise serve index.html for SPA routing
        file_path = os.path.join(STATIC_FOLDER, path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return send_from_directory(STATIC_FOLDER, path)
        else:
            return send_from_directory(STATIC_FOLDER, 'index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
