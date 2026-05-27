"""
Architecture Scoring Module for Dynamic Adaptation.

The selector can use either fixed latency thresholds or adaptive thresholds
estimated from recent runtime latency observations.
"""

from math import isfinite


def _cfg_float(cfg, name: str, default: float) -> float:
    try:
        return float(getattr(cfg, name, default))
    except (TypeError, ValueError):
        return default


def _cfg_int(cfg, name: str, default: int) -> int:
    try:
        return int(getattr(cfg, name, default))
    except (TypeError, ValueError):
        return default


def _cfg_bool(cfg, name: str, default: bool) -> bool:
    value = getattr(cfg, name, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)


def _median(values):
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _normalized_weights(cfg) -> dict:
    weights = {
        'latency': max(0.0, _cfg_float(cfg, 'ADAPTATION_WEIGHT_LATENCY', 0.65)),
        'pending': max(0.0, _cfg_float(cfg, 'ADAPTATION_WEIGHT_PENDING', 0.20)),
        'failure': max(0.0, _cfg_float(cfg, 'ADAPTATION_WEIGHT_FAILURE', 0.10)),
        'message_loss': max(0.0, _cfg_float(cfg, 'ADAPTATION_WEIGHT_MESSAGE_LOSS', 0.05)),
    }
    total = sum(weights.values())
    if total <= 0.0:
        return {'latency': 1.0, 'pending': 0.0, 'failure': 0.0, 'message_loss': 0.0}
    return {name: value / total for name, value in weights.items()}


def get_latency_thresholds(cfg, latency_history=None) -> dict:
    static_low = _cfg_float(cfg, 'LATENCY_THRESHOLD_LOW', 10.0)
    static_high = _cfg_float(cfg, 'LATENCY_THRESHOLD_HIGH', 40.0)
    if static_high < static_low:
        static_high = static_low

    context = {
        'low': static_low,
        'high': static_high,
        'mode': 'static',
        'history_size': 0,
    }

    if not _cfg_bool(cfg, 'ADAPTIVE_THRESHOLDS', True):
        return context

    history = []
    for value in latency_history or []:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            continue
        if isfinite(numeric_value) and numeric_value >= 0.0:
            history.append(numeric_value)
    window = max(1, _cfg_int(cfg, 'ADAPTIVE_THRESHOLD_WINDOW', 12))
    history = history[-window:]
    context['history_size'] = len(history)

    warmup = max(1, _cfg_int(cfg, 'ADAPTIVE_THRESHOLD_WARMUP', 4))
    if len(history) < warmup:
        context['mode'] = 'static-warmup'
        return context

    baseline = _median(history)
    abs_deviations = [abs(value - baseline) for value in history]
    robust_sigma = 1.4826 * _median(abs_deviations)
    min_spread = _cfg_float(cfg, 'ADAPTIVE_THRESHOLD_MIN_SPREAD', 5.0)
    spread = max(robust_sigma, min_spread)

    low_multiplier = _cfg_float(cfg, 'ADAPTIVE_THRESHOLD_LOW_MULTIPLIER', 0.5)
    high_multiplier = _cfg_float(cfg, 'ADAPTIVE_THRESHOLD_HIGH_MULTIPLIER', 2.0)
    low = baseline + low_multiplier * spread
    high = baseline + high_multiplier * spread

    if high <= low:
        high = low + spread

    context.update({
        'low': low,
        'high': high,
        'mode': 'adaptive',
        'baseline': baseline,
        'spread': spread,
    })
    return context


def _apply_hysteresis(cfg, selected_arch, current_arch, latency, thresholds):
    if not current_arch or selected_arch == current_arch:
        return selected_arch

    ratio = max(0.0, _cfg_float(cfg, 'ADAPTIVE_THRESHOLD_HYSTERESIS', 0.10))
    if ratio == 0.0:
        return selected_arch

    low = thresholds['low']
    high = thresholds['high']
    min_margin = _cfg_float(cfg, 'ADAPTIVE_THRESHOLD_MIN_MARGIN', 1.0)
    low_margin = max(min_margin, abs(low) * ratio)
    high_margin = max(min_margin, abs(high) * ratio)

    if current_arch == 'centralized-impprox':
        if selected_arch == 'semi-decentralized' and latency < low + low_margin:
            return current_arch
        if selected_arch == 'decentralized' and latency < high + high_margin:
            return current_arch
    elif current_arch == 'semi-decentralized':
        if selected_arch == 'centralized-impprox' and latency > low - low_margin:
            return current_arch
        if selected_arch == 'decentralized' and latency < high + high_margin:
            return current_arch
    elif current_arch == 'decentralized':
        if selected_arch == 'semi-decentralized' and latency > high - high_margin:
            return current_arch
        if selected_arch == 'centralized-impprox' and latency > low - low_margin:
            return current_arch

    return selected_arch


def select_best_architecture(
    cfg,
    latency: float = None,
    latency_history=None,
    current_architecture: str = None,
    thresholds: dict = None,
) -> tuple:
    threshold_context = thresholds or get_latency_thresholds(cfg, latency_history)
    green_threshold = threshold_context['low']
    yellow_threshold = threshold_context['high']
    
    scores = {
        'decentralized': 0.0,
        'semi-decentralized': 0.0,
        'centralized-impprox': 0.0
    }
    
    if latency is None:
        best_arch = 'centralized-impprox'
        scores['centralized-impprox'] = 100.0
        return best_arch, scores

    # Determine zone
    if latency < green_threshold:
        # Green Zone
        scores['centralized-impprox'] = 100.0
        scores['semi-decentralized'] = 60.0
        scores['decentralized'] = 20.0
    elif latency < yellow_threshold:
        # Yellow Zone
        scores['centralized-impprox'] = 40.0
        scores['semi-decentralized'] = 100.0
        scores['decentralized'] = 60.0
    else:
        # Red Zone
        scores['centralized-impprox'] = 10.0
        scores['semi-decentralized'] = 50.0
        scores['decentralized'] = 100.0
 
    best_arch = max(scores, key=scores.get)
    best_arch = _apply_hysteresis(
        cfg,
        best_arch,
        current_architecture,
        latency,
        threshold_context,
    )
    return best_arch, scores


def compute_performance_score(cfg, latency: float = None, metrics: dict = None, thresholds: dict = None) -> dict:
    """Return normalized DA score components and the stable/degraded/critical state."""
    metrics = metrics or {}
    thresholds = thresholds or get_latency_thresholds(cfg)
    weights = _normalized_weights(cfg)

    default_latency_ref = _cfg_float(cfg, 'LATENCY_THRESHOLD_HIGH', thresholds.get('high', 40.0))
    latency_ref = max(1e-9, _cfg_float(cfg, 'ADAPTATION_LATENCY_REF', default_latency_ref))
    pending_ref = max(1e-9, _cfg_float(cfg, 'ADAPTATION_PENDING_REF', 1.0))
    failure_ref = max(1e-9, _cfg_float(cfg, 'ADAPTATION_FAILURE_REF', 0.50))

    latency_norm = 0.0
    if latency is not None:
        try:
            numeric_latency = float(latency)
            if isfinite(numeric_latency) and numeric_latency >= 0.0:
                latency_norm = _clamp01(numeric_latency / latency_ref)
        except (TypeError, ValueError):
            latency_norm = 0.0

    pending_ratio = max(0.0, float(metrics.get('pending_ratio', 0.0) or 0.0))
    failure_rate = max(0.0, float(metrics.get('failure_rate', 0.0) or 0.0))
    message_loss_rate = max(0.0, float(metrics.get('message_loss_rate', 0.0) or 0.0))

    pending_norm = _clamp01(pending_ratio / pending_ref)
    failure_norm = _clamp01(failure_rate / failure_ref)
    message_loss_norm = _clamp01(message_loss_rate)

    score = (
        weights['latency'] * latency_norm
        + weights['pending'] * pending_norm
        + weights['failure'] * failure_norm
        + weights['message_loss'] * message_loss_norm
    )

    low = _cfg_float(cfg, 'ADAPTATION_SCORE_LOW', 0.35)
    high = _cfg_float(cfg, 'ADAPTATION_SCORE_HIGH', 0.65)
    if high < low:
        high = low

    pending_critical = _cfg_float(cfg, 'ADAPTATION_PENDING_CRITICAL_RATIO', 2.0)
    failure_critical = _cfg_float(cfg, 'ADAPTATION_FAILURE_CRITICAL_RATE', 1.25)
    message_critical = _cfg_float(cfg, 'ADAPTATION_MESSAGE_CRITICAL_LOSS', 0.60)
    critical_override = (
        pending_ratio >= pending_critical
        or failure_rate >= failure_critical
        or message_loss_rate >= message_critical
    )

    if critical_override or score >= high:
        state = 'critical'
    elif score >= low:
        state = 'degraded'
    else:
        state = 'stable'

    return {
        'score': score,
        'state': state,
        'critical_override': critical_override,
        'weights': weights,
        'components': {
            'latency': latency_norm,
            'pending': pending_norm,
            'failure': failure_norm,
            'message_loss': message_loss_norm,
        },
        'thresholds': {
            'score_low': low,
            'score_high': high,
            'latency_ref': latency_ref,
            'pending_ref': pending_ref,
            'failure_ref': failure_ref,
            'pending_critical': pending_critical,
            'failure_critical': failure_critical,
            'message_critical': message_critical,
        },
    }


def _apply_score_hysteresis(cfg, selected_arch, current_arch, score_details):
    if (
        not current_arch
        or selected_arch == current_arch
        or score_details.get('critical_override')
        or score_details.get('recovery_mode')
    ):
        return selected_arch

    margin = max(0.0, _cfg_float(cfg, 'ADAPTATION_SCORE_HYSTERESIS', 0.05))
    if margin == 0.0:
        return selected_arch

    score = score_details['score']
    low = score_details['thresholds']['score_low']
    high = score_details['thresholds']['score_high']

    if current_arch == 'centralized-impprox':
        if selected_arch == 'semi-decentralized' and score < low + margin:
            return current_arch
        if selected_arch == 'decentralized' and score < high + margin:
            return current_arch
    elif current_arch == 'semi-decentralized':
        if selected_arch == 'centralized-impprox' and score > low - margin:
            return current_arch
        if selected_arch == 'decentralized' and score < high + margin:
            return current_arch
    elif current_arch == 'decentralized':
        if selected_arch == 'semi-decentralized' and score > high - margin:
            return current_arch
        if selected_arch == 'centralized-impprox' and score > low - margin:
            return current_arch

    return selected_arch


def select_hybrid_architecture(
    cfg,
    latency: float = None,
    runtime_metrics: dict = None,
    latency_history=None,
    current_architecture: str = None,
    thresholds: dict = None,
) -> tuple:
    runtime_metrics = runtime_metrics or {}
    threshold_context = thresholds or get_latency_thresholds(cfg, latency_history)
    score_details = compute_performance_score(cfg, latency, runtime_metrics, threshold_context)
    malicious_ratio = 0.0
    try:
        malicious_ratio = float(getattr(cfg, 'N_MALICIOUS', 0)) / max(1, int(getattr(cfg, 'N_ROBOTS', 1)))
    except (TypeError, ValueError):
        malicious_ratio = 0.0

    recovery_mode = (
        _cfg_float(cfg, 'FAIL_PROB', 0.0) <= _cfg_float(cfg, 'ADAPTATION_RECOVERY_FAIL_PROB_THRESHOLD', 0.08)
        and _cfg_float(cfg, 'COMM_FAIL_PROB', 0.0) <= _cfg_float(cfg, 'ADAPTATION_RECOVERY_COMM_FAIL_THRESHOLD', 0.05)
        and malicious_ratio <= _cfg_float(cfg, 'ADAPTATION_RECOVERY_MALICIOUS_RATIO_THRESHOLD', 0.20)
    )
    score_details['recovery_mode'] = recovery_mode

    state = score_details['state']
    if recovery_mode:
        selected_arch = 'centralized-impprox'
        scores = {'centralized-impprox': 100.0, 'semi-decentralized': 55.0, 'decentralized': 15.0}
    elif state == 'stable':
        selected_arch = 'centralized-impprox'
        scores = {'centralized-impprox': 100.0, 'semi-decentralized': 60.0, 'decentralized': 20.0}
    elif state == 'degraded':
        selected_arch = 'semi-decentralized'
        scores = {'centralized-impprox': 40.0, 'semi-decentralized': 100.0, 'decentralized': 60.0}
    else:
        message_loss_rate = float(runtime_metrics.get('message_loss_rate', 0.0) or 0.0)
        configured_comm_loss = _cfg_float(cfg, 'COMM_FAIL_PROB', 0.0)
        failure_rate = float(runtime_metrics.get('failure_rate', 0.0) or 0.0)

        fd_pressure = (
            message_loss_rate >= _cfg_float(cfg, 'ADAPTATION_FD_MESSAGE_LOSS_THRESHOLD', 0.35)
            or configured_comm_loss >= _cfg_float(cfg, 'ADAPTATION_FD_COMM_FAIL_PROB_THRESHOLD', 0.35)
            or malicious_ratio >= _cfg_float(cfg, 'ADAPTATION_FD_MALICIOUS_RATIO_THRESHOLD', 0.50)
            or failure_rate >= _cfg_float(cfg, 'ADAPTATION_FD_FAILURE_RATE_THRESHOLD', 999.0)
        )
        selected_arch = 'decentralized' if fd_pressure else 'semi-decentralized'
        scores = {'centralized-impprox': 10.0, 'semi-decentralized': 90.0, 'decentralized': 100.0 if fd_pressure else 70.0}
        score_details['fd_pressure'] = fd_pressure

    selected_arch = _apply_score_hysteresis(cfg, selected_arch, current_architecture, score_details)
    score_details['selected_state'] = state
    return selected_arch, scores, score_details
