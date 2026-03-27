import csv
import json
import math
import os
import random
import time
from collections import deque

from .env_maps import topologyName_dict


DEFAULTS = {
    "RESULTS_DIR": "results",
    "SIM_TIME": 180,
    "TOPOLOGY_NAME": "mesh9",
    "N_ROOMS": 9,
    "N_ANTS": 12,
    "INITIAL_MALES": 4,
    "COLONY_STRATEGY": "balanced",
    "RESOURCE_SPAWNING_TIME": 20,
    "MEAL_RESTORE": 38,
    "DRINK_RESTORE": 42,
    "MICRO_NAPS_PER_DAY": 120,
    "MICRO_NAP_DURATION": 1,
    "MATING_PROBABILITY": 0.05,
    "BROOD_MIN": 1,
    "BROOD_MAX": 2,
    "N_REPETITIONS": 1,
    "FAIL_PROB": 0.0005,
    "MOVEMENT_TIME": 1,
    "SEED": None,
}

STRATEGY_FACTORS = {
    "balanced": {"mate": 1.0, "food": 1.0, "water": 1.0, "rest": 1.0},
    "brood-focus": {"mate": 1.5, "food": 0.95, "water": 0.95, "rest": 0.9},
    "forager": {"mate": 0.8, "food": 1.2, "water": 1.05, "rest": 0.95},
    "hydration-first": {"mate": 0.9, "food": 0.95, "water": 1.35, "rest": 1.0},
    "rest-guarded": {"mate": 0.9, "food": 1.0, "water": 1.0, "rest": 1.2},
    "expansion": {"mate": 1.25, "food": 1.0, "water": 1.0, "rest": 0.95},
    "adaptive-colony": {"mate": 1.0, "food": 1.0, "water": 1.0, "rest": 1.0},
}


def _resolve_topology_name(config):
    name = config["TOPOLOGY_NAME"]
    if name in topologyName_dict:
        return name
    if name in {"mesh", "ring", "tree"}:
        candidate = f"{name}{config['N_ROOMS']}"
        if candidate in topologyName_dict:
            return candidate
    raise ValueError(f"Unsupported topology: {name}")


def _merge_config(payload):
    config = {**DEFAULTS, **(payload or {})}
    config["SIM_TIME"] = int(config["SIM_TIME"])
    config["N_ROOMS"] = int(config["N_ROOMS"])
    config["N_ANTS"] = int(config["N_ANTS"])
    config["INITIAL_MALES"] = max(0, min(int(config["INITIAL_MALES"]), config["N_ANTS"]))
    config["MICRO_NAPS_PER_DAY"] = max(1, int(config["MICRO_NAPS_PER_DAY"]))
    config["MICRO_NAP_DURATION"] = max(1, int(config["MICRO_NAP_DURATION"]))
    config["BROOD_MIN"] = max(1, int(config["BROOD_MIN"]))
    config["BROOD_MAX"] = max(config["BROOD_MIN"], int(config["BROOD_MAX"]))
    config["MATING_PROBABILITY"] = float(config["MATING_PROBABILITY"])
    config["FAIL_PROB"] = float(config["FAIL_PROB"])
    config["RESOURCE_SPAWNING_TIME"] = max(1, int(config["RESOURCE_SPAWNING_TIME"]))
    config["MEAL_RESTORE"] = float(config["MEAL_RESTORE"])
    config["DRINK_RESTORE"] = float(config["DRINK_RESTORE"])
    config["MOVEMENT_TIME"] = max(1, int(config["MOVEMENT_TIME"]))
    config["TOPOLOGY_NAME"] = _resolve_topology_name(config)
    return config


def _special_chambers(room_count):
    indices = list(range(room_count))
    return {
        "nest": 0,
        "nursery": indices[min(room_count - 1, max(1, room_count // 2))],
        "food": sorted({indices[min(room_count - 1, 1)], indices[min(room_count - 1, max(1, room_count // 3))]}),
        "water": sorted({indices[min(room_count - 1, 2)], indices[min(room_count - 1, max(1, (room_count * 2) // 3))]}),
        "rest": sorted({indices[max(0, room_count - 1)], indices[max(0, room_count - 2)]}),
    }


def _next_step(topology, start, destination):
    if start == destination:
        return start
    visited = {start}
    queue = deque([(start, [])])
    while queue:
        node, path = queue.popleft()
        for neighbor in topology[node]:
            if neighbor in visited:
                continue
            new_path = path + [neighbor]
            if neighbor == destination:
                return new_path[0]
            visited.add(neighbor)
            queue.append((neighbor, new_path))
    return start


def _pick_destination(current, candidates, topology):
    best = current
    best_distance = math.inf
    for candidate in candidates:
        if candidate == current:
            return candidate
        visited = {current}
        queue = deque([(current, 0)])
        while queue:
            node, distance = queue.popleft()
            if node == candidate:
                if distance < best_distance:
                    best = candidate
                    best_distance = distance
                break
            for neighbor in topology[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, distance + 1))
    return best


def _create_ant(ant_id, sex, birth_time, chamber, generation, rng, mother_id=None, father_id=None):
    return {
        "id": ant_id,
        "sex": sex,
        "birthTime": birth_time,
        "generation": generation,
        "motherId": mother_id,
        "fatherId": father_id,
        "chamber": chamber,
        "destination": chamber,
        "alive": True,
        "deathTime": None,
        "deathCause": None,
        "maturityAge": rng.randint(20, 60),
        "maxAge": rng.randint(900, 2200),
        "hunger": rng.uniform(72, 96),
        "thirst": rng.uniform(70, 96),
        "energy": rng.uniform(74, 97),
        "children": [],
        "mates": [],
        "microNaps": 0,
        "meals": 0,
        "drinks": 0,
        "moves": 0,
        "state": "active",
        "sleepUntil": None,
        "nextNapTime": birth_time + max(1, int(1440 / DEFAULTS["MICRO_NAPS_PER_DAY"])) + rng.randint(0, 2),
        "lastMateTime": -999,
        "visitedChambers": [chamber],
    }


def _log_event(writer, sim_time, ant, event, details="", partner_id=-1, child_id=-1, destination=None):
    writer.writerow(
        {
            "simTime": sim_time,
            "antId": ant["id"],
            "sex": ant["sex"],
            "partnerId": partner_id,
            "childId": child_id,
            "position": ant["chamber"],
            "destination": ant["destination"] if destination is None else destination,
            "event": event,
            "hunger": round(ant["hunger"], 2),
            "thirst": round(ant["thirst"], 2),
            "energy": round(ant["energy"], 2),
            "generation": ant["generation"],
            "details": details,
        }
    )


def run(payload=None, run_idx=0):
    config = _merge_config(payload)
    topology = topologyName_dict[config["TOPOLOGY_NAME"]]
    if config["N_ROOMS"] != len(topology):
        raise ValueError("N_ROOMS mismatch with selected topology")

    rng_seed = config["SEED"] if config["SEED"] is not None else int(time.time() * 1000) + run_idx
    rng = random.Random(rng_seed)
    results_dir = config["RESULTS_DIR"]
    os.makedirs(results_dir, exist_ok=True)
    run_stamp = f"{int(time.time() * 1000)}_{run_idx + 1}"
    logfile = os.path.join(results_dir, f"anthill_log_{run_stamp}.csv")
    lineage_file = os.path.join(results_dir, f"anthill_lineage_{run_stamp}.json")
    chambers = _special_chambers(config["N_ROOMS"])
    strategy = STRATEGY_FACTORS.get(config["COLONY_STRATEGY"], STRATEGY_FACTORS["balanced"]).copy()

    ant_counter = 0
    ants = {}
    births = 0
    resource_tick = 0

    def spawn_ant(sex, birth_time, chamber, generation, mother_id=None, father_id=None):
        nonlocal ant_counter, births
        ant = _create_ant(ant_counter, sex, birth_time, chamber, generation, rng, mother_id, father_id)
        ant["nextNapTime"] = birth_time + max(1, int(1440 / config["MICRO_NAPS_PER_DAY"])) + rng.randint(0, 2)
        ants[ant_counter] = ant
        ant_counter += 1
        births += 1
        return ant

    for idx in range(config["N_ANTS"]):
        sex = "M" if idx < config["INITIAL_MALES"] else "F"
        chamber = chambers["nest"] if idx < 4 else rng.choice(list(topology.keys()))
        spawn_ant(sex, 0, chamber, 0)

    start_wall = time.time()
    event_count = 0
    fieldnames = [
        "simTime",
        "antId",
        "sex",
        "partnerId",
        "childId",
        "position",
        "destination",
        "event",
        "hunger",
        "thirst",
        "energy",
        "generation",
        "details",
    ]

    with open(logfile, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for ant in ants.values():
            _log_event(writer, 0, ant, "birth", "initial colony")
            event_count += 1

        for sim_time in range(1, config["SIM_TIME"] + 1):
            if config["COLONY_STRATEGY"] == "adaptive-colony":
                living = [ant for ant in ants.values() if ant["alive"]]
                females = sum(1 for ant in living if ant["sex"] == "F")
                males = sum(1 for ant in living if ant["sex"] == "M")
                strategy["mate"] = 1.25 if females > males else 0.9
                strategy["rest"] = 1.15 if sum(1 for ant in living if ant["energy"] < 40) > max(1, len(living) // 4) else 0.95
                strategy["water"] = 1.2 if sum(1 for ant in living if ant["thirst"] < 35) > max(1, len(living) // 5) else 1.0

            if sim_time % config["RESOURCE_SPAWNING_TIME"] == 0:
                resource_tick += 1
                pseudo_ant = {
                    "id": -1,
                    "sex": "-",
                    "chamber": chambers["nest"],
                    "destination": chambers["nest"],
                    "hunger": 0,
                    "thirst": 0,
                    "energy": 0,
                    "generation": 0,
                }
                _log_event(writer, sim_time, pseudo_ant, "resource_spawn", f"pulse {resource_tick}")
                event_count += 1

            alive_females = [ant for ant in ants.values() if ant["alive"] and ant["sex"] == "F"]
            sleeping_female_ids = {ant["id"] for ant in alive_females if ant["state"] == "sleeping"}

            for ant_id in sorted(list(ants.keys())):
                ant = ants[ant_id]
                if not ant["alive"]:
                    continue

                age = sim_time - ant["birthTime"]
                ant["hunger"] -= rng.uniform(0.24, 0.52) / strategy["food"]
                ant["thirst"] -= rng.uniform(0.28, 0.58) / strategy["water"]
                ant["energy"] -= rng.uniform(0.12, 0.24) / strategy["rest"]

                if ant["state"] == "sleeping":
                    ant["energy"] = min(100, ant["energy"] + 4.5)
                    if sim_time >= ant["sleepUntil"]:
                        ant["state"] = "active"
                        ant["sleepUntil"] = None
                        _log_event(writer, sim_time, ant, "nap_end", "micro-nap complete")
                        event_count += 1
                    else:
                        continue

                if ant["hunger"] <= 0:
                    ant["alive"] = False
                    ant["deathTime"] = sim_time
                    ant["deathCause"] = "starvation"
                    ant["state"] = "dead"
                    _log_event(writer, sim_time, ant, "death", ant["deathCause"])
                    event_count += 1
                    continue

                if ant["thirst"] <= 0:
                    ant["alive"] = False
                    ant["deathTime"] = sim_time
                    ant["deathCause"] = "dehydration"
                    ant["state"] = "dead"
                    _log_event(writer, sim_time, ant, "death", ant["deathCause"])
                    event_count += 1
                    continue

                if age >= ant["maxAge"] or rng.random() < config["FAIL_PROB"] / 100:
                    ant["alive"] = False
                    ant["deathTime"] = sim_time
                    ant["deathCause"] = "natural causes" if age >= ant["maxAge"] else "colony hazard"
                    ant["state"] = "dead"
                    _log_event(writer, sim_time, ant, "death", ant["deathCause"])
                    event_count += 1
                    continue

                food_destination = _pick_destination(ant["chamber"], chambers["food"], topology)
                water_destination = _pick_destination(ant["chamber"], chambers["water"], topology)
                rest_destination = _pick_destination(ant["chamber"], chambers["rest"], topology)
                nursery = chambers["nursery"]

                need_food = ant["hunger"] < 42
                need_water = ant["thirst"] < 38
                need_rest = sim_time >= ant["nextNapTime"] and ant["energy"] < 96

                female_sleep_ratio = len(sleeping_female_ids) / len(alive_females) if alive_females else 0
                can_sleep = ant["sex"] == "M" or female_sleep_ratio < 0.2 or ant["state"] == "sleeping"

                if need_food:
                    ant["destination"] = food_destination
                    if ant["chamber"] == ant["destination"]:
                        ant["hunger"] = min(100, ant["hunger"] + config["MEAL_RESTORE"])
                        ant["meals"] += 1
                        _log_event(writer, sim_time, ant, "eat", "refuel in food chamber")
                        event_count += 1
                        continue
                elif need_water:
                    ant["destination"] = water_destination
                    if ant["chamber"] == ant["destination"]:
                        ant["thirst"] = min(100, ant["thirst"] + config["DRINK_RESTORE"])
                        ant["drinks"] += 1
                        _log_event(writer, sim_time, ant, "drink", "hydrate in water chamber")
                        event_count += 1
                        continue
                elif need_rest and can_sleep:
                    ant["destination"] = rest_destination
                    if ant["chamber"] == ant["destination"]:
                        ant["state"] = "sleeping"
                        ant["sleepUntil"] = sim_time + config["MICRO_NAP_DURATION"]
                        ant["microNaps"] += 1
                        ant["nextNapTime"] = sim_time + max(1, int(1440 / config["MICRO_NAPS_PER_DAY"])) + rng.randint(0, 2)
                        if ant["sex"] == "F":
                            sleeping_female_ids.add(ant["id"])
                        _log_event(writer, sim_time, ant, "nap_start", "one-minute micro-nap")
                        event_count += 1
                        continue
                elif age >= ant["maturityAge"] and sim_time - ant["lastMateTime"] > 15:
                    candidates = []
                    for other in ants.values():
                        if not other["alive"] or other["id"] == ant["id"]:
                            continue
                        if other["sex"] == ant["sex"] or other["chamber"] != ant["chamber"]:
                            continue
                        if sim_time - other["lastMateTime"] <= 15:
                            continue
                        if other["id"] in {ant["motherId"], ant["fatherId"]}:
                            continue
                        if ant["id"] in {other["motherId"], other["fatherId"]}:
                            continue
                        if sim_time - other["birthTime"] < other["maturityAge"]:
                            continue
                        candidates.append(other)

                    mating_roll = config["MATING_PROBABILITY"] * strategy["mate"]
                    if ant["chamber"] != nursery and rng.random() < 0.7:
                        ant["destination"] = nursery
                    elif candidates and rng.random() < mating_roll:
                        partner = rng.choice(candidates)
                        ant["lastMateTime"] = sim_time
                        partner["lastMateTime"] = sim_time
                        ant["mates"].append({"partnerId": partner["id"], "time": sim_time})
                        partner["mates"].append({"partnerId": ant["id"], "time": sim_time})
                        _log_event(writer, sim_time, ant, "mate", "breeding event", partner_id=partner["id"])
                        event_count += 1

                        brood_size = rng.randint(config["BROOD_MIN"], config["BROOD_MAX"])
                        mother_id = ant["id"] if ant["sex"] == "F" else partner["id"]
                        father_id = partner["id"] if ant["sex"] == "F" else ant["id"]
                        parent_generation = max(ant["generation"], partner["generation"])

                        for _ in range(brood_size):
                            sex = "F" if rng.random() < 0.5 else "M"
                            child = spawn_ant(sex, sim_time, nursery, parent_generation + 1, mother_id, father_id)
                            ants[mother_id]["children"].append(child["id"])
                            ants[father_id]["children"].append(child["id"])
                            _log_event(writer, sim_time, child, "birth", "bred in nursery", partner_id=father_id, child_id=child["id"])
                            event_count += 1
                        continue

                if ant["destination"] == ant["chamber"]:
                    if rng.random() < 0.22:
                        ant["destination"] = rng.choice(topology[ant["chamber"]])
                    else:
                        ant["destination"] = ant["chamber"]

                if ant["destination"] != ant["chamber"]:
                    next_chamber = _next_step(topology, ant["chamber"], ant["destination"])
                    ant["chamber"] = next_chamber
                    ant["moves"] += 1
                    ant["visitedChambers"].append(next_chamber)
                    _log_event(writer, sim_time, ant, "move", "crawl", destination=ant["destination"])
                    event_count += 1

    colony = {
        "strategy": config["COLONY_STRATEGY"],
        "topology": config["TOPOLOGY_NAME"],
        "specialChambers": chambers,
        "totalBirths": births,
        "finalPopulation": sum(1 for ant in ants.values() if ant["alive"]),
    }

    serialized_ants = {}
    for ant in ants.values():
        serialized_ants[str(ant["id"])] = {
            "id": ant["id"],
            "sex": ant["sex"],
            "generation": ant["generation"],
            "birthTime": ant["birthTime"],
            "motherId": ant["motherId"],
            "fatherId": ant["fatherId"],
            "alive": ant["alive"],
            "deathTime": ant["deathTime"],
            "deathCause": ant["deathCause"],
            "currentChamber": ant["chamber"],
            "children": ant["children"],
            "mates": ant["mates"],
            "microNaps": ant["microNaps"],
            "meals": ant["meals"],
            "drinks": ant["drinks"],
            "moves": ant["moves"],
            "visitedChambers": sorted(set(ant["visitedChambers"])),
            "lastKnownNeeds": {
                "hunger": round(ant["hunger"], 2),
                "thirst": round(ant["thirst"], 2),
                "energy": round(ant["energy"], 2),
            },
            "maturityAge": ant["maturityAge"],
            "maxAge": ant["maxAge"],
            "state": ant["state"],
        }

    with open(lineage_file, "w") as handle:
        json.dump({"colony": colony, "ants": serialized_ants}, handle, indent=2)

    return {
        "logfile": logfile,
        "lineage_file": lineage_file,
        "wall_time": time.time() - start_wall,
        "event_count": event_count,
        "run_stamp": run_stamp,
    }
