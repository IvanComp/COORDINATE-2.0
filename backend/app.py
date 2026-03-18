import os
import json
import sys
import csv
import time
import tempfile
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
RTLOLA_SPECS_DIR = os.path.join(BASE_DIR, 'rtlola_specs')
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(RTLOLA_SPECS_DIR, exist_ok=True)

@app.route('/api/topologies', methods=['GET'])
def get_topologies():
    return jsonify(list(topologyName_dict.keys()))

@app.route('/api/topology/<name>', methods=['GET'])
def get_topology(name):
    if name not in topologyName_dict and name in ['mesh', 'ring', 'tree']:
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
        config = request.json

        # Save config to a temp file (unique per request to avoid races)
        os.makedirs('configuration', exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            prefix='run_',
            dir='configuration',
            delete=False
        ) as f:
            config_path = f.name
            json.dump(config, f, indent=2)
            
        # Run simulator
        # simulator.run() returns (logfile, wall_time, event_count)
        logfile, wall_time, event_count = simulator.run(config_path)
        
        return jsonify({'success': True, 'logfile': os.path.basename(logfile), 'wallTime': wall_time, 'eventCount': event_count})
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
    default_spec = 'spec2.rtlola'
    
    if not os.path.exists(default_spec):
        return jsonify({'error': 'RTLola spec file not found'}), 404
    
    try:
        with open(default_spec, 'r') as f:
            content = f.read()
        return jsonify({'content': content, 'path': default_spec})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rtlola/spec', methods=['POST'])
def save_rtlola_spec():
    """Save a custom RTLola specification."""
    try:
        data = request.json
        content = data.get('content', '')
        
        if not content:
            return jsonify({'error': 'No content provided'}), 400
        
        # Create a timestamped filename for the custom spec
        timestamp = int(time.time() * 1000)
        spec_filename = f'spec_custom_{timestamp}.rtlola'
        spec_path = os.path.join(RTLOLA_SPECS_DIR, spec_filename)
        
        # Save the custom spec
        with open(spec_path, 'w') as f:
            f.write(content)
        
        return jsonify({'success': True, 'specFile': spec_path})
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
