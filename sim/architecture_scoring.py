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
