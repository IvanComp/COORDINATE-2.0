import json
import math
import os
import random
import threading
import time
from collections import deque

from sim.ant_simulator import STRATEGY_FACTORS, _next_step, _pick_destination, _resolve_topology_name, _special_chambers
from sim.env_maps import topologyName_dict


LIVE_DEFAULTS = {
    "TOPOLOGY_NAME": "mesh16",
    "N_ROOMS": 16,
    "N_ANTS": 24,
    "INITIAL_MALES": 8,
    "COLONY_STRATEGY": "balanced",
    "RESOURCE_SPAWNING_TIME": 180,
    "MEAL_RESTORE": 52,
    "DRINK_RESTORE": 58,
    "MICRO_NAPS_PER_DAY": 18,
    "MICRO_NAP_DURATION": 20,
    "MATING_PROBABILITY": 0.18,
    "BROOD_MIN": 1,
    "BROOD_MAX": 2,
    "FAIL_PROB": 0.015,
    "MOVEMENT_TIME": 1,
    "SIM_MINUTES_PER_TICK": 1,
    "LIVE_SECONDS_PER_TICK": 5,
    "HUNGER_DECAY_PER_MIN": 0.011,
    "THIRST_DECAY_PER_MIN": 0.013,
    "ENERGY_DECAY_PER_MIN": 0.02,
    "NAP_RECOVERY_PER_MIN": 0.95,
    "MATURE_AGE_MIN": 2880,
    "MATURE_AGE_MAX": 7200,
    "MAX_AGE_MIN": 43200,
    "MAX_AGE_MAX": 129600,
    "MATE_COOLDOWN_MINUTES": 1440,
    "SNAPSHOT_INTERVAL_SECONDS": 60,
    "MAX_RECENT_EVENTS": 180,
    "SEED": None,
}


class LiveColonyRunner:
    def __init__(self, results_dir):
        self.results_dir = results_dir
        self.snapshot_path = os.path.join(results_dir, "live_colony_snapshot.json")
        self.lock = threading.RLock()
        self.shutdown_event = threading.Event()
        self.state = None
        self.status = "stopped"
        self.rng = random.Random()
        self.last_snapshot_wall = 0.0
        self.thread = threading.Thread(target=self._loop, daemon=True, name="live-colony-runner")
        self._load_snapshot()
        self.thread.start()

    def _merge_config(self, payload=None):
        config = {**LIVE_DEFAULTS, **(payload or {})}
        config["N_ROOMS"] = int(config["N_ROOMS"])
        config["N_ANTS"] = int(config["N_ANTS"])
        config["INITIAL_MALES"] = max(0, min(int(config["INITIAL_MALES"]), config["N_ANTS"]))
        config["RESOURCE_SPAWNING_TIME"] = max(1, int(config["RESOURCE_SPAWNING_TIME"]))
        config["MICRO_NAPS_PER_DAY"] = max(1, int(config["MICRO_NAPS_PER_DAY"]))
        config["MICRO_NAP_DURATION"] = max(5, int(config["MICRO_NAP_DURATION"]))
        config["BROOD_MIN"] = max(1, int(config["BROOD_MIN"]))
        config["BROOD_MAX"] = max(config["BROOD_MIN"], int(config["BROOD_MAX"]))
        config["MATING_PROBABILITY"] = float(config["MATING_PROBABILITY"])
        config["FAIL_PROB"] = float(config["FAIL_PROB"])
        config["MOVEMENT_TIME"] = max(1, int(config["MOVEMENT_TIME"]))
        config["SIM_MINUTES_PER_TICK"] = max(1, int(config["SIM_MINUTES_PER_TICK"]))
        config["LIVE_SECONDS_PER_TICK"] = max(1, float(config["LIVE_SECONDS_PER_TICK"]))
        config["HUNGER_DECAY_PER_MIN"] = max(0.0001, float(config["HUNGER_DECAY_PER_MIN"]))
        config["THIRST_DECAY_PER_MIN"] = max(0.0001, float(config["THIRST_DECAY_PER_MIN"]))
        config["ENERGY_DECAY_PER_MIN"] = max(0.0001, float(config["ENERGY_DECAY_PER_MIN"]))
        config["NAP_RECOVERY_PER_MIN"] = max(0.1, float(config["NAP_RECOVERY_PER_MIN"]))
        config["MATURE_AGE_MIN"] = max(1440, int(config["MATURE_AGE_MIN"]))
        config["MATURE_AGE_MAX"] = max(config["MATURE_AGE_MIN"], int(config["MATURE_AGE_MAX"]))
        config["MAX_AGE_MIN"] = max(config["MATURE_AGE_MAX"] + 1440, int(config["MAX_AGE_MIN"]))
        config["MAX_AGE_MAX"] = max(config["MAX_AGE_MIN"], int(config["MAX_AGE_MAX"]))
        config["MATE_COOLDOWN_MINUTES"] = max(60, int(config["MATE_COOLDOWN_MINUTES"]))
        config["SNAPSHOT_INTERVAL_SECONDS"] = max(15, int(config["SNAPSHOT_INTERVAL_SECONDS"]))
        config["MAX_RECENT_EVENTS"] = max(20, int(config["MAX_RECENT_EVENTS"]))
        config["TOPOLOGY_NAME"] = _resolve_topology_name(config)
        return config

    def _create_ant(self, ant_id, sex, birth_time, chamber, generation, mother_id=None, father_id=None):
        config = self.state["config"]
        next_nap_gap = max(90, int(1440 / config["MICRO_NAPS_PER_DAY"]))
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
            "maturityAge": self.rng.randint(config["MATURE_AGE_MIN"], config["MATURE_AGE_MAX"]),
            "maxAge": self.rng.randint(config["MAX_AGE_MIN"], config["MAX_AGE_MAX"]),
            "hunger": self.rng.uniform(76, 98),
            "thirst": self.rng.uniform(76, 98),
            "energy": self.rng.uniform(82, 100),
            "children": [],
            "mates": [],
            "microNaps": 0,
            "meals": 0,
            "drinks": 0,
            "moves": 0,
            "state": "active",
            "sleepUntil": None,
            "nextNapTime": birth_time + next_nap_gap + self.rng.randint(0, 30),
            "lastMateTime": -999999,
            "visitedChambers": [chamber],
        }

    def _event_row(self, sim_time, ant, event, details="", partner_id=-1, child_id=-1, destination=None):
        return {
            "simTime": round(sim_time, 2),
            "antId": ant["id"],
            "sex": ant["sex"],
            "partnerId": partner_id,
            "childId": child_id,
            "position": ant["chamber"],
            "destination": ant["destination"] if destination is None else destination,
            "event": event,
            "hunger": round(float(ant.get("hunger", 0)), 2),
            "thirst": round(float(ant.get("thirst", 0)), 2),
            "energy": round(float(ant.get("energy", 0)), 2),
            "generation": ant.get("generation", 0),
            "details": details,
        }

    def _record_event(self, ant, event, details="", partner_id=-1, child_id=-1, destination=None):
        row = self._event_row(self.state["simTime"], ant, event, details, partner_id, child_id, destination)
        recent = self.state["recentEvents"]
        recent.append(row)
        if len(recent) > self.state["config"]["MAX_RECENT_EVENTS"]:
            del recent[: len(recent) - self.state["config"]["MAX_RECENT_EVENTS"]]

        self.state["eventCount"] += 1
        if event == "birth":
            self.state["totalBirths"] += 1
        elif event == "death":
            self.state["totalDeaths"] += 1
        elif event == "mate":
            self.state["totalMatings"] += 1
        elif event == "eat":
            self.state["totalMeals"] += 1
        elif event == "drink":
            self.state["totalDrinks"] += 1
        elif event == "nap_start":
            self.state["totalNaps"] += 1
        elif event == "move":
            self.state["totalMoves"] += 1

    def _spawn_ant(self, sex, birth_time, chamber, generation, mother_id=None, father_id=None):
        ant_id = self.state["antCounter"]
        ant = self._create_ant(ant_id, sex, birth_time, chamber, generation, mother_id, father_id)
        self.state["ants"][ant_id] = ant
        self.state["antCounter"] += 1
        return ant

    def _create_initial_state(self, payload=None):
        config = self._merge_config(payload)
        topology = topologyName_dict[config["TOPOLOGY_NAME"]]
        if len(topology) != config["N_ROOMS"]:
            raise ValueError("N_ROOMS mismatch with selected topology")

        seed = config["SEED"] if config["SEED"] is not None else int(time.time() * 1000)
        self.rng = random.Random(seed)

        self.state = {
            "config": config,
            "seed": seed,
            "topologyName": config["TOPOLOGY_NAME"],
            "specialChambers": _special_chambers(config["N_ROOMS"]),
            "simTime": 0,
            "resourceTick": 0,
            "ants": {},
            "antCounter": 0,
            "recentEvents": [],
            "eventCount": 0,
            "totalBirths": 0,
            "totalDeaths": 0,
            "totalMatings": 0,
            "totalMeals": 0,
            "totalDrinks": 0,
            "totalMoves": 0,
            "totalNaps": 0,
            "createdAt": time.time(),
            "updatedAt": time.time(),
        }

        nest = self.state["specialChambers"]["nest"]
        topology_keys = list(topology.keys())
        for idx in range(config["N_ANTS"]):
            sex = "M" if idx < config["INITIAL_MALES"] else "F"
            chamber = nest if idx < min(4, config["N_ANTS"]) else self.rng.choice(topology_keys)
            ant = self._spawn_ant(sex, 0, chamber, 0)
            self._record_event(ant, "birth", "live colony start")

        self.status = "running"
        self.last_snapshot_wall = time.time()

    def _serialize_ant(self, ant):
        return {
            "id": ant["id"],
            "sex": ant["sex"],
            "generation": ant["generation"],
            "birthTime": ant["birthTime"],
            "motherId": ant["motherId"],
            "fatherId": ant["fatherId"],
            "position": ant["chamber"],
            "destination": ant["destination"],
            "alive": ant["alive"],
            "deathTime": ant["deathTime"],
            "deathCause": ant["deathCause"],
            "hunger": round(ant["hunger"], 2),
            "thirst": round(ant["thirst"], 2),
            "energy": round(ant["energy"], 2),
            "children": ant["children"],
            "mates": ant["mates"],
            "microNaps": ant["microNaps"],
            "meals": ant["meals"],
            "drinks": ant["drinks"],
            "moves": ant["moves"],
            "visitedChambers": ant["visitedChambers"],
            "state": ant["state"],
        }

    def _summary(self):
        ants = list(self.state["ants"].values()) if self.state else []
        living = [ant for ant in ants if ant["alive"]]
        females = [ant for ant in living if ant["sex"] == "F"]
        awake_females = [ant for ant in females if ant["state"] != "sleeping"]
        return {
            "living": len(living),
            "sleeping": sum(1 for ant in living if ant["state"] == "sleeping"),
            "females": len(females),
            "males": sum(1 for ant in living if ant["sex"] == "M"),
            "awakeFemaleRatio": round((len(awake_females) / len(females)) * 100) if females else 100,
            "births": self.state["totalBirths"] if self.state else 0,
            "deaths": self.state["totalDeaths"] if self.state else 0,
            "matings": self.state["totalMatings"] if self.state else 0,
            "meals": self.state["totalMeals"] if self.state else 0,
            "drinks": self.state["totalDrinks"] if self.state else 0,
            "moves": self.state["totalMoves"] if self.state else 0,
            "naps": self.state["totalNaps"] if self.state else 0,
            "events": self.state["eventCount"] if self.state else 0,
        }

    def _snapshot_payload(self):
        ants = {str(ant_id): self._serialize_ant(ant) for ant_id, ant in self.state["ants"].items()}
        return {
            "status": self.status,
            "state": {
                **self.state,
                "ants": ants,
            },
        }

    def _save_snapshot(self):
        if not self.state:
            return
        os.makedirs(self.results_dir, exist_ok=True)
        with open(self.snapshot_path, "w") as handle:
            json.dump(self._snapshot_payload(), handle, indent=2)
        self.last_snapshot_wall = time.time()

    def _load_snapshot(self):
        if not os.path.exists(self.snapshot_path):
            return
        try:
            with open(self.snapshot_path, "r") as handle:
                data = json.load(handle)
            raw_state = data.get("state")
            if not raw_state:
                return
            raw_state["ants"] = {int(k): v for k, v in raw_state.get("ants", {}).items()}
            self.state = raw_state
            self.status = data.get("status", "paused")
            self.rng = random.Random(self.state.get("seed", int(time.time() * 1000)))
        except Exception:
            self.state = None
            self.status = "stopped"

    def _maybe_snapshot(self):
        if not self.state:
            return
        interval = self.state["config"]["SNAPSHOT_INTERVAL_SECONDS"]
        if (time.time() - self.last_snapshot_wall) >= interval:
            self._save_snapshot()

    def _step(self):
        if not self.state:
            return

        config = self.state["config"]
        topology = topologyName_dict[self.state["topologyName"]]
        chambers = self.state["specialChambers"]
        increment = config["SIM_MINUTES_PER_TICK"]
        self.state["simTime"] += increment
        sim_time = self.state["simTime"]
        strategy = STRATEGY_FACTORS.get(config["COLONY_STRATEGY"], STRATEGY_FACTORS["balanced"]).copy()

        living = [ant for ant in self.state["ants"].values() if ant["alive"]]
        if config["COLONY_STRATEGY"] == "adaptive-colony":
            females = sum(1 for ant in living if ant["sex"] == "F")
            males = sum(1 for ant in living if ant["sex"] == "M")
            strategy["mate"] = 1.2 if females > males else 0.85
            strategy["rest"] = 1.2 if sum(1 for ant in living if ant["energy"] < 30) > max(1, len(living) // 5) else 1.0
            strategy["water"] = 1.25 if sum(1 for ant in living if ant["thirst"] < 35) > max(1, len(living) // 6) else 1.0

        previous_resource_block = int((sim_time - increment) // config["RESOURCE_SPAWNING_TIME"])
        current_resource_block = int(sim_time // config["RESOURCE_SPAWNING_TIME"])
        if current_resource_block > previous_resource_block:
            self.state["resourceTick"] += 1
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
            self._record_event(pseudo_ant, "resource_spawn", f"pulse {self.state['resourceTick']}")

        alive_females = [ant for ant in self.state["ants"].values() if ant["alive"] and ant["sex"] == "F"]
        sleeping_female_ids = {ant["id"] for ant in alive_females if ant["state"] == "sleeping"}

        for ant_id in sorted(self.state["ants"].keys()):
            ant = self.state["ants"][ant_id]
            if not ant["alive"]:
                continue

            age = sim_time - ant["birthTime"]
            ant["hunger"] -= self.rng.uniform(config["HUNGER_DECAY_PER_MIN"] * 0.92, config["HUNGER_DECAY_PER_MIN"] * 1.08) * increment / strategy["food"]
            ant["thirst"] -= self.rng.uniform(config["THIRST_DECAY_PER_MIN"] * 0.92, config["THIRST_DECAY_PER_MIN"] * 1.08) * increment / strategy["water"]
            ant["energy"] -= self.rng.uniform(config["ENERGY_DECAY_PER_MIN"] * 0.9, config["ENERGY_DECAY_PER_MIN"] * 1.1) * increment / strategy["rest"]

            if ant["state"] == "sleeping":
                ant["energy"] = min(100, ant["energy"] + config["NAP_RECOVERY_PER_MIN"] * increment)
                if sim_time >= ant["sleepUntil"]:
                    ant["state"] = "active"
                    ant["sleepUntil"] = None
                    self._record_event(ant, "nap_end", "rest completed")
                else:
                    continue

            if ant["hunger"] <= 0:
                ant["alive"] = False
                ant["deathTime"] = sim_time
                ant["deathCause"] = "starvation"
                ant["state"] = "dead"
                self._record_event(ant, "death", ant["deathCause"])
                continue

            if ant["thirst"] <= 0:
                ant["alive"] = False
                ant["deathTime"] = sim_time
                ant["deathCause"] = "dehydration"
                ant["state"] = "dead"
                self._record_event(ant, "death", ant["deathCause"])
                continue

            hazard_roll = config["FAIL_PROB"] * (increment / 1440)
            if age >= ant["maxAge"] or self.rng.random() < hazard_roll:
                ant["alive"] = False
                ant["deathTime"] = sim_time
                ant["deathCause"] = "natural causes" if age >= ant["maxAge"] else "colony hazard"
                ant["state"] = "dead"
                self._record_event(ant, "death", ant["deathCause"])
                continue

            food_destination = _pick_destination(ant["chamber"], chambers["food"], topology)
            water_destination = _pick_destination(ant["chamber"], chambers["water"], topology)
            rest_destination = _pick_destination(ant["chamber"], chambers["rest"], topology)
            nursery = chambers["nursery"]

            need_food = ant["hunger"] < 45
            need_water = ant["thirst"] < 40
            need_rest = sim_time >= ant["nextNapTime"] and ant["energy"] < 90
            female_sleep_ratio = len(sleeping_female_ids) / len(alive_females) if alive_females else 0
            can_sleep = ant["sex"] == "M" or female_sleep_ratio < 0.35 or ant["state"] == "sleeping"

            if need_food:
                ant["destination"] = food_destination
                if ant["chamber"] == ant["destination"]:
                    ant["hunger"] = min(100, ant["hunger"] + config["MEAL_RESTORE"])
                    ant["meals"] += 1
                    self._record_event(ant, "eat", "feeds in the food chamber")
                    continue
            elif need_water:
                ant["destination"] = water_destination
                if ant["chamber"] == ant["destination"]:
                    ant["thirst"] = min(100, ant["thirst"] + config["DRINK_RESTORE"])
                    ant["drinks"] += 1
                    self._record_event(ant, "drink", "hydrates in the water chamber")
                    continue
            elif need_rest and can_sleep:
                ant["destination"] = rest_destination
                if ant["chamber"] == ant["destination"]:
                    ant["state"] = "sleeping"
                    ant["sleepUntil"] = sim_time + config["MICRO_NAP_DURATION"]
                    ant["microNaps"] += 1
                    ant["nextNapTime"] = sim_time + max(90, int(1440 / config["MICRO_NAPS_PER_DAY"])) + self.rng.randint(0, 30)
                    if ant["sex"] == "F":
                        sleeping_female_ids.add(ant["id"])
                    self._record_event(ant, "nap_start", "settles into a rest cycle")
                    continue
            elif age >= ant["maturityAge"] and sim_time - ant["lastMateTime"] > config["MATE_COOLDOWN_MINUTES"]:
                candidates = []
                for other in self.state["ants"].values():
                    if not other["alive"] or other["id"] == ant["id"]:
                        continue
                    if other["sex"] == ant["sex"] or other["chamber"] != ant["chamber"]:
                        continue
                    if sim_time - other["lastMateTime"] <= config["MATE_COOLDOWN_MINUTES"]:
                        continue
                    if other["id"] in {ant["motherId"], ant["fatherId"]}:
                        continue
                    if ant["id"] in {other["motherId"], other["fatherId"]}:
                        continue
                    if sim_time - other["birthTime"] < other["maturityAge"]:
                        continue
                    candidates.append(other)

                mating_roll = config["MATING_PROBABILITY"] * strategy["mate"] * (increment / 1440)
                if ant["chamber"] != nursery and self.rng.random() < 0.18:
                    ant["destination"] = nursery
                elif candidates and self.rng.random() < mating_roll:
                    partner = self.rng.choice(candidates)
                    ant["lastMateTime"] = sim_time
                    partner["lastMateTime"] = sim_time
                    ant["mates"].append({"partnerId": partner["id"], "time": sim_time})
                    partner["mates"].append({"partnerId": ant["id"], "time": sim_time})
                    self._record_event(ant, "mate", "colony breeding event", partner_id=partner["id"])

                    brood_size = self.rng.randint(config["BROOD_MIN"], config["BROOD_MAX"])
                    mother_id = ant["id"] if ant["sex"] == "F" else partner["id"]
                    father_id = partner["id"] if ant["sex"] == "F" else ant["id"]
                    parent_generation = max(ant["generation"], partner["generation"])
                    for _ in range(brood_size):
                        child_sex = "F" if self.rng.random() < 0.5 else "M"
                        child = self._spawn_ant(child_sex, sim_time, nursery, parent_generation + 1, mother_id, father_id)
                        self.state["ants"][mother_id]["children"].append(child["id"])
                        self.state["ants"][father_id]["children"].append(child["id"])
                        self._record_event(child, "birth", "born in the nursery", partner_id=father_id, child_id=child["id"])
                    continue

            if ant["destination"] == ant["chamber"]:
                if self.rng.random() < 0.08:
                    ant["destination"] = self.rng.choice(topology[ant["chamber"]])
                else:
                    ant["destination"] = ant["chamber"]

            if ant["destination"] != ant["chamber"]:
                next_chamber = _next_step(topology, ant["chamber"], ant["destination"])
                ant["chamber"] = next_chamber
                ant["moves"] += 1
                ant["visitedChambers"].append(next_chamber)
                self._record_event(ant, "move", "crawls through the colony", destination=ant["destination"])

        self.state["updatedAt"] = time.time()
        self._maybe_snapshot()

    def _loop(self):
        while not self.shutdown_event.is_set():
            should_sleep = 0.5
            with self.lock:
                if self.status == "running" and self.state:
                    self._step()
                    should_sleep = self.state["config"]["LIVE_SECONDS_PER_TICK"]
            time.sleep(should_sleep)

    def get_state(self):
        with self.lock:
            if not self.state:
                return {
                    "status": self.status,
                    "hasColony": False,
                    "config": self._merge_config({}),
                }
            return {
                "status": self.status,
                "hasColony": True,
                "simTime": self.state["simTime"],
                "simDay": round(self.state["simTime"] / 1440, 2),
                "topologyName": self.state["topologyName"],
                "specialChambers": self.state["specialChambers"],
                "summary": self._summary(),
                "config": self.state["config"],
                "recentEvents": list(self.state["recentEvents"][-80:]),
                "ants": {str(ant_id): self._serialize_ant(ant) for ant_id, ant in self.state["ants"].items()},
                "createdAt": self.state["createdAt"],
                "updatedAt": self.state["updatedAt"],
            }

    def get_ant_profile(self, ant_id):
        with self.lock:
            if not self.state or ant_id not in self.state["ants"]:
                return None
            ant = self.state["ants"][ant_id]
            return {
                "profile": self._serialize_ant(ant),
                "colony": {
                    "strategy": self.state["config"]["COLONY_STRATEGY"],
                    "topology": self.state["topologyName"],
                    "specialChambers": self.state["specialChambers"],
                    "simTime": self.state["simTime"],
                },
            }

    def start(self, payload=None):
        with self.lock:
            restart = bool((payload or {}).get("restart"))
            if self.state is None or restart:
                self._create_initial_state(payload)
            else:
                self.status = "running"
            self._save_snapshot()
            return self.get_state()

    def pause(self):
        with self.lock:
            if self.state:
                self.status = "paused"
                self._save_snapshot()
            return self.get_state()

    def resume(self):
        with self.lock:
            if self.state:
                self.status = "running"
                self._save_snapshot()
            return self.get_state()

    def stop(self):
        with self.lock:
            if self.state:
                self.status = "stopped"
                self._save_snapshot()
            return self.get_state()

    def shutdown(self):
        self.shutdown_event.set()
        with self.lock:
            self._save_snapshot()
