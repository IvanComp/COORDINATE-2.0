
import os, sys, time, json, random
from threading import Lock
import numpy as np

from .core import Cfg, Clock, Room, Space, Item, Robot, EVENT_LOG_HEADER
from .env_maps import topologyName_dict
from .adaptation_overhead import log_overhead_statistics, overhead_log_path
from .run_statistics import RunResult, TaskRecord, summarize_run, summary_path, write_summary

_simulation_lock = Lock()

def _sort_events_csv_by_time(csv_path: str) -> int:
    if not os.path.exists(csv_path):
        return 0
    try:
        with open(csv_path, 'r') as f:
            lines = f.readlines()
        if not lines:
            return 0
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
        return len(rows)
    except Exception:
        return 0


def _log_sim_time(cfg: Cfg, sim_secs: float):
    # write simTime.csv
    path = cfg.SIMTIME_LOGFILE
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
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
    d.setdefault('ADAPTATION_POLICY', 'contextual-bandit')
    d.setdefault('ADAPTATION_CHECK_INTERVAL', 300.0)
    d.setdefault('ADAPTATION_WINDOW', 3600.0)
    d.setdefault('ADAPTATION_MIN_SWITCH_INTERVAL', 30.0)
    d.setdefault('ADAPTATION_PERSISTENCE_CHECKS', 2)
    d.setdefault('ADAPTATION_CRITICAL_BYPASS_PERSISTENCE', True)
    d.setdefault('BANDIT_EXPLORATION_EPSILON', 0.08)
    d.setdefault('BANDIT_MIN_EXPLORATION_EPSILON', 0.02)
    d.setdefault('BANDIT_EXPLORATION_DECAY', 0.995)
    d.setdefault('BANDIT_EXPLORATION_BYPASS_PERSISTENCE', True)
    d.setdefault('BANDIT_IMPROVEMENT_MARGIN', 0.02)
    d.setdefault('BANDIT_SWITCH_PENALTY', 0.03)
    d.setdefault('BANDIT_REWARD_VERSION', 'completion-constrained-v1')
    d.setdefault('BANDIT_COMPLETION_TARGET', 0.65)
    d.setdefault('BANDIT_MIN_TERMINAL_OUTCOMES', 3)
    # These normalizers preserve useful variation in the one-hour RTLola
    # evidence. They are not thresholds and do not encode a mechanism prior.
    d.setdefault('BANDIT_CREATED_TASKS_REF', 40.0)
    d.setdefault('BANDIT_FAILURE_REF', 2.5)
    d.setdefault('BANDIT_SUSPICION_REF', 10.0)
    d.setdefault('NETWORK_PROBE_SAMPLES_PER_CHECK', 5)
    d.setdefault('BANDIT_RIDGE', 1.0)
    d.setdefault('BANDIT_UCB_ALPHA', 0.50)
    d.setdefault('BANDIT_INITIAL_SAMPLES_PER_ACTION', 2)
    d.setdefault('BANDIT_CONTEXT_MIN_SAMPLES_PER_ACTION', 1)
    d.setdefault('BANDIT_CONTEXT_BIN_THRESHOLD', 0.5)
    d.setdefault('BANDIT_INITIAL_SAMPLING_BYPASS_PERSISTENCE', True)
    d.setdefault('LATENCY_THRESHOLD_LOW', 10.0)
    d.setdefault('LATENCY_THRESHOLD_HIGH', 40.0)
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
    # Centralized coordination has finite decision capacity; FD patrols are a
    # bounded shared resource rather than a free inspection loop per robot.
    d.setdefault('COORDINATOR_SERVICE_TIME', 0.25)
    d.setdefault('COORDINATOR_FAKE_REQUEST_SERVICE_TIME', d['COORDINATOR_SERVICE_TIME'])
    d.setdefault('COORDINATOR_COMMAND_LOSS_PROB', -1.0)
    d.setdefault('COORDINATOR_FAILURE_PROB', 0.0)
    d.setdefault('COORDINATOR_AVAILABLE', True)
    d.setdefault('FD_INSPECTION_INTERVAL', 15 * 60.0)
    d.setdefault('FD_MAX_PATROLLERS', 6)
    d.setdefault('SD_COORDINATION_HOPS', 1)
    # Verifying a received rescue request is a local decision step. By default
    # it uses the existing per-agent computation cost from the COORDINATE model.
    d.setdefault('RESCUE_VERIFICATION_TIME', d.get('COMP_TIME', 0.0))
    # booleans default
    for k in ['LOG_ITEM','LOG_DELIVERY','LOG_LOAD','LOG_DROP','LOG_EXPIRE','LOG_MOVE','LOG_FAIL','LOG_RECOVERY','LOG_HELP','LOG_FAKE','LOG_RESCUE']:
        d.setdefault(k, True if k in ['LOG_ITEM','LOG_DELIVERY','LOG_EXPIRE'] else False)
    return Cfg(d)


def _get_rtlola_latency(metrics: dict):
    metric_names = (
        'mean_relative_latency_1h',
        'mean_latency_1h',
        'latest_relative_latency',
        'latest_latency',
        'global_relative_latency',
        'global_latency',
    )
    for metric_name in metric_names:
        value = metrics.get(metric_name)
        if value is not None and np.isfinite(value) and value > 0:
            return value, metric_name
    return None, None


def _apply_rtlola_context_metrics(cfg: Cfg, metrics: dict, observed: dict) -> dict:
    def monitor_value(name: str, default: float = 0.0) -> float:
        try:
            value = float(observed.get(name, default))
        except (TypeError, ValueError):
            return default
        return value if np.isfinite(value) else default

    def optional_monitor_value(name: str):
        if name not in observed:
            return None
        return monitor_value(name)

    failures = max(0.0, monitor_value('monitor_failures_1h'))
    messages = max(0.0, monitor_value('monitor_message_count_1h'))
    losses = max(0.0, monitor_value('monitor_message_losses_1h'))
    probe_messages = max(0.0, monitor_value('monitor_network_probe_count_1h'))
    probe_losses = max(0.0, monitor_value('monitor_network_probe_losses_1h'))
    fake_evidence = max(0.0, monitor_value('monitor_fake_evidence_1h'))
    suspicious_signals = max(0.0, monitor_value('monitor_suspicious_signals_1h'))
    rescue_requests = max(0.0, monitor_value('monitor_rescue_requests_1h'))
    outages = max(0.0, monitor_value('monitor_coordinator_outages_1h'))

    created = optional_monitor_value('monitor_created_tasks_1h')
    delivered = optional_monitor_value('monitor_delivered_tasks_1h')
    expired = optional_monitor_value('monitor_expired_tasks_1h')

    metrics.update({
        'failures_window': failures,
        'failure_rate': failures / max(1, int(cfg.N_ROBOTS)),
        'messages_sent': messages,
        'messages_lost': losses,
        'message_loss_rate': losses / max(1.0, messages),
        'network_probe_count': probe_messages,
        'network_probe_losses': probe_losses,
        'network_probe_loss_rate': probe_losses / max(1.0, probe_messages),
        'suspicion_evidence': fake_evidence,
        'suspicious_signals_window': suspicious_signals,
        'rescue_requests': rescue_requests,
        'suspicion_rate': fake_evidence / max(1.0, rescue_requests),
        'coordinator_outages': outages,
        'coordinator_outage_rate': outages / max(1.0, rescue_requests),
    })

    # Completion is a terminal-outcome rate, not delivered/created in the same
    # rolling window: the latter is distorted by work created before the window
    # and by tasks that are still pending. All three event counts originate
    # from RTLola, with the Python event window retained only as startup fallback.
    if created is not None and delivered is not None and expired is not None:
        created_count = max(0, int(round(created)))
        delivered_count = max(0, int(round(delivered)))
        expired_count = max(0, int(round(expired)))
        terminal_count = delivered_count + expired_count
        pending_tasks = max(0, int(metrics.get('pending_tasks', 0)))
        metrics.update({
            'created_window': created_count,
            'delivered_window': delivered_count,
            'expired_window': expired_count,
            'terminal_tasks_window': terminal_count,
            'completion_available': terminal_count > 0,
            'completion_rate': delivered_count / terminal_count if terminal_count else 0.0,
            'completion_source': 'rtlola_terminal_outcomes_1h',
            'pending_ratio': pending_tasks / max(1, created_count),
            'deadline_miss_rate': expired_count / max(1, created_count),
            'throughput_rate': delivered_count / max(1e-9, float(getattr(cfg, 'ADAPTATION_WINDOW', 3600.0))),
            'throughput_norm': min(1.0, delivered_count / max(1, created_count)),
        })
    return metrics


def _minimum_delivery_time(cfg: Cfg, space: Space, target_room: Room) -> float:
    if target_room is None:
        return 0.0

    try:
        distance = space.getSource().getProximity()[target_room]
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
    delivered_window,
    expired_window,
    failure_window,
    window: float,
) -> dict:
    created_window = _prune_times(created_window, now, window)
    delivered_window = _prune_times(delivered_window, now, window)
    expired_window = _prune_times(expired_window, now, window)
    failure_window = _prune_times(failure_window, now, window)
    messages_sent, messages_lost = _recent_message_counts(cfg, now, window)

    pending_tasks = len(space.availItems) + len(space.movingItems)
    created_count = len(created_window)
    delivered_count = len(delivered_window)
    expired_count = len(expired_window)
    terminal_count = delivered_count + expired_count
    pending_ratio = pending_tasks / max(1, created_count)
    failure_rate = len(failure_window) / max(1, int(cfg.N_ROBOTS))
    message_loss_rate = messages_lost / max(1, messages_sent)
    deadline_miss_rate = expired_count / max(1, created_count)
    throughput_rate = delivered_count / max(1e-9, window)
    throughput_norm = delivered_count / max(1, created_count)

    robots = space.getAllRobots()
    idle_agents = sum(
        1 for robot in robots
        if robot.isHealthy() and robot.isFree() and not robot.hasOtherTasks()
    )
    idle_ratio = idle_agents / max(1, len(robots))

    return {
        'pending_tasks': pending_tasks,
        'created_window': created_count,
        'delivered_window': delivered_count,
        'expired_window': expired_count,
        'terminal_tasks_window': terminal_count,
        'completion_available': terminal_count > 0,
        'completion_rate': delivered_count / terminal_count if terminal_count else 0.0,
        'completion_source': 'python_terminal_outcomes_window',
        'pending_ratio': pending_ratio,
        'failures_window': len(failure_window),
        'failure_rate': failure_rate,
        'messages_sent': messages_sent,
        'messages_lost': messages_lost,
        'message_loss_rate': message_loss_rate,
        'deadline_miss_rate': deadline_miss_rate,
        'throughput_rate': throughput_rate,
        'throughput_norm': min(1.0, throughput_norm),
        'idle_agents': idle_agents,
        'idle_ratio': idle_ratio,
    }, created_window, delivered_window, expired_window, failure_window


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

def _validate_targets(cfg: Cfg, room_count: int):
    targets = cfg.TARGETS
    if type(targets) is int and targets == -1:
        if room_count < 2:
            raise ValueError('TARGETS=-1 requires a room other than SOURCE')
        return None
    if not isinstance(targets, list) or not targets:
        raise ValueError('TARGETS must be -1 or a non-empty list of room IDs')
    if any(type(room) is not int or not 0 <= room < room_count for room in targets):
        raise ValueError(f'TARGETS must contain integer room IDs from 0 to {room_count - 1}')
    destinations = [room for room in targets if room != cfg.SOURCE]
    if not destinations:
        raise ValueError('TARGETS must include a room other than SOURCE')
    return destinations


def getTargetRoom(cfg: Cfg, rooms):
    destinations = _validate_targets(cfg, len(rooms))
    return rooms[random.choice(destinations)] if destinations else None

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
    result = run_with_stats(config_path)
    return result.logfile, result.wall_time, result.event_count


def run_with_stats(config_path='config.json', *, collect_tasks=False):
    with _simulation_lock:
        return _run(config_path, collect_tasks)


def _run(config_path, collect_tasks):
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
    
    if cfg.TOPOLOGY_NAME == 'custom':
        topo = _build_custom_topology(cfg)
        cfg.TOPOLOGY_NAME = getattr(cfg, 'CUSTOM_TOPOLOGY_NAME', 'custom')
    else:
        cfg.TOPOLOGY_NAME = _resolve_topology_name(cfg)
        topo = topologyName_dict[cfg.TOPOLOGY_NAME]
    if cfg.N_ROOMS != len(topo):
        print('N_ROOMS mismatch with selected TOPOLOGY_NAME'); sys.exit(-1)
    _validate_targets(cfg, len(topo))

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
    
    # resolve logfile
    logfile = cfg.LOGFILE if cfg.LOGFILE else _logfile_name(cfg)
    cfg.LOGFILE = logfile  # write back

    summary_path(logfile).unlink(missing_ok=True)
    overhead_log_path(logfile).unlink(missing_ok=True)
    os.makedirs(os.path.dirname(logfile) or '.', exist_ok=True)
    with open(logfile, 'w') as trace:
        trace.write(EVENT_LOG_HEADER)

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

    # Legacy FD is strictly local: agents only inspect tasks when their normal
    # routes bring them to a room. Newer scenarios can opt into a bounded
    # patrol explicitly, without changing the historical baseline.
    inspection_interval = max(1.0, float(getattr(cfg, 'FD_INSPECTION_INTERVAL', 15 * 60.0)))
    fd_patroller_count = 0
    if bool(getattr(cfg, 'FD_PATROL_ENABLED', True)):
        fd_patroller_count = min(len(bots), max(0, int(getattr(cfg, 'FD_MAX_PATROLLERS', 4))))
    for slot in range(fd_patroller_count):
        clock.scheduleEvent(
            f'fd-inspection-{slot}',
            [inspection_interval * slot / fd_patroller_count],
            ['_'],
            ['deterministic'],
        )

    # FD local scouts are fixed agents. They independently choose a local
    # random walk; unlike the retired patrol, no shared cursor or dispatcher
    # assigns robots or rooms.
    local_scout_count = 0
    if bool(getattr(cfg, 'FD_LOCAL_SEARCH_ENABLED', False)):
        local_scout_count = min(len(bots), max(0, int(getattr(cfg, 'FD_LOCAL_SEARCH_AGENT_COUNT', 0))))
    local_search_interval = max(1.0, float(getattr(cfg, 'FD_LOCAL_SEARCH_INTERVAL', 15 * 60.0)))
    for idx in range(local_scout_count):
        clock.scheduleEvent(
            f'fd-local-search-{idx}',
            [local_search_interval * idx / max(1, local_scout_count)],
            ['_'],
            ['deterministic'],
        )

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
    adaptation_policy = str(getattr(cfg, 'ADAPTATION_POLICY', 'contextual-bandit')).lower()
    bandit_policy = None
    bandit_pending_action = None
    bandit_pending_context = None
    bandit_pending_started_at = None
    bandit_feedback_window = max(
        float(getattr(cfg, 'ADAPTATION_CHECK_INTERVAL', 300.0)),
        float(getattr(cfg, 'BANDIT_FEEDBACK_WINDOW', getattr(cfg, 'ADAPTATION_WINDOW', 3600.0))),
    )
    if cfg.ARCHITECTURE == 'dynamic-adaptation':
        try:
            from .contextual_bandit import BANDIT_POLICIES, ConservativeContextualBandit
            if adaptation_policy in BANDIT_POLICIES:
                bandit_policy = ConservativeContextualBandit(cfg)
        except Exception as e:
            print(f"[WARNING] Could not initialize contextual-bandit policy: {e}")
    
    # Relative-latency tracking for adaptation (Python-based fallback)
    latency_window = []  # Store (timestamp, relative latency) tuples
    latency_window_duration = float(getattr(cfg, 'ADAPTATION_WINDOW', 3600.0))
    created_window = []
    delivered_window = []
    expired_window = []
    failure_window = []
    item_create_times = {}  # Track when each item was created
    item_min_delivery_times = {}  # Track ideal delivery time by item
    adaptation_latency_history = []  # Store aggregate latency seen at adaptation checks
    deliveries = []
    switches = []
    tasks = {}
    expired_count = failed_count = recovered_count = 0
    
    try:
        while True:
            clock.checkClock()
            ts, event = clock.getNextEvent(through=cfg.SIM_TIME)
            if event is None:
                break
            
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

                        if (
                            'COORDINATOR_SERVICE_TIME' in phase
                            and cfg.COORDINATOR_SERVICE_TIME != phase['COORDINATOR_SERVICE_TIME']
                        ):
                            cfg.COORDINATOR_SERVICE_TIME = phase['COORDINATOR_SERVICE_TIME']
                            # print(f"[Phase] Time {ts:.1f}: Changed coordinator service time")

                        if (
                            'COORDINATOR_FAILURE_PROB' in phase
                            and cfg.COORDINATOR_FAILURE_PROB != phase['COORDINATOR_FAILURE_PROB']
                        ):
                            cfg.COORDINATOR_FAILURE_PROB = phase['COORDINATOR_FAILURE_PROB']
                            # print(f"[Phase] Time {ts:.1f}: Changed coordinator failure probability")

                        if (
                            'COORDINATOR_AVAILABLE' in phase
                            and cfg.COORDINATOR_AVAILABLE != phase['COORDINATOR_AVAILABLE']
                        ):
                            cfg.COORDINATOR_AVAILABLE = phase['COORDINATOR_AVAILABLE']
                            # print(f"[Phase] Time {ts:.1f}: Changed coordinator availability")

                        if 'RECOVERY_TIME' in phase and cfg.RECOVERY_TIME != phase['RECOVERY_TIME']:
                            cfg.RECOVERY_TIME = phase['RECOVERY_TIME']
                            # print(f"[Phase] Time {ts:.1f}: Changed RECOVERY_TIME to {cfg.RECOVERY_TIME}")
                            
                        if 'ITEM_SPAWNING_TIME' in phase and cfg.ITEM_SPAWNING_TIME != phase['ITEM_SPAWNING_TIME']:
                            cfg.ITEM_SPAWNING_TIME = phase['ITEM_SPAWNING_TIME']
                            # print(f"[Phase] Time {ts:.1f}: Changed ITEM_SPAWNING_TIME to {cfg.ITEM_SPAWNING_TIME}")
                        break
            
            # Artificial delay removed
            # time.sleep(0.001)
            
            event_count += 1
            
            # Process simulation event
            if event == 'item':
                trg = getTargetRoom(cfg, rooms)
                item = Item(cfg, logfile, itemIdx, space, ts, imp=-1, target=trg)
                space.newItem(item)
                item_create_times[itemIdx] = ts  # Track creation time
                item_min_delivery_times[itemIdx] = _minimum_delivery_time(cfg, space, item.getTarget())
                if collect_tasks:
                    tasks[itemIdx] = TaskRecord(ts, item_min_delivery_times[itemIdx])
                if rtlola_monitor:
                    rtlola_monitor.send_event(ts, -1, itemIdx, -1, -1, -1, 'create')
                created_window.append(ts)
                created_window = _prune_times(created_window, ts, latency_window_duration)
                itemIdx += 1
                random.shuffle(botsRandomOrder)
                for bot in botsRandomOrder:
                    if (
                        bot.getLocation() == space.getSource()
                        and bot.isFree()
                        and bot.isHealthy()
                        and not bot.isRescuing()
                        and not bot.rescueReserved
                        and not bot.hasOtherTasks()
                    ):
                        it = space.getMoreImportantItem(room=space.getSource())
                        if it is not None:
                            bot.loadItem(it, clock.getTime())
                            break
            elif event.startswith('move-'):
                idx = int(event.split('-')[1])
                bot = bots[idx]

                was_healthy = bot.isHealthy()
                delivered_item = bot.move(ts)
                if was_healthy and not bot.isHealthy():
                    failed_count += 1
                    failure_window.append(ts)
                    failure_window = _prune_times(failure_window, ts, latency_window_duration)
                    cfg.record_monitor_event(ts, 'agent_failed')

                if delivered_item is not None:
                    delivered_window.append(ts)
                    delivered_window = _prune_times(delivered_window, ts, latency_window_duration)
                    item_id = delivered_item.getIdx()
                    min_delivery_time = item_min_delivery_times.pop(item_id)
                    delivery_latency = ts - item_create_times.pop(item_id)
                    relative_latency = max(0.0, delivery_latency - min_delivery_time)
                    deliveries.append((delivery_latency, relative_latency))
                    if collect_tasks:
                        tasks[item_id].outcome = 'deliver'
                        tasks[item_id].ended_at = ts
                    if delivery_latency > 0:
                        latency_window.append((ts, relative_latency))
                        latency_window = [(t, lat) for t, lat in latency_window if ts - t <= latency_window_duration]
                    if rtlola_monitor:
                        rtlola_monitor.send_event(
                            ts, -1, item_id, -1, -1, delivered_item.getTarget().getIdx(), 'deliver',
                            minimum_delivery_time=min_delivery_time,
                        )
            elif event.startswith('recovery-'):
                idx = int(event.split('-')[1]); bots[idx].recovery(ts)
                recovered_count += 1
                cfg.record_monitor_event(ts, 'agent_recovered')
            elif event.startswith('central-request-'):
                request_id = int(event.split('-')[2]); space.processCentralRequest(request_id, ts)
            elif event.startswith('central-decision-'):
                request_id = int(event.split('-')[2]); space.processCentralDecision(request_id, ts)
            elif event.startswith('central-command-'):
                request_id = int(event.split('-')[2]); space.processCentralCommand(request_id, ts)
            elif event.startswith('peer-rescue-'):
                rescue_id = int(event.split('-')[2]); space.processPeerRescue(rescue_id, ts)
            elif event.startswith('rescue-verification-'):
                idx = int(event.split('-')[2]); bots[idx].completeRescueVerification(ts)
            elif event.startswith('fd-inspection-'):
                if cfg.current_architecture == 'decentralized':
                    patroller = space.selectFDPatroller()
                    if patroller is not None:
                        patroller.beginFDInspection(ts)
                clock.scheduleEvent(
                    event,
                    [inspection_interval],
                    ['_'],
                    ['deterministic'],
                )
            elif event.startswith('fd-local-search-'):
                idx = int(event.rsplit('-', 1)[1])
                if cfg.current_architecture == 'decentralized':
                    bots[idx].beginFDLocalSearch(ts, force=True)
                clock.scheduleEvent(
                    event,
                    [local_search_interval],
                    ['_'],
                    ['deterministic'],
                )
            elif event.startswith('expire-'):
                idx = int(event.split('-')[1])
                item = space.getItembyId(idx)
                if rtlola_monitor:
                    rtlola_monitor.send_event(ts, -1, idx, -1, -1, -1, 'expire')
                space.expireItem(item, ts)
                expired_count += 1
                if collect_tasks:
                    tasks[idx].outcome = 'expire'
                    tasks[idx].ended_at = ts
                item_create_times.pop(idx)
                item_min_delivery_times.pop(idx)
                expired_window.append(ts)
                expired_window = _prune_times(expired_window, ts, latency_window_duration)
            
            # Check for architecture adaptation.
            if rtlola_monitor and (ts - last_adaptation_check) >= adaptation_interval:
                last_adaptation_check = ts
                probe_samples = max(1, int(getattr(cfg, 'NETWORK_PROBE_SAMPLES_PER_CHECK', 5)))
                probe_loss_probability = max(0.0, min(1.0, float(cfg.COMM_FAIL_PROB)))
                for _ in range(probe_samples):
                    probe_event = (
                        'network_probe_lost'
                        if np.random.uniform() < probe_loss_probability
                        else 'network_probe_delivered'
                    )
                    rtlola_monitor.send_event(ts, -1, -1, -1, -1, -1, probe_event)
                
                # Start overhead measurement
                adaptation_start_time = time.time()
                adaptation_check_count += 1
                
                # Prefer the live RTLola metric, with the Python window as a safe fallback.
                rtlola_query_start = time.time()
                monitor_metrics = rtlola_monitor.snapshot(ts)
                rtlola_latency, rtlola_metric = _get_rtlola_latency(monitor_metrics)
                python_latency = sum(lat for _, lat in latency_window) / len(latency_window) if latency_window else None
                if rtlola_latency is not None:
                    raw_latency = rtlola_latency
                    latency_source = f'rtlola:{rtlola_metric}'
                else:
                    raw_latency = python_latency
                    latency_source = 'python_window' if python_latency is not None else 'none'
                rtlola_query_time = time.time() - rtlola_query_start

                runtime_metrics, created_window, delivered_window, expired_window, failure_window = _runtime_adaptation_metrics(
                    cfg,
                    space,
                    ts,
                    created_window,
                    delivered_window,
                    expired_window,
                    failure_window,
                    latency_window_duration,
                )
                runtime_metrics = _apply_rtlola_context_metrics(
                    cfg, runtime_metrics, monitor_metrics,
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
                score_details = {'policy': adaptation_policy}
                switch_reason = 'no_decision'
                threshold_context = {
                    'low': None,
                    'high': None,
                    'mode': 'contextual-bandit' if bandit_policy is not None else 'legacy',
                    'history_size': len(adaptation_latency_history),
                }
                bandit_context = {}
                bandit_update_details = {}
                bandit_reward = None
                reward_details = {}
                bandit_feedback_elapsed = None
                bandit_feedback_ready = False

                if bandit_policy is not None:
                    from .contextual_bandit import build_context, context_reward

                    bandit_context = build_context(cfg, runtime_metrics, effective_latency, current_arch)
                    decision_due = bandit_pending_action is None

                    if bandit_pending_action is not None and bandit_pending_context is not None:
                        bandit_feedback_elapsed = max(0.0, ts - float(bandit_pending_started_at or ts))
                        if bandit_feedback_elapsed >= bandit_feedback_window:
                            bandit_reward, reward_details = context_reward(
                                cfg,
                                bandit_context,
                            )
                            if bandit_reward is not None:
                                bandit_update_details = bandit_policy.update(
                                    bandit_pending_action,
                                    bandit_pending_context,
                                    bandit_reward,
                                ) or {}
                                bandit_pending_action = None
                                bandit_pending_context = None
                                bandit_pending_started_at = None
                                decision_due = True
                                bandit_feedback_ready = True
                            else:
                                switch_reason = 'waiting_terminal_outcomes'
                        else:
                            switch_reason = 'waiting_feedback_window'

                    if decision_due:
                        decision = bandit_policy.select(bandit_context, current_arch)
                        candidate_arch = decision['candidate_architecture']
                        best_arch = candidate_arch
                        scores = decision.get('scores', {})
                        switch_reason = decision.get('reason', 'bandit')
                        selected_value = scores.get(best_arch)
                        current_value = scores.get(current_arch)
                        score_details = {
                            'policy': 'contextual-bandit',
                            'state': 'online_learning',
                            'score': selected_value,
                            'selected_value': selected_value,
                            'current_value': current_value,
                            'greedy_architecture': decision.get('greedy_architecture'),
                            'estimated_values': decision.get('estimated_values', {}),
                            'confidence_bounds': decision.get('confidence_bounds', {}),
                            'selection_switch_cost': decision.get('selection_switch_cost'),
                            'epsilon': decision.get('epsilon'),
                            'explored': decision.get('explored'),
                            'initial_sampling': decision.get('initial_sampling', False),
                            'improvement_margin': decision.get('improvement_margin'),
                            'critical_override': decision.get('critical_override', False),
                            'fd_pressure': decision.get('fd_pressure', False),
                            'critical_reason': decision.get('critical_reason'),
                            'context_key': decision.get('context_key'),
                            'reward': bandit_reward,
                            'reward_details': reward_details,
                            'update_details': bandit_update_details,
                        }
                    else:
                        _, confidence_bounds, scores = bandit_policy.values(bandit_context)
                        selected_value = scores.get(current_arch)
                        score_details = {
                            'policy': 'contextual-bandit',
                            'state': 'waiting_feedback',
                            'score': selected_value,
                            'selected_value': selected_value,
                            'current_value': selected_value,
                            'estimated_values': {},
                            'confidence_bounds': confidence_bounds,
                            'selection_switch_cost': bandit_policy.selection_switch_cost,
                            'epsilon': bandit_policy.epsilon,
                            'explored': False,
                            'initial_sampling': False,
                            'improvement_margin': bandit_policy.improvement_margin,
                            'critical_override': False,
                            'fd_pressure': False,
                            'critical_reason': None,
                            'context_key': None,
                            'reward': bandit_reward,
                            'reward_details': reward_details,
                            'update_details': bandit_update_details,
                        }
                else:
                    from .architecture_scoring import get_latency_thresholds
                    threshold_context = get_latency_thresholds(cfg, adaptation_latency_history)

                    if adaptation_policy in {'latency-threshold', 'legacy', 'latency'}:
                        switch_reason = 'no_latency'
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
                        score_details['policy'] = 'hybrid-score'
                        best_arch = candidate_arch
                        switch_reason = score_details.get('state', 'hybrid_score')

                time_since_last_switch = ts - last_switch_time
                if best_arch != current_arch:
                    if time_since_last_switch < min_time_between_switches:
                        best_arch = current_arch
                        switch_reason = 'cooldown'
                    elif adaptation_policy not in {'latency-threshold', 'legacy', 'latency'}:
                        required_checks = (
                            1 if bandit_policy is not None
                            else max(1, int(getattr(cfg, 'ADAPTATION_PERSISTENCE_CHECKS', 2)))
                        )
                        bypass_persistence = (
                            score_details.get('critical_override', False)
                            and _cfg_bool(cfg, 'ADAPTATION_CRITICAL_BYPASS_PERSISTENCE', True)
                        ) or (
                            score_details.get('explored', False)
                            and _cfg_bool(cfg, 'BANDIT_EXPLORATION_BYPASS_PERSISTENCE', True)
                        ) or (
                            score_details.get('initial_sampling', False)
                            and _cfg_bool(cfg, 'BANDIT_INITIAL_SAMPLING_BYPASS_PERSISTENCE', True)
                        )
                        persisted, candidate_history = _candidate_persisted(
                            candidate_history,
                            candidate_arch,
                            required_checks,
                        )
                        if not (bypass_persistence or persisted):
                            best_arch = current_arch
                            switch_reason = f'waiting_persistence_{len(candidate_history)}/{required_checks}'
                else:
                    candidate_history = []

                switched_now = best_arch != current_arch
                if switched_now:
                    adaptation_switch_count += 1
                    switches.append((ts, best_arch))
                    last_switch_time = ts
                    cfg.set_architecture(best_arch)
                    candidate_history = []
                    with open(logfile, 'a') as f:
                        f.write(f'{ts},-2,-1,-1,-1,-1,switch_architecture_{best_arch}\n')

                if bandit_policy is not None and bandit_pending_action is None:
                    bandit_pending_action = best_arch
                    bandit_pending_context = bandit_context
                    bandit_pending_started_at = ts

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
                    'score_latency': score_details.get('components', {}).get('latency', bandit_context.get('latency_norm')),
                    'score_pending': score_details.get('components', {}).get('pending', bandit_context.get('pending_norm')),
                    'score_failure': score_details.get('components', {}).get('failure', bandit_context.get('failure_norm')),
                    'score_message_loss': score_details.get('components', {}).get('message_loss', bandit_context.get('message_loss_rate')),
                    'score_deadline_miss': bandit_context.get('deadline_miss_rate'),
                    'score_throughput': bandit_context.get('throughput_norm'),
                    'score_idle': bandit_context.get('idle_ratio'),
                    'pending_tasks': runtime_metrics.get('pending_tasks'),
                    'created_window': runtime_metrics.get('created_window'),
                    'delivered_window': runtime_metrics.get('delivered_window'),
                    'expired_window': runtime_metrics.get('expired_window'),
                    'terminal_tasks_window': runtime_metrics.get('terminal_tasks_window'),
                    'completion_available': runtime_metrics.get('completion_available'),
                    'completion_rate': runtime_metrics.get('completion_rate'),
                    'pending_ratio': runtime_metrics.get('pending_ratio'),
                    'failures_window': runtime_metrics.get('failures_window'),
                    'failure_rate': runtime_metrics.get('failure_rate'),
                    'messages_sent': runtime_metrics.get('messages_sent'),
                    'messages_lost': runtime_metrics.get('messages_lost'),
                    'message_loss_rate': runtime_metrics.get('message_loss_rate'),
                    'network_probe_count': runtime_metrics.get('network_probe_count'),
                    'network_probe_losses': runtime_metrics.get('network_probe_losses'),
                    'network_probe_loss_rate': runtime_metrics.get('network_probe_loss_rate'),
                    'deadline_miss_rate': runtime_metrics.get('deadline_miss_rate'),
                    'throughput_rate': runtime_metrics.get('throughput_rate'),
                    'throughput_norm': runtime_metrics.get('throughput_norm'),
                    'idle_agents': runtime_metrics.get('idle_agents'),
                    'idle_ratio': runtime_metrics.get('idle_ratio'),
                    'suspicion_evidence': runtime_metrics.get('suspicion_evidence'),
                    'suspicious_signals_window': runtime_metrics.get('suspicious_signals_window'),
                    'rescue_requests': runtime_metrics.get('rescue_requests'),
                    'suspicion_rate': runtime_metrics.get('suspicion_rate'),
                    'coordinator_outages': runtime_metrics.get('coordinator_outages'),
                    'coordinator_outage_rate': runtime_metrics.get('coordinator_outage_rate'),
                    'adaptation_policy': score_details.get('policy'),
                    'bandit_reward': score_details.get('reward'),
                    'bandit_feedback_window_s': bandit_feedback_window,
                    'bandit_feedback_elapsed_s': bandit_feedback_elapsed,
                    'bandit_feedback_ready': bandit_feedback_ready,
                    'bandit_pending_action': bandit_pending_action,
                    'bandit_reward_version': score_details.get('reward_details', {}).get('reward_version'),
                    'bandit_reward_ready': score_details.get('reward_details', {}).get('reward_ready'),
                    'bandit_reward_mode': score_details.get('reward_details', {}).get('reward_mode'),
                    'bandit_completion_target': score_details.get('reward_details', {}).get('completion_target'),
                    'bandit_completion_rate': score_details.get('reward_details', {}).get('completion_rate'),
                    'bandit_completion_deficit': score_details.get('reward_details', {}).get('completion_deficit'),
                    'bandit_terminal_tasks_window': score_details.get('reward_details', {}).get('terminal_tasks_window'),
                    'bandit_badness': score_details.get('reward_details', {}).get('badness'),
                    'bandit_throughput_bonus': score_details.get('reward_details', {}).get('throughput_bonus'),
                    'bandit_switch_penalty': score_details.get('reward_details', {}).get('switch_penalty'),
                    'bandit_selection_switch_cost': score_details.get('selection_switch_cost'),
                    'bandit_reward_latency': score_details.get('reward_details', {}).get('reward_latency'),
                    'bandit_reward_pending': score_details.get('reward_details', {}).get('reward_pending'),
                    'bandit_reward_failure': score_details.get('reward_details', {}).get('reward_failure'),
                    'bandit_reward_message_loss': score_details.get('reward_details', {}).get('reward_message_loss'),
                    'bandit_reward_deadline_miss': score_details.get('reward_details', {}).get('reward_deadline_miss'),
                    'bandit_reward_throughput_shortfall': score_details.get('reward_details', {}).get('reward_throughput_shortfall'),
                    'bandit_reward_idle_when_pending': score_details.get('reward_details', {}).get('reward_idle_when_pending'),
                    'bandit_updated_action': score_details.get('update_details', {}).get('updated_action'),
                    'bandit_prediction_before_update': score_details.get('update_details', {}).get('prediction_before_update'),
                    'bandit_prediction_error': score_details.get('update_details', {}).get('prediction_error'),
                    'bandit_confidence_before_update': score_details.get('update_details', {}).get('confidence_before_update'),
                    'bandit_updates_for_action': score_details.get('update_details', {}).get('updates_for_action'),
                    'bandit_epsilon': score_details.get('epsilon'),
                    'bandit_explored': score_details.get('explored'),
                    'bandit_initial_sampling': score_details.get('initial_sampling'),
                    'bandit_improvement_margin': score_details.get('improvement_margin'),
                    'bandit_current_value': score_details.get('current_value'),
                    'bandit_selected_value': score_details.get('selected_value'),
                    'bandit_value_ce': score_details.get('estimated_values', {}).get('centralized-impprox'),
                    'bandit_value_sd': score_details.get('estimated_values', {}).get('semi-decentralized'),
                    'bandit_value_fd': score_details.get('estimated_values', {}).get('decentralized'),
                    'bandit_confidence_ce': score_details.get('confidence_bounds', {}).get('centralized-impprox'),
                    'bandit_confidence_sd': score_details.get('confidence_bounds', {}).get('semi-decentralized'),
                    'bandit_confidence_fd': score_details.get('confidence_bounds', {}).get('decentralized'),
                    'bandit_greedy_architecture': score_details.get('greedy_architecture'),
                    'bandit_critical_reason': score_details.get('critical_reason'),
                    'bandit_context_key': score_details.get('context_key'),
                    'bandit_regime': score_details.get('regime'),
                    'context_latency_norm': bandit_context.get('latency_norm'),
                    'context_latency_missing': bandit_context.get('latency_missing'),
                    'context_completion_rate': bandit_context.get('completion_rate'),
                    'context_terminal_tasks_window': bandit_context.get('terminal_tasks_window'),
                    'context_arrival_rate_norm': bandit_context.get('arrival_rate_norm'),
                    'context_failure_norm': bandit_context.get('failure_norm'),
                    'context_network_probe_loss_rate': bandit_context.get('network_probe_loss_rate'),
                    'context_suspicion_norm': bandit_context.get('suspicion_norm'),
                    'completion_source': runtime_metrics.get('completion_source'),
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
    trace_rows = _sort_events_csv_by_time(logfile)
    
    # Log adaptation overhead statistics
    log_overhead_statistics(
        adaptation_check_count,
        adaptation_switch_count,
        adaptation_overhead_total,
        adaptation_overhead_samples,
        wall_time,
        logfile
    )
    
    metrics = summarize_run(
        cfg.SIM_TIME, clock.getTime(), itemIdx, expired_count, failed_count, recovered_count,
        deliveries, switches, adaptation_overhead_samples,
    )
    metrics['trace_rows'] = trace_rows
    result = RunResult(logfile, wall_time, event_count, metrics, tasks)
    write_summary(result)
    print(os.path.basename(logfile), '--> Simulation time (wall):', wall_time, f'({event_count} events)')
    return result

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'config.json'
    run(path)
