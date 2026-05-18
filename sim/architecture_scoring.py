"""
Architecture Scoring Module for Dynamic Adaptation

Evaluates architectures based on system conditions (Load, Security, Reliability)
derived from the "Self-Adaptive Coordination of Robot Teams via Dynamic Architecture Selection" paper
applied to the Ghent University Hospital topology.
"""

def _cfg_float(cfg, name: str, default: float) -> float:
    try:
        return float(getattr(cfg, name, default))
    except (TypeError, ValueError):
        return default


def select_best_architecture(cfg, latency: float = None) -> tuple:
    green_threshold = _cfg_float(cfg, 'LATENCY_THRESHOLD_LOW', 10.0)
    yellow_threshold = _cfg_float(cfg, 'LATENCY_THRESHOLD_HIGH', 40.0)

    if yellow_threshold < green_threshold:
        yellow_threshold = green_threshold
    
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
    return best_arch, scores
