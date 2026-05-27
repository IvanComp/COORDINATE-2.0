
import os, sys, time, json, random
import numpy as np

from .core import Cfg, Clock, Room, Space, Item, Robot
from .env_maps import topologyName_dict
from .adaptation_overhead import log_overhead_statistics

def _sort_events_csv_by_time(csv_path: str):
    if not os.path.exists(csv_path):
        return
    try:
        with open(csv_path, 'r') as f:
            lines = f.readlines()
        if not lines:
            return
        header, rows = lines[0], lines[1:]
        def keyfun(line):
            try:
                first = line.split(',', 1)[0]
                return float(first)
            except Exception:
                return 0.0
        rows.sort(key=keyfun)
        with open(csv_path, 'w') as f:
            f.write(header)
            f.writelines(rows)
    except Exception:
        pass


def _log_sim_time(cfg: Cfg, sim_secs: float):
    # write simTime.csv
    path = cfg.SIMTIME_LOGFILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path)
    with open(path, 'a') as f:
        if new:
            f.write('arch,space,Nrooms,Nbot,Nmal,failProb,commFailProb,arrival,loadItem,moveItem,dropItem,comp,comm,recovery,simTime\n')
        f.write(f"{cfg.ARCHITECTURE},{cfg.TOPOLOGY_NAME},{cfg.N_ROOMS},{cfg.N_ROBOTS},{cfg.N_MALICIOUS},{int(cfg.FAIL_PROB*100)},{int(cfg.COMM_FAIL_PROB*1000)},{int(cfg.ITEM_SPAWNING_TIME)},{int(cfg.LOAD_TIME)},{int(cfg.MOVEMENT_TIME)},{int(cfg.DROP_TIME)},{int(cfg.COMP_TIME)},{int(cfg.COMM_TIME)},{int(cfg.RECOVERY_TIME)},{sim_secs}\n")

def _build_cfg(config_path: str) -> Cfg:
    with open(config_path, 'r') as f:
        d = json.load(f)
    # Fill derived / defaults
    d.setdefault('SIMTIME_LOGFILE', os.path.join(d.get('RESULTS_DIR', 'results'), 'simTime.csv'))
    d.setdefault('LOGFILE', '')
    d.setdefault('ITEM_SPAWNING_TRACE', '_')
    d.setdefault('LOAD_TRACE', '_')
    d.setdefault('MOVEMENT_TRACE', '_')
    d.setdefault('DROP_TRACE', '_')
    d.setdefault('COMP_TRACE', '_')
    d.setdefault('COMM_TRACE', '_')
    d.setdefault('RECOVERY_TRACE', '_')
    d.setdefault('TARGETS', -1)
    d.setdefault('MALICIOUS_FAKE_FAILURES', True)
    d.setdefault('FIND_ROUTE_STRATEGY', 'breadth')
    d.setdefault('INITIAL_ARCHITECTURE', 'semi-decentralized')
    d.setdefault('ADAPTATION_POLICY', 'hybrid-score')
    d.setdefault('ADAPTATION_CHECK_INTERVAL', 300.0)
    d.setdefault('ADAPTATION_WINDOW', 3600.0)
    d.setdefault('ADAPTATION_MIN_SWITCH_INTERVAL', 30.0)
    d.setdefault('ADAPTATION_PERSISTENCE_CHECKS', 2)
    d.setdefault('ADAPTATION_CRITICAL_BYPASS_PERSISTENCE', True)
    d.setdefault('LATENCY_THRESHOLD_LOW', 10.0)
    d.setdefault('LATENCY_THRESHOLD_HIGH', 40.0)
    d.setdefault('RTLOLA_METRIC_TIMEOUT', 0.05)
    d.setdefault('ADAPTIVE_THRESHOLDS', True)
    d.setdefault('ADAPTIVE_THRESHOLD_WINDOW', 12)
    d.setdefault('ADAPTIVE_THRESHOLD_WARMUP', 4)
    d.setdefault('ADAPTIVE_THRESHOLD_MIN_SPREAD', 5.0)
    d.setdefault('ADAPTIVE_THRESHOLD_LOW_MULTIPLIER', 0.5)
    d.setdefault('ADAPTIVE_THRESHOLD_HIGH_MULTIPLIER', 2.0)
    d.setdefault('ADAPTIVE_THRESHOLD_HYSTERESIS', 0.10)
    d.setdefault('ADAPTIVE_THRESHOLD_MIN_MARGIN', 1.0)
    d.setdefault('ADAPTATION_SCORE_LOW', 0.35)
    d.setdefault('ADAPTATION_SCORE_HIGH', 0.65)
    d.setdefault('ADAPTATION_SCORE_HYSTERESIS', 0.05)
    d.setdefault('ADAPTATION_WEIGHT_LATENCY', 0.65)
    d.setdefault('ADAPTATION_WEIGHT_PENDING', 0.20)
    d.setdefault('ADAPTATION_WEIGHT_FAILURE', 0.10)
    d.setdefault('ADAPTATION_WEIGHT_MESSAGE_LOSS', 0.05)
    d.setdefault('ADAPTATION_PENDING_REF', 1.0)
    d.setdefault('ADAPTATION_FAILURE_REF', 0.50)
    d.setdefault('ADAPTATION_PENDING_CRITICAL_RATIO', 2.0)
    d.setdefault('ADAPTATION_FAILURE_CRITICAL_RATE', 1.25)
    d.setdefault('ADAPTATION_MESSAGE_CRITICAL_LOSS', 0.60)
    d.setdefault('ADAPTATION_FD_MESSAGE_LOSS_THRESHOLD', 0.35)
    d.setdefault('ADAPTATION_FD_COMM_FAIL_PROB_THRESHOLD', 0.35)
    d.setdefault('ADAPTATION_FD_MALICIOUS_RATIO_THRESHOLD', 0.50)
    d.setdefault('ADAPTATION_FD_FAILURE_RATE_THRESHOLD', 999.0)
    d.setdefault('ADAPTATION_RECOVERY_FAIL_PROB_THRESHOLD', 0.08)
    d.setdefault('ADAPTATION_RECOVERY_COMM_FAIL_THRESHOLD', 0.05)
    d.setdefault('ADAPTATION_RECOVERY_MALICIOUS_RATIO_THRESHOLD', 0.20)
    # Keep simulator resilient if frontend payload omits optional fields.
    d.setdefault('IMPORTANCE_PROBABILITIES', [0.5, 0.1, 0.4])
    d.setdefault('EXPIRATION_TIME', [-1, -1, -1])
    d.setdefault('EXPIRATION_DISTR', ['exponential', 'exponential', 'exponential'])
    d.setdefault('PRIVACY_COMM_TIME_BONUS', [0.0, 0.0, 0.0])
    d.setdefault('PRIVACY_COMP_TIME_BONUS', [0.0, 0.0, 0.0])
    # booleans default
    for k in ['LOG_ITEM','LOG_DELIVERY','LOG_LOAD','LOG_DROP','LOG_EXPIRE','LOG_MOVE','LOG_FAIL','LOG_RECOVERY','LOG_HELP','LOG_FAKE','LOG_RESCUE']:
        d.setdefault(k, True if k in ['LOG_ITEM','LOG_DELIVERY','LOG_EXPIRE'] else False)
    return Cfg(d)


def _get_rtlola_latency(rtlola_monitor, timeout: float = 0.0):
    if not rtlola_monitor:
        return None, None

    metric_names = (
        'mean_relative_latency_1h',
        'mean_latency_1h',
        'latest_relative_latency',
        'latest_latency',
        'global_relative_latency',
        'global_latency',
    )
    deadline = time.time() + max(0.0, timeout)

    while True:
        metrics = rtlola_monitor.get_all_metrics(timeout=0.0)
        for metric_name in metric_names:
            value = metrics.get(metric_name)
            if value is None:
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if np.isfinite(value) and value > 0:
                return value, metric_name

        if time.time() >= deadline:
            return None, None
        time.sleep(0.001)


def _minimum_delivery_time(cfg: Cfg, space: Space, target_room: Room) -> float:
    if target_room is None:
        return 0.0

    try:
        distance = target_room.getProximity()[space.getSource()]
    except KeyError:
        return 0.0

    return max(
        0.0,
        float(cfg.LOAD_TIME) + float(distance) * float(cfg.MOVEMENT_TIME) + float(cfg.DROP_TIME),
    )


def _prune_times(values, now: float, window: float):
    return [value for value in values if now - value <= window]


def _cfg_bool(cfg: Cfg, name: str, default: bool) -> bool:
    value = getattr(cfg, name, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)


def _recent_message_counts(cfg: Cfg, now: float, window: float):
    events = getattr(cfg, 'da_message_events', [])
    events = [(t, delivered) for t, delivered in events if now - t <= window]
    cfg.da_message_events = events
    sent = len(events)
    lost = sum(1 for _, delivered in events if not delivered)
    return sent, lost


def _runtime_adaptation_metrics(
    cfg: Cfg,
    space: Space,
    now: float,
    created_window,
    failure_window,
    window: float,
) -> dict:
    created_window = _prune_times(created_window, now, window)
    failure_window = _prune_times(failure_window, now, window)
    messages_sent, messages_lost = _recent_message_counts(cfg, now, window)

    pending_tasks = len(space.availItems) + len(space.movingItems)
    created_count = len(created_window)
    pending_ratio = pending_tasks / max(1, created_count)
    failure_rate = len(failure_window) / max(1, int(cfg.N_ROBOTS))
    message_loss_rate = messages_lost / max(1, messages_sent)

    return {
        'pending_tasks': pending_tasks,
        'created_window': created_count,
        'pending_ratio': pending_ratio,
        'failures_window': len(failure_window),
        'failure_rate': failure_rate,
        'messages_sent': messages_sent,
        'messages_lost': messages_lost,
        'message_loss_rate': message_loss_rate,
    }, created_window, failure_window


def _candidate_persisted(candidate_history, candidate, required_checks: int):
    if required_checks <= 1:
        return True, [candidate]
    candidate_history.append(candidate)
    candidate_history = candidate_history[-required_checks:]
    return (
        len(candidate_history) == required_checks
        and all(value == candidate for value in candidate_history)
    ), candidate_history

def _logfile_name(cfg: Cfg) -> str:
    base = cfg.RESULTS_DIR
    os.makedirs(base, exist_ok=True)
    if cfg.ARCHITECTURE == 'decentralized':
        prefix = 'fully_'
    elif cfg.ARCHITECTURE == 'semi-decentralized':
        prefix = 'semi_'
    elif cfg.ARCHITECTURE.startswith('centralized-'):
        prefix = f"centralized{cfg.ARCHITECTURE.split('-',1)[1].capitalize()}_"
    else:
        prefix = f"{cfg.ARCHITECTURE}_"

    name = prefix + cfg.TOPOLOGY_NAME + '_Nbot' + str(cfg.N_ROBOTS) + '_Nmal' + str(cfg.N_MALICIOUS)
    name += '_p' + str(int(cfg.FAIL_PROB*100)) + 'pc_cmF' + str(int(cfg.COMM_FAIL_PROB*1000))
    name += '_A' + str(int(cfg.ITEM_SPAWNING_TIME)) + '_L' + str(int(cfg.LOAD_TIME)) + '_M' + str(int(cfg.MOVEMENT_TIME)) + '_D' + str(int(cfg.DROP_TIME))
    name += '_cp' + str(int(cfg.COMP_TIME)) + '_cm' + str(int(cfg.COMM_TIME)) + '_R' + str(int(cfg.RECOVERY_TIME)) + '.csv'
    return os.path.join(base, name)


def _apply_malicious_count(cfg: Cfg, bots, value):
    try:
        next_count = int(value)
    except (TypeError, ValueError):
        return

    next_count = max(0, min(next_count, len(bots)))
    if getattr(cfg, 'N_MALICIOUS', None) == next_count:
        return

    cfg.N_MALICIOUS = next_count
    for idx, bot in enumerate(bots):
        bot.malicious = idx < next_count

def getTargetRoom(cfg: Cfg, rooms):
    if cfg.TARGETS == -1:
        return None
    if max(cfg.TARGETS) >= len(rooms):
        print('[ERROR] TARGETS has an index outside room range'); sys.exit(-1)
    trg = [t for t in cfg.TARGETS if t != cfg.SOURCE]
    if len(trg) == 0:
        return None
    idx = random.choice(trg)
    return rooms[idx]

def _resolve_topology_name(cfg: Cfg) -> str:
    """Support both full topology names (mesh25) and shorthand (mesh/ring/tree/etc.)."""
    name = cfg.TOPOLOGY_NAME
    if name in topologyName_dict:
        return name
    if name in ['mesh', 'ring', 'tree', 'line', 'star', 'fully_connected', 'fullyconnected', 'bus']:
        if name == 'fullyconnected':
            name = 'fully_connected'
        candidate = f'{name}{cfg.N_ROOMS}'
        if candidate in topologyName_dict:
            return candidate
    print('Unsupported topology:', name)
    sys.exit(-1)

def _build_custom_topology(cfg: Cfg):
    custom = getattr(cfg, 'CUSTOM_TOPOLOGY', None)
    if not isinstance(custom, dict):
        print('Missing CUSTOM_TOPOLOGY for custom room layout')
        sys.exit(-1)

    nodes = custom.get('nodes', [])
    edges = custom.get('edges', [])
    try:
        node_ids = sorted(int(node['id']) for node in nodes)
    except Exception:
        print('Invalid CUSTOM_TOPOLOGY nodes')
        sys.exit(-1)

    expected_ids = list(range(len(node_ids)))
    if node_ids != expected_ids:
        print('CUSTOM_TOPOLOGY nodes must be sequential room IDs starting at 0')
        sys.exit(-1)

    topology = {idx: [] for idx in node_ids}
    for edge in edges:
        try:
            source = int(edge['source'])
            target = int(edge['target'])
        except Exception:
            print('Invalid CUSTOM_TOPOLOGY edge')
            sys.exit(-1)

        if source == target or source not in topology or target not in topology:
            print('CUSTOM_TOPOLOGY contains an invalid edge')
            sys.exit(-1)
        if target not in topology[source]:
            topology[source].append(target)
        if source not in topology[target]:
            topology[target].append(source)

    if not edges:
        print('CUSTOM_TOPOLOGY needs at least one edge')
        sys.exit(-1)

    visited = {0}
    queue = [0]
    while queue:
        room = queue.pop(0)
        for neighbor in topology[room]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    if len(visited) != len(topology):
        print('CUSTOM_TOPOLOGY must be connected')
        sys.exit(-1)

    return {idx: sorted(adjacents) for idx, adjacents in topology.items()}

def run(config_path='config.json'):
    cfg = _build_cfg(config_path)
    seed = getattr(cfg, 'RANDOM_SEED', None)
    if seed is not None:
        random.seed(int(seed))
        np.random.seed(int(seed))
    # print("DEBUG: Loaded Config:", json.dumps(cfg.__dict__, indent=2))
    
    # Validate architecture
    valid_archs = ['decentralized', 'semi-decentralized', 'centralized-proximity', 
                   'centralized-importance', 'centralized-proximp', 'centralized-impprox', 
                   'dynamic-adaptation']
    if cfg.ARCHITECTURE not in valid_archs:
        print('Unsupported architecture:', cfg.ARCHITECTURE); sys.exit(-1)
    
    # Initialize RTLola monitor for dynamic-adaptation
    rtlola_monitor = None
    if cfg.ARCHITECTURE == 'dynamic-adaptation':
        # print("[Monitor] Initializing RTLola CLI for dynamic-adaptation")
        try:
            from .rtlola_monitor import RTLolaMonitor
            # Get spec file path - convert to absolute if relative
            spec_file = getattr(cfg, 'RTLOLA_SPEC_FILE', 'spec2.rtlola')
            if not os.path.isabs(spec_file):
                # Try project root first, then fallback to sim package directory
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                candidate_root = os.path.join(project_root, spec_file)
                script_dir = os.path.dirname(os.path.abspath(__file__))
                candidate_pkg = os.path.join(script_dir, spec_file)
                spec_file = candidate_root if os.path.exists(candidate_root) else candidate_pkg
            
            rtlola_binary = getattr(cfg, 'RTLOLA_BINARY_PATH', None)
            rtlola_monitor = RTLolaMonitor(spec_file=spec_file, rtlola_binary=rtlola_binary)
            # print(f"[RTLola] Using spec: {spec_file}")
        except Exception as e:
            print(f"[ERROR] Failed to initialize RTLola monitor: {e}")
            print(f"[ERROR] RTLola is required for dynamic-adaptation architecture.")
            print(f"[ERROR] Ensure 'rtlola-cli' is installed and in your PATH, or configured in config.json.")
            sys.exit(-1)
    
    if cfg.TOPOLOGY_NAME == 'custom':
        topo = _build_custom_topology(cfg)
        resolved_topology_name = getattr(cfg, 'CUSTOM_TOPOLOGY_NAME', 'custom')
        cfg.TOPOLOGY_NAME = resolved_topology_name
    else:
        resolved_topology_name = _resolve_topology_name(cfg)
        cfg.TOPOLOGY_NAME = resolved_topology_name
        topo = topologyName_dict[resolved_topology_name]
    if cfg.N_ROOMS != len(topo.keys()):
        print('N_ROOMS mismatch with selected TOPOLOGY_NAME'); sys.exit(-1)

    # resolve logfile
    logfile = cfg.LOGFILE if cfg.LOGFILE else _logfile_name(cfg)
    cfg.LOGFILE = logfile  # write back

    # Remove existing logfile to ensure fresh simulation data
    if os.path.exists(logfile):
        try:
            os.remove(logfile)
        except OSError:
            pass

    # init env
    start_wall = time.time()
    clock = Clock()
    rooms = [Room(i) for i in range(cfg.N_ROOMS)]
    space = Space(cfg, rooms, topo, clock, source=rooms[cfg.SOURCE])
    
    # Set RTLola monitor reference in cfg for Robot access
    cfg.rtlola_monitor = rtlola_monitor

    # robots
    bots = []
    for i in range(cfg.N_ROBOTS):
        bots.append(Robot(cfg, i, i < cfg.N_MALICIOUS, space, logfile))
    botsRandomOrder = list(bots)

    # schedule first item
    clock.scheduleEvent('item', [cfg.ITEM_SPAWNING_TIME], [cfg.ITEM_SPAWNING_TRACE], [cfg.ITEM_SPAWNING_DISTR])

    itemIdx = 0
    event_count = 0
    last_adaptation_check = 0.0
    adaptation_interval = getattr(cfg, 'ADAPTATION_CHECK_INTERVAL', 300.0)  # Check every 5 minutes by default
    
    # Overhead tracking for dynamic adaptation
    adaptation_overhead_total = 0.0  # Total wall-clock time spent on adaptation
    adaptation_check_count = 0       # Number of adaptation checks performed
    adaptation_switch_count = 0      # Number of architecture switches
    adaptation_overhead_samples = [] # Individual overhead measurements
    
    # Adaptation State
    smoothed_latency = None
    alpha = 0.2 # Smoothing factor for EMA
    last_switch_time = -300.0 # Allow immediate switch at start
    min_time_between_switches = float(getattr(cfg, 'ADAPTATION_MIN_SWITCH_INTERVAL', 30.0))
    candidate_history = []
    
    # Relative-latency tracking for adaptation (Python-based fallback)
    latency_window = []  # Store (timestamp, relative latency) tuples
    latency_window_duration = float(getattr(cfg, 'ADAPTATION_WINDOW', 3600.0))
    created_window = []
    failure_window = []
    item_create_times = {}  # Track when each item was created
    item_min_delivery_times = {}  # Track ideal delivery time by item
    adaptation_latency_history = []  # Store aggregate latency seen at adaptation checks
    
    try:
        while clock.getTime() < cfg.SIM_TIME:
            clock.checkClock()
            ts, event = clock.getNextEvent()
            
            # Dynamic Parameter Updates (Scenario A)
            # Check if we have phases defined in config
            if hasattr(cfg, 'PHASES') and cfg.PHASES:
                for phase in cfg.PHASES:
                    if phase['start'] <= ts < phase['end']:
                        # Apply phase parameters
                        if 'N_MALICIOUS' in phase:
                            _apply_malicious_count(cfg, bots, phase['N_MALICIOUS'])

                        if 'FAIL_PROB' in phase and cfg.FAIL_PROB != phase['FAIL_PROB']:
                            cfg.FAIL_PROB = phase['FAIL_PROB']
                            # print(f"[Phase] Time {ts:.1f}: Changed FAIL_PROB to {cfg.FAIL_PROB}")
                        
                        if 'COMM_FAIL_PROB' in phase and cfg.COMM_FAIL_PROB != phase['COMM_FAIL_PROB']:
                            cfg.COMM_FAIL_PROB = phase['COMM_FAIL_PROB']
                            # print(f"[Phase] Time {ts:.1f}: Changed COMM_FAIL_PROB to {cfg.COMM_FAIL_PROB}")

                        if 'RECOVERY_TIME' in phase and cfg.RECOVERY_TIME != phase['RECOVERY_TIME']:
                            cfg.RECOVERY_TIME = phase['RECOVERY_TIME']
                            # print(f"[Phase] Time {ts:.1f}: Changed RECOVERY_TIME to {cfg.RECOVERY_TIME}")
                            
                        if 'ITEM_SPAWNING_TIME' in phase and cfg.ITEM_SPAWNING_TIME != phase['ITEM_SPAWNING_TIME']:
                            cfg.ITEM_SPAWNING_TIME = phase['ITEM_SPAWNING_TIME']
                            # print(f"[Phase] Time {ts:.1f}: Changed ITEM_SPAWNING_TIME to {cfg.ITEM_SPAWNING_TIME}")
                        break
            
            # Artificial delay removed
            # time.sleep(0.001)
            
            # Check if no more events (simulation complete)
            if event is None:
                # print(f"[INFO] No more events at time {clock.getTime()}. Simulation complete.")
                break
                
            event_count += 1
            
            # Send event to RTLola if monitoring is active
            if rtlola_monitor and rtlola_monitor.is_running():
                # Determine event details for RTLola (spec2.rtlola format: time,itemId,event,destination)
                item_id = -1
                destination = -1
                event_type = ""
                
                if event == 'item':
                    event_type = "create"
                    item_id = itemIdx
                    destination = -1  # Not yet assigned
                elif event.startswith('move-'):
                    idx = int(event.split('-')[1])
                    if bots[idx].getItem():
                        item_id = bots[idx].getItem().getIdx()
                        destination = bots[idx].destination.getIdx()
                        event_type = "move"
                elif event.startswith('recovery-'):
                    event_type = "recover"
                elif event.startswith('expire-'):
                    item_id = int(event.split('-')[1])
                    event_type = "expire"
                
                # Send to RTLola (only send events that RTLola cares about)
                if event_type in ["create", "deliver"]:
                    try:
                        rtlola_monitor.send_event(ts, -1, item_id, -1, -1, destination, event_type)
                    except Exception as e:
                        print(f"[RTLola] Error sending event: {e}")
            
            # Process simulation event
            if event == 'item':
                trg = getTargetRoom(cfg, rooms)
                item = Item(cfg, logfile, itemIdx, space, ts, imp=-1, target=trg)
                space.newItem(item)
                item_create_times[itemIdx] = ts  # Track creation time
                item_min_delivery_times[itemIdx] = _minimum_delivery_time(cfg, space, item.getTarget())
                created_window.append(ts)
                created_window = _prune_times(created_window, ts, latency_window_duration)
                itemIdx += 1
                random.shuffle(botsRandomOrder)
                for bot in botsRandomOrder:
                    if bot.getLocation() == space.getSource() and bot.isFree() and bot.isHealthy() and not bot.hasOtherTasks():
                        it = space.getMoreImportantItem(room=space.getSource())
                        if it is not None:
                            bot.loadItem(it, clock.getTime())
                            break
            elif event.startswith('move-'):
                idx = int(event.split('-')[1])
                bot = bots[idx]

                item_before_move = bot.getItem()
                delivery_item_id = item_before_move.getIdx() if item_before_move is not None else None
                delivery_destination = bot.destination if item_before_move is not None else None
                delivery_destination_id = delivery_destination.getIdx() if delivery_destination is not None else -1

                # Process the move first: delivery is triggered inside Robot.move().
                was_healthy = bot.isHealthy()
                bots[idx].move(ts)
                if was_healthy and not bot.isHealthy():
                    failure_window.append(ts)
                    failure_window = _prune_times(failure_window, ts, latency_window_duration)

                if item_before_move is not None and bot.getLocation() == delivery_destination:
                    if delivery_item_id in item_create_times:
                        delivery_latency = ts - item_create_times[delivery_item_id]
                        min_delivery_time = item_min_delivery_times.get(delivery_item_id, 0.0)
                        relative_latency = max(0.0, delivery_latency - min_delivery_time)
                        
                        if delivery_latency > 0:
                            latency_window.append((ts, relative_latency))
                            
                            latency_window = [(t, lat) for t, lat in latency_window if ts - t <= latency_window_duration]
                    
                    if rtlola_monitor and rtlola_monitor.is_running():
                        try:
                            rtlola_monitor.send_event(ts, -1, delivery_item_id, -1, -1, delivery_destination_id, "deliver")
                        except Exception as e:
                            print(f"[RTLola] Error sending delivery event: {e}")
            elif event.startswith('recovery-'):
                idx = int(event.split('-')[1]); bots[idx].recovery(ts)
            elif event.startswith('expire-'):
                idx = int(event.split('-')[1]); item = space.getItembyId(idx); space.expireItem(item, ts)
            
            # Check for architecture adaptation (score-based)
            if rtlola_monitor and rtlola_monitor.is_running() and (ts - last_adaptation_check) >= adaptation_interval:
                last_adaptation_check = ts
                try:
                    rtlola_monitor.send_event(ts, -1, -1, -1, -1, -1, "adaptation_check")
                except Exception as e:
                    print(f"[RTLola] Error sending adaptation check: {e}")
                
                # Start overhead measurement
                adaptation_start_time = time.time()
                adaptation_check_count += 1
                
                # Prefer the live RTLola metric, with the Python window as a safe fallback.
                rtlola_query_start = time.time()
                metric_timeout = getattr(cfg, 'RTLOLA_METRIC_TIMEOUT', 0.0)
                rtlola_latency, rtlola_metric = _get_rtlola_latency(rtlola_monitor, timeout=metric_timeout)
                python_latency = sum(lat for _, lat in latency_window) / len(latency_window) if latency_window else None
                if rtlola_latency is not None:
                    raw_latency = rtlola_latency
                    latency_source = f'rtlola:{rtlola_metric}'
                else:
                    raw_latency = python_latency
                    latency_source = 'python_window' if python_latency is not None else 'none'
                rtlola_query_time = time.time() - rtlola_query_start

                runtime_metrics, created_window, failure_window = _runtime_adaptation_metrics(
                    cfg,
                    space,
                    ts,
                    created_window,
                    failure_window,
                    latency_window_duration,
                )

                if raw_latency is not None:
                    if smoothed_latency is None:
                        smoothed_latency = raw_latency
                    else:
                        smoothed_latency = alpha * raw_latency + (1 - alpha) * smoothed_latency

                effective_latency = smoothed_latency if smoothed_latency is not None else raw_latency

                scoring_start = time.time()
                current_arch = cfg.current_architecture
                candidate_arch = current_arch
                best_arch = current_arch
                scores = {}
                score_details = {}
                switch_reason = 'no_latency'

                # Import scoring functions
                from .architecture_scoring import get_latency_thresholds
                threshold_context = get_latency_thresholds(cfg, adaptation_latency_history)

                time_since_last_switch = ts - last_switch_time
                if time_since_last_switch < min_time_between_switches:
                    switch_reason = 'cooldown'
                else:
                    policy = str(getattr(cfg, 'ADAPTATION_POLICY', 'hybrid-score')).lower()
                    if policy in {'latency-threshold', 'legacy', 'latency'}:
                        if effective_latency is not None:
                            from .architecture_scoring import select_best_architecture
                            candidate_arch, scores = select_best_architecture(
                                cfg,
                                effective_latency,
                                latency_history=adaptation_latency_history,
                                current_architecture=current_arch,
                                thresholds=threshold_context,
                            )
                            best_arch = candidate_arch
                            switch_reason = 'latency_threshold'
                    else:
                        from .architecture_scoring import select_hybrid_architecture
                        candidate_arch, scores, score_details = select_hybrid_architecture(
                            cfg,
                            effective_latency,
                            runtime_metrics=runtime_metrics,
                            latency_history=adaptation_latency_history,
                            current_architecture=current_arch,
                            thresholds=threshold_context,
                        )
                        best_arch = candidate_arch
                        switch_reason = score_details.get('state', 'hybrid_score')

                    if best_arch != current_arch and policy not in {'latency-threshold', 'legacy', 'latency'}:
                        required_checks = max(1, int(getattr(cfg, 'ADAPTATION_PERSISTENCE_CHECKS', 2)))
                        bypass_persistence = (
                            score_details.get('critical_override', False)
                            and _cfg_bool(cfg, 'ADAPTATION_CRITICAL_BYPASS_PERSISTENCE', True)
                        )
                        persisted, candidate_history = _candidate_persisted(
                            candidate_history,
                            candidate_arch,
                            required_checks,
                        )
                        if not (bypass_persistence or persisted):
                            best_arch = current_arch
                            switch_reason = f'waiting_persistence_{len(candidate_history)}/{required_checks}'
                    elif best_arch == current_arch:
                        candidate_history = []

                    if best_arch != current_arch:
                        adaptation_switch_count += 1
                        last_switch_time = ts
                        cfg.set_architecture(best_arch)
                        candidate_history = []
                        with open(logfile, 'a') as f:
                            f.write(f'{ts},-2,-1,-1,-1,-1,switch_architecture_{best_arch}\n')

                scoring_time = time.time() - scoring_start

                if effective_latency is not None:
                    adaptation_latency_history.append(effective_latency)
                    try:
                        history_limit = max(1, int(getattr(cfg, 'ADAPTIVE_THRESHOLD_WINDOW', 12)))
                    except (TypeError, ValueError):
                        history_limit = 12
                    adaptation_latency_history = adaptation_latency_history[-history_limit:]

                check_overhead = time.time() - adaptation_start_time
                adaptation_overhead_total += check_overhead
                adaptation_overhead_samples.append({
                    'sim_time': ts,
                    'total_overhead_ms': check_overhead * 1000,
                    'rtlola_query_ms': rtlola_query_time * 1000,
                    'scoring_ms': scoring_time * 1000,
                    'switched': best_arch != current_arch,
                    'latency': effective_latency,
                    'raw_latency': raw_latency,
                    'latency_source': latency_source,
                    'threshold_low': threshold_context.get('low'),
                    'threshold_high': threshold_context.get('high'),
                    'threshold_mode': threshold_context.get('mode'),
                    'threshold_history_size': threshold_context.get('history_size'),
                    'performance_score': score_details.get('score'),
                    'performance_state': score_details.get('state'),
                    'fd_pressure': score_details.get('fd_pressure'),
                    'recovery_mode': score_details.get('recovery_mode'),
                    'score_latency': score_details.get('components', {}).get('latency'),
                    'score_pending': score_details.get('components', {}).get('pending'),
                    'score_failure': score_details.get('components', {}).get('failure'),
                    'score_message_loss': score_details.get('components', {}).get('message_loss'),
                    'pending_tasks': runtime_metrics.get('pending_tasks'),
                    'created_window': runtime_metrics.get('created_window'),
                    'pending_ratio': runtime_metrics.get('pending_ratio'),
                    'failures_window': runtime_metrics.get('failures_window'),
                    'failure_rate': runtime_metrics.get('failure_rate'),
                    'messages_sent': runtime_metrics.get('messages_sent'),
                    'messages_lost': runtime_metrics.get('messages_lost'),
                    'message_loss_rate': runtime_metrics.get('message_loss_rate'),
                    'current_architecture': current_arch,
                    'candidate_architecture': candidate_arch,
                    'selected_architecture': best_arch,
                    'switch_reason': switch_reason,
                })

                # # Log overhead info
                # print(f"[OVERHEAD] Check #{adaptation_check_count}: {check_overhead*1000:.2f}ms "
                #       f"(RTLola: {rtlola_query_time*1000:.2f}ms, Scoring: {scoring_time*1000:.2f}ms)")
    
    finally:
        # Clean up RTLola monitor
        if rtlola_monitor:
            rtlola_monitor.shutdown()

    wall_time = time.time() - start_wall
    _log_sim_time(cfg, wall_time)
    _sort_events_csv_by_time(logfile)
    
    # Log adaptation overhead statistics
    log_overhead_statistics(
        adaptation_check_count,
        adaptation_switch_count,
        adaptation_overhead_total,
        adaptation_overhead_samples,
        wall_time,
        logfile
    )
    
    print(os.path.basename(logfile), '--> Simulation time (wall):', wall_time, f'({event_count} events)')
    return logfile, wall_time, event_count

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'config.json'
    run(path)
