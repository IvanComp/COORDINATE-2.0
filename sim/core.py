
# core.py
# Discrete-Event core used by simulator.py. No external deps except numpy.

import os, sys, random, queue, numpy as np
from typing import List, Dict, Optional
from .privacy_techniques import PrivacyRuntime

# A thin read-only config holder (dict-like access with attributes).
class Cfg:
    def __init__(self, d: Dict):
        self.__dict__.update(d)
        # For dynamic-adaptation: track current active architecture
        if self.ARCHITECTURE == 'dynamic-adaptation':
            # Start with a default architecture (can be overridden by INITIAL_ARCHITECTURE)
            self.current_architecture = getattr(self, 'INITIAL_ARCHITECTURE', 'centralized-impprox')
        else:
            self.current_architecture = self.ARCHITECTURE
        # RTLola monitor reference (set by simulator)
        self.rtlola_monitor = None
        self.da_message_events = []
    
    def set_architecture(self, new_arch: str):
        """Update the current architecture at runtime (for dynamic-adaptation)."""
        if new_arch not in ['decentralized', 'semi-decentralized', 'centralized-impprox']:
            print(f'[WARNING] Invalid architecture for dynamic switching: {new_arch}')
            return
        self.current_architecture = new_arch
        # print(f'[ADAPTATION] Switched architecture to: {new_arch}')

    def record_coordination_message(self, simTime: float, delivered: bool):
        """Track coordination-message outcomes for dynamic-adaptation metrics."""
        self.da_message_events.append((simTime, bool(delivered)))
        self.record_monitor_event(
            simTime,
            'message_delivered' if delivered else 'message_lost',
        )

    def record_monitor_event(self, simTime: float, event: str):
        """Forward an observable runtime event to RTLola when it is active."""
        monitor = getattr(self, 'rtlola_monitor', None)
        if monitor is None or not monitor.is_running():
            return
        try:
            monitor.send_event(simTime, -1, -1, -1, -1, -1, event)
        except Exception as exc:
            print(f'[RTLola] Error sending {event}: {exc}')

class Clock:
    def __init__(self):
        self.time = 0.0
        # timestamp -> list of events (preserve simultaneous events)
        self.eventDict = {}

    def getTime(self):
        return self.time

    def scheduleEvent(self, event, avgTimes, traceFiles, distributions):
        inc = 0.0
        for avg, trace, distr in zip(avgTimes, traceFiles, distributions):
            if distr == 'exponential':
                inc += np.random.exponential(avg)
            elif distr == 'uniform':
                inc += np.random.uniform(0.0, float(avg) * 2.0)
            elif distr == 'deterministic':
                inc += float(avg)
            elif distr == 'trace':
                if avg >= 0:
                    print('[ERROR] Using trace but avg >= 0')
                    sys.exit(-1)
                with open(trace, 'r') as f:
                    lines = f.readlines()
                if len(lines) == 0:
                    print('No more timestamps in', trace)
                    os.remove(trace)
                    sys.exit(0)
                val = lines[0].strip()
                with open(trace, 'w') as f:
                    f.writelines(lines[1:])
                inc += float(val)
            else:
                print('[ERROR] Unsupported distribution:', distr)
                sys.exit(-1)
        ts = self.time + inc
        self.eventDict.setdefault(ts, []).append(event)

    def getNextEvent(self):
        if not self.eventDict:
            # No more events - simulation complete
            return None, None
        t = min(self.eventDict.keys())
        self.time = t
        ev = self.eventDict[t].pop(0)
        if len(self.eventDict[t]) == 0:
            del self.eventDict[t]
        return t, ev

    def removeEvent(self, eventToRemove):
        for k in list(self.eventDict.keys()):
            self.eventDict[k] = [ev for ev in self.eventDict[k] if ev != eventToRemove]
            if len(self.eventDict[k]) == 0:
                del self.eventDict[k]

    def checkClock(self):
        vals = [ev for evs in self.eventDict.values() for ev in evs]
        if len(vals) != len(set(vals)):
            # duplicate event label would break semantics
            dups = [x for x in set(vals) if vals.count(x) > 1]
            print('[ERROR] The same event has been scheduled more than once:', dups)
            sys.exit(-1)


class Room:
    def __init__(self, idx: int):
        self.idx = idx
        self.source = False
        self.adjacents: List['Room'] = []

    def setSource(self):
        self.source = True

    def setAdjacentRooms(self, rooms: List['Room']):
        self.adjacents = rooms

    def getAdjacentRooms(self) -> List['Room']:
        return self.adjacents

    def isAdjacent(self, room: 'Room') -> bool:
        return room in self.adjacents

    def getIdx(self) -> int:
        return self.idx

    def getProximity(self) -> Dict['Room', int]:
        # BFS distances from self
        prox = {}
        q = queue.Queue()
        q.put((self, 0))
        while not q.empty():
            r, d = q.get()
            if r not in prox:
                prox[r] = d
                for n in r.adjacents:
                    q.put((n, d + 1))
        return prox


class Item:
    def __init__(self, cfg: Cfg, logfile: str, idx: int, space: 'Space', simTime: float, imp=-1, target: Optional[Room]=None):
        self.cfg = cfg
        self.idx = idx
        self.position = space.getSource()
        self.target = target if target is not None else random.choice([r for r in space.getRooms() if r != space.getSource()])
        self.importance = self._randImportance(cfg.IMPORTANCE_PROBABILITIES) if imp == -1 else imp
        self.uber = None
        self.logfile = logfile
        if cfg.LOG_ITEM:
            self._log(simTime, 'create')

    def _randImportance(self, probs):
        if abs(sum(probs) - 1.0) > 1e-9:
            print('[ERROR] IMPORTANCE_PROBABILITIES must sum to 1')
            sys.exit(-1)
        r = np.random.uniform()
        s = 0.0
        for k, p in enumerate(probs):
            s += p
            if r < s:
                return k
        return len(probs) - 1

    # getters / setters
    def getIdx(self): return self.idx
    def getImportance(self): return self.importance
    def getLocation(self): return self.position
    def setLocation(self, room): self.position = room
    def getTarget(self): return self.target
    def getUber(self): return self.uber
    def setUber(self, robot): self.uber = robot

    def _log(self, simTime, event):
        os.makedirs(os.path.dirname(self.logfile), exist_ok=True)
        new = not os.path.exists(self.logfile)
        with open(self.logfile, 'a') as f:
            if new:
                f.write('simTime,robotId,itemId,itemImportance,position,destination,event\n')
            f.write(f'{simTime},{-1},{self.idx},{self.importance},{self.position.getIdx()},{self.target.getIdx()},{event}\n')


class Robot:
    def __init__(self, cfg: Cfg, idx: int, malicious: bool, space: 'Space', logfile: str):
        self.cfg = cfg
        self.idx = idx
        self.malicious = malicious
        self.space = space
        self.position = space.getSource()
        self.destination = space.getSource()
        self.space.setRobotPosition(self, self.position)
        self.item: Optional[Item] = None
        self.healthy = True
        self.optRoute: List[Room] = []
        self.memoryItem = None
        # A rescue is a distinct workflow from normal priority preemption.
        # Keeping it separate prevents a fake request from being abandoned
        # after the first hop instead of being checked at its reported room.
        self.rescueMission = None
        self.rescueReserved = False
        self._rescue_event_idx = 0
        self._fd_patrol_cursor = idx
        self._fd_recovery_item: Optional[Item] = None
        self.logfile = logfile

    # helpers
    def getIdx(self): return self.idx
    def isFree(self): return self.item is None
    def isHealthy(self): return self.healthy
    def isRescuing(self): return self.rescueMission is not None
    def isAvailableForRescue(self): return self.isHealthy() and not self.isRescuing() and not self.rescueReserved
    def hasOtherTasks(self): return len(self.optRoute) > 0
    def getItem(self): return self.item
    def setItem(self, item: Item): self.item, item.uber = item, self
    def unsetItem(self):
        if self.item:
            self.item.uber = None
        self.item = None
    def getItemImportance(self): return -1 if self.item is None else self.item.getImportance()
    def getLocation(self): return self.position
    def setLocation(self, r): self.position = r; self.space.setRobotPosition(self, r)
    def setDestination(self, r): self.destination = r

    def _privacy_bonus_by_importance(self, item: Optional[Item], bonus_cfg_name: str) -> float:
        if item is None:
            return 0.0
        bonuses = getattr(self.cfg, bonus_cfg_name, [0.0] * len(self.cfg.IMPORTANCE_PROBABILITIES))
        imp = item.getImportance()
        if imp < 0 or imp >= len(bonuses):
            return 0.0
        try:
            return float(bonuses[imp])
        except (TypeError, ValueError):
            return 0.0

    def _effective_comm_time(self, item: Optional[Item]) -> float:
        return float(self.cfg.COMM_TIME) + self._privacy_bonus_by_importance(item, 'PRIVACY_COMM_TIME_BONUS')

    def _effective_comp_time(self, item: Optional[Item]) -> float:
        return float(self.cfg.COMP_TIME) + self._privacy_bonus_by_importance(item, 'PRIVACY_COMP_TIME_BONUS')

    def beginFDInspection(self, simTime: float):
        """Start one local FD inspection without exchanging rescue messages."""
        if (
            self.cfg.current_architecture != 'decentralized'
            or not bool(getattr(self.cfg, 'FD_PATROL_ENABLED', True))
            or not self.isHealthy()
            or not self.isFree()
            or self.isRescuing()
            or self.optRoute
        ):
            return
        target = self.space.nextFDInspectionRoom(self)
        if target is None or target == self.position:
            return
        self.destination = target
        self.optRoute = self.space.findRoute(
            self.position, target, strategy=self.cfg.FIND_ROUTE_STRATEGY,
        )
        if self.optRoute:
            self.space.clock.scheduleEvent(
                f'move-{self.getIdx()}',
                [self.cfg.MOVEMENT_TIME],
                [self.cfg.MOVEMENT_TRACE],
                [self.cfg.MOVEMENT_DISTR],
            )

    def beginFDLocalSearch(self, simTime: float, force: bool = False) -> bool:
        """Let an idle FD agent independently explore a short local route."""
        if (
            self.cfg.current_architecture != 'decentralized'
            or not bool(getattr(self.cfg, 'FD_LOCAL_SEARCH_ENABLED', False))
            or not self.isHealthy()
            or not self.isFree()
            or self.isRescuing()
            or self.optRoute
            or self.position != self.space.getSource()
        ):
            return False
        probability = min(1.0, max(0.0, float(getattr(self.cfg, 'FD_LOCAL_SEARCH_PROBABILITY', 0.0))))
        if not force and random.random() >= probability:
            return False

        hops = max(1, int(getattr(self.cfg, 'FD_LOCAL_SEARCH_HOPS', 1)))
        route = []
        current = self.position
        previous = None
        for _ in range(hops):
            candidates = current.getAdjacentRooms()
            forward = [room for room in candidates if room != previous]
            if forward:
                candidates = forward
            if not candidates:
                break
            following = random.choice(candidates)
            route.append(following)
            previous, current = current, following
        if not route:
            return False

        self.destination = route[-1]
        self.optRoute = route
        self.space.clock.scheduleEvent(
            f'move-{self.getIdx()}',
            [self.cfg.MOVEMENT_TIME],
            [self.cfg.MOVEMENT_TRACE],
            [self.cfg.MOVEMENT_DISTR],
        )
        return True

    def _log(self, simTime, event):
        os.makedirs(os.path.dirname(self.logfile), exist_ok=True)
        new = not os.path.exists(self.logfile)
        with open(self.logfile, 'a') as f:
            if new:
                f.write('simTime,robotId,itemId,itemImportance,position,destination,event\n')
            if self.item is None:
                f.write(f'{simTime},{self.idx},{-1},{-1},{self.position.getIdx()},{self.destination.getIdx()},{event}\n')
            else:
                f.write(f'{simTime},{self.idx},{self.item.getIdx()},{self.item.getImportance()},{self.position.getIdx()},{self.destination.getIdx()},{event}\n')

    def dropItem(self, simTime, itemExpired=False):
        delivered_item = self.item
        delivered = self.position == self.destination
        if delivered:
            if self.cfg.LOG_DELIVERY: self._log(simTime, 'deliver')
            self.space.deliverItem(self.item)
        else:
            if self.cfg.LOG_DROP: self._log(simTime, 'drop')
            if itemExpired:
                self.space.clock.removeEvent(f'move-{self.getIdx()}')
            else:
                self.item.setLocation(self.position)
                self.space.switchItem(self.item)
        self.unsetItem()
        self.destination = self.space.getSource()
        if (
            delivered
            and self.cfg.current_architecture == 'decentralized'
            and self.isHealthy()
            and self._fd_recovery_item is delivered_item
        ):
            self._fd_recovery_item = None

        # A fully decentralized robot can use only what it observes locally.
        # When a failed peer has left a task in this room, continue with that
        # task instead of becoming idle after the delivery.
        if (
            delivered
            and self.cfg.current_architecture == 'decentralized'
            and self.isHealthy()
        ):
            next_item = self.space.getMoreImportantItem(room=self.position)
            if next_item is not None:
                self.loadItem(next_item, simTime)
                return

        if len(self.space.getItemsByImportance(imp=-1, room=self.position)) == 0 and self.isHealthy():
            self.optRoute = self.space.findRoute(self.position, self.destination, strategy=self.cfg.FIND_ROUTE_STRATEGY)
            if itemExpired and self.position != self.space.getSource():
                self.space.clock.scheduleEvent(f'move-{self.getIdx()}', [self.cfg.MOVEMENT_TIME], [self.cfg.MOVEMENT_TRACE], [self.cfg.MOVEMENT_DISTR])
            elif not itemExpired and self.optRoute:
                self.space.clock.scheduleEvent(f'move-{self.getIdx()}', [self.cfg.MOVEMENT_TIME], [self.cfg.MOVEMENT_TRACE], [self.cfg.MOVEMENT_DISTR])

    def loadItem(self, item: Item, simTime):
        if self.item is not None:
            self.dropItem(simTime)
        eff_comp_time = self._effective_comp_time(item)
        eff_comm_time = self._effective_comm_time(item)
        privacy_delay = 0.0
        if self.cfg.current_architecture == 'semi-decentralized':
            privacy_delay = self.space.transmitCoordinationMessage(
                simTime,
                'task_assignment',
                f'peer:{self.getIdx()}',
                f'agent:{self.getIdx()}',
                item.getTarget(),
                {'item_id': item.getIdx(), 'importance': item.getImportance()},
            )
        elif 'centralized-' in self.cfg.current_architecture:
            privacy_delay = self.space.transmitCoordinationMessage(
                simTime,
                'task_assignment',
                'coordinator',
                f'agent:{self.getIdx()}',
                item.getTarget(),
                {'item_id': item.getIdx(), 'importance': item.getImportance()},
            )
        eff_comm_time += privacy_delay
        # Pay computation/communication costs depending on mechanism
        if self.cfg.current_architecture == 'semi-decentralized':
            avg = [self.cfg.LOAD_TIME, eff_comp_time, self.cfg.MOVEMENT_TIME, eff_comm_time, self.cfg.DROP_TIME]
            trc = [self.cfg.LOAD_TRACE, self.cfg.COMP_TRACE, self.cfg.MOVEMENT_TRACE, self.cfg.COMM_TRACE, self.cfg.DROP_TRACE]
            dst = [self.cfg.LOAD_DISTR, self.cfg.COMP_DISTR, self.cfg.MOVEMENT_DISTR, self.cfg.COMM_DISTR, self.cfg.DROP_DISTR]
        elif 'centralized-' in self.cfg.current_architecture:
            avg = [self.cfg.LOAD_TIME, 0, self.cfg.MOVEMENT_TIME, eff_comm_time, self.cfg.DROP_TIME]
            trc = [self.cfg.LOAD_TRACE, '_', self.cfg.MOVEMENT_TRACE, self.cfg.COMM_TRACE, self.cfg.DROP_TRACE]
            dst = [self.cfg.LOAD_DISTR, self.cfg.COMP_DISTR, self.cfg.MOVEMENT_DISTR, self.cfg.COMM_DISTR, self.cfg.DROP_DISTR]
        else:
            avg = [self.cfg.LOAD_TIME, eff_comp_time, self.cfg.MOVEMENT_TIME, 0, self.cfg.DROP_TIME]
            trc = [self.cfg.LOAD_TRACE, self.cfg.COMP_TRACE, self.cfg.MOVEMENT_TRACE, '_', self.cfg.DROP_TRACE]
            dst = [self.cfg.LOAD_DISTR, self.cfg.COMP_DISTR, self.cfg.MOVEMENT_DISTR, self.cfg.COMM_DISTR, self.cfg.DROP_DISTR]
        self.space.clock.scheduleEvent(f'move-{self.getIdx()}', avg, trc, dst)
        self.memoryItem = None
        self.setItem(item)
        self.destination = item.getTarget()
        self.space.switchItem(item)
        self.optRoute = self.space.findRoute(self.position, self.destination, strategy=self.cfg.FIND_ROUTE_STRATEGY)
        if self.cfg.LOG_LOAD:
            self._log(simTime, 'startLoading')

    def canLoadItem(self):
        if not self.isHealthy(): return False
        if len(self.space.getItemsByImportance(imp=-1, room=self.position)) == 0: return False
        if self.isFree(): return True
        currImp = self.item.getImportance()
        impItems = self.space.getItemsWithMoreImportance(imp=currImp, room=self.position)
        return len(impItems) > 0

    def move(self, simTime):
        if len(self.optRoute) == 0:
            print(f'[ERROR] Robot {self.getIdx()} stuck in Room {self.position.getIdx()}'); sys.exit(-1)
        nextRoom = self.optRoute.pop(0)
        self.setLocation(nextRoom)
        if self.cfg.LOG_MOVE: self._log(simTime, 'move')
        if self._fail(simTime):
            self.space.clock.scheduleEvent(f'recovery-{self.getIdx()}', [self.cfg.RECOVERY_TIME], [self.cfg.RECOVERY_TRACE], [self.cfg.RECOVERY_DISTR])
            self.memoryItem = None
            self.rescueMission = None
        elif self.isRescuing():
            self._continueRescueMission(simTime)
            return
        elif self.destination == nextRoom and not self.isFree():
            self.dropItem(simTime); self.memoryItem = None
        elif self._fd_recovery_item is not None and self.position == self.destination:
            recovery_item = self._fd_recovery_item
            self._fd_recovery_item = None
            if recovery_item in self.space.availItems and recovery_item.getLocation() == self.position:
                self.loadItem(recovery_item, simTime)
            elif self.canLoadItem():
                self.loadItem(self.space.getMoreImportantItem(room=nextRoom), simTime)
        elif self.memoryItem is not None:
            if self.memoryItem[0].getImportance() > self.space.getMaxImportance(room=nextRoom):
                self.optRoute = self.space.findRoute(self.position, self.memoryItem[1], strategy=self.cfg.FIND_ROUTE_STRATEGY)
                self.space.clock.scheduleEvent(f'move-{self.getIdx()}', [self.cfg.MOVEMENT_TIME], [self.cfg.MOVEMENT_TRACE], [self.cfg.MOVEMENT_DISTR])
            else:
                self.loadItem(self.space.getMoreImportantItem(room=nextRoom), simTime)
            self.memoryItem = None
        elif self.canLoadItem():
            self.loadItem(self.space.getMoreImportantItem(room=nextRoom), simTime)
        elif len(self.optRoute) == 0 and self.isFree() and self.position != self.space.getSource():
            self.destination = self.space.getSource()
            self.optRoute = self.space.findRoute(self.position, self.destination, strategy=self.cfg.FIND_ROUTE_STRATEGY)
            self.space.clock.scheduleEvent(f'move-{self.getIdx()}', [self.cfg.MOVEMENT_TIME], [self.cfg.MOVEMENT_TRACE], [self.cfg.MOVEMENT_DISTR])
        elif not (self.isFree() and self.position == self.space.getSource()):
            self.space.clock.scheduleEvent(f'move-{self.getIdx()}', [self.cfg.MOVEMENT_TIME], [self.cfg.MOVEMENT_TRACE], [self.cfg.MOVEMENT_DISTR])
        # malicious fake messages
        if self.isHealthy() and self.malicious and self.cfg.MALICIOUS_FAKE_FAILURES:
            # The coordination layer models delivery (or loss) of the actual
            # rescue request.  A malicious agent still attempts the request.
            self._fakeFailure(nextRoom, simTime)

    def _fail(self, simTime):
        if np.random.uniform() < self.cfg.FAIL_PROB:
            self.healthy = False
            if self.cfg.LOG_FAIL: self._log(simTime, 'fail')
            if self.item is not None:
                itemToDrop = self.item
                requeue_failed_fd_task = (
                    self.cfg.current_architecture == 'decentralized'
                    and bool(getattr(self.cfg, 'FD_REQUEUE_ON_FAILURE', False))
                    and self.position != self.destination
                )
                if requeue_failed_fd_task:
                    # FD has no rescue message or dispatcher. A durable task
                    # is simply republished to its origin after a failed run,
                    # where any independently available agent may pick it up.
                    itemToDrop.setLocation(self.space.getSource())
                    self.space.switchItem(itemToDrop)
                    self.unsetItem()
                    self.destination = self.space.getSource()
                    self.optRoute = []
                elif self.cfg.current_architecture == 'decentralized':
                    self._fd_recovery_item = itemToDrop
                    self.dropItem(simTime)
                else:
                    self.dropItem(simTime)
                if self.cfg.current_architecture == 'semi-decentralized':
                    importance = itemToDrop.getImportance() if not self.malicious else len(self.cfg.IMPORTANCE_PROBABILITIES) + 1
                    self._sendPeers(importance, self.position, simTime)
                elif 'centralized-' in self.cfg.current_architecture:
                    strat = self.cfg.current_architecture.split('-')[1]
                    importance = itemToDrop.getImportance() if not self.malicious else len(self.cfg.IMPORTANCE_PROBABILITIES) + 1
                    self._sendMaster(importance, self.position, simTime, strat)
            return True
        return False

    def recovery(self, simTime):
        self.healthy = True
        self.position = self.space.getSource()
        self.space.setRobotPosition(self, self.position)
        self.destination = self.space.getSource()
        self.optRoute = []
        if self.cfg.LOG_RECOVERY: self._log(simTime, 'recover')
        if self.cfg.current_architecture == 'decentralized' and self._fd_recovery_item is not None:
            recovery_item = self._fd_recovery_item
            if recovery_item in self.space.availItems:
                self.destination = recovery_item.getLocation()
                self.optRoute = self.space.findRoute(
                    self.position, self.destination, strategy=self.cfg.FIND_ROUTE_STRATEGY,
                )
                if self.optRoute:
                    self.space.clock.scheduleEvent(
                        f'move-{self.getIdx()}',
                        [self.cfg.MOVEMENT_TIME],
                        [self.cfg.MOVEMENT_TRACE],
                        [self.cfg.MOVEMENT_DISTR],
                    )
                    return
                if self.destination == self.position:
                    self._fd_recovery_item = None
                    self.loadItem(recovery_item, simTime)
                    return
            self._fd_recovery_item = None
        if self.canLoadItem():
            self.loadItem(self.space.getMoreImportantItem(room=self.position), simTime)

    # messaging
    def _sendPeers(self, itemImportance, position, simTime, fake=False):
        near = self.space.getNearRobots(self)
        if self.cfg.LOG_HELP and not fake: self._log(simTime, 'help')
        if hasattr(self.cfg, 'record_monitor_event'):
            self.cfg.record_monitor_event(simTime, 'rescue_request')
        # choose a helper among close robots with min importance
        cand = self.space.getRobotsByImportance(self, near, itemImportance)
        if len(cand) == 0: return None
        helper = random.choice(cand)
        # SD remains peer-local, but the rescue request still traverses one
        # communication hop before a helper can change mission.
        self.space.schedulePeerRescue(self, helper, itemImportance, position, simTime, fake=fake)

    def _sendMaster(self, itemImportance, position, simTime, strategy, fake=False):
        if self.cfg.LOG_HELP and not fake: self._log(simTime, 'help')
        if hasattr(self.cfg, 'record_monitor_event'):
            self.cfg.record_monitor_event(simTime, 'rescue_request')
        self.space.scheduleCentralRequest(self, itemImportance, position, simTime, strategy, fake=fake)

    def _fakeFailure(self, position, simTime):
        if self.cfg.LOG_FAKE: self._log(simTime, 'fakeFailure')
        # Endpoint telemetry observes a suspicious false-failure signal before
        # the active coordination mechanism decides whether to act on it.
        # This makes the DA context independent of the preceding architecture.
        if hasattr(self.cfg, 'record_monitor_event'):
            self.cfg.record_monitor_event(simTime, 'suspicious_signal')
        maxImp = len(self.cfg.IMPORTANCE_PROBABILITIES) + 1
        if self.cfg.current_architecture == 'semi-decentralized':
            self._sendPeers(maxImp, self.position, simTime, fake=True)
        elif 'centralized-' in self.cfg.current_architecture:
            strat = self.cfg.current_architecture.split('-')[1]
            self._sendMaster(maxImp, self.position, simTime, strat, fake=True)

    def _scheduleRescueVerification(self, simTime):
        if self.rescueMission is not None:
            self.rescueMission['verification_pending'] = True
        self._rescue_event_idx += 1
        verification_time = max(
            0.0,
            float(getattr(self.cfg, 'RESCUE_VERIFICATION_TIME', self.cfg.COMP_TIME)),
        )
        self.space.clock.scheduleEvent(
            f'rescue-verification-{self.getIdx()}-{self._rescue_event_idx}',
            [verification_time],
            ['_'],
            ['deterministic'],
        )

    def _resumeInterruptedMission(self, simTime):
        mission = self.rescueMission
        if mission is None:
            return

        resume_item = mission['resume_item']
        resume_room = mission['resume_room']
        if resume_item is None:
            self.rescueMission = None
            if self.position != self.space.getSource():
                self.destination = self.space.getSource()
                self.optRoute = self.space.findRoute(self.position, self.destination, strategy=self.cfg.FIND_ROUTE_STRATEGY)
                self.space.clock.scheduleEvent(f'move-{self.getIdx()}', [self.cfg.MOVEMENT_TIME], [self.cfg.MOVEMENT_TRACE], [self.cfg.MOVEMENT_DISTR])
            return

        if self.position == resume_room:
            self.rescueMission = None
            if resume_item in self.space.availItems and resume_item.getLocation() == self.position:
                self.loadItem(resume_item, simTime)
            elif self.canLoadItem():
                self.loadItem(self.space.getMoreImportantItem(room=self.position), simTime)
            return

        mission['stage'] = 'return'
        self.destination = resume_room
        self.optRoute = self.space.findRoute(self.position, self.destination, strategy=self.cfg.FIND_ROUTE_STRATEGY)
        self.space.clock.scheduleEvent(f'move-{self.getIdx()}', [self.cfg.MOVEMENT_TIME], [self.cfg.MOVEMENT_TRACE], [self.cfg.MOVEMENT_DISTR])

    def _continueRescueMission(self, simTime):
        mission = self.rescueMission
        if mission is None:
            return

        if mission['stage'] == 'return':
            if self.position == mission['resume_room']:
                self._resumeInterruptedMission(simTime)
            elif self.optRoute:
                self.space.clock.scheduleEvent(f'move-{self.getIdx()}', [self.cfg.MOVEMENT_TIME], [self.cfg.MOVEMENT_TRACE], [self.cfg.MOVEMENT_DISTR])
            return

        if self.position != mission['help_room']:
            if self.optRoute:
                self.space.clock.scheduleEvent(f'move-{self.getIdx()}', [self.cfg.MOVEMENT_TIME], [self.cfg.MOVEMENT_TRACE], [self.cfg.MOVEMENT_DISTR])
            return

        if mission['fake']:
            if not mission.get('verification_pending', False):
                self._scheduleRescueVerification(simTime)
            return

        rescue_item = self.space.getMoreImportantItem(room=self.position)
        self.rescueMission = None
        if rescue_item is not None:
            self.loadItem(rescue_item, simTime)
        else:
            self.rescueMission = mission
            self._resumeInterruptedMission(simTime)

    def completeRescueVerification(self, simTime):
        """Resume after reaching a fake rescue location and finding no task."""
        if (
            self.rescueMission is not None
            and self.rescueMission['fake']
            and self.rescueMission.get('verification_pending', False)
        ):
            self.rescueMission['verification_pending'] = False
            if hasattr(self.cfg, 'record_monitor_event'):
                self.cfg.record_monitor_event(simTime, 'verified_fake_request')
            self._resumeInterruptedMission(simTime)

    def _abortMission(self, newItemImportance, helpRoom, simTime, fake=False):
        if self.cfg.LOG_RESCUE: self._log(simTime, 'rescue')
        if not self.isAvailableForRescue() or self.getItemImportance() >= newItemImportance:
            return False

        resume_item = self.item
        resume_room = self.position
        if not self.isFree():
            self.dropItem(simTime)
        self.space.clock.removeEvent(f'move-{self.getIdx()}')
        self.rescueMission = {
            'fake': bool(fake),
            'help_room': helpRoom,
            'requested_importance': newItemImportance,
            'resume_item': resume_item,
            'resume_room': resume_room,
            'stage': 'outbound',
            'verification_pending': False,
        }

        if self.position == helpRoom:
            if fake:
                self._scheduleRescueVerification(simTime)
            else:
                self._continueRescueMission(simTime)
            return True

        self.destination = helpRoom
        self.optRoute = self.space.findRoute(self.position, self.destination, strategy=self.cfg.FIND_ROUTE_STRATEGY)
        self.space.clock.scheduleEvent(f'move-{self.getIdx()}', [self.cfg.MOVEMENT_TIME], [self.cfg.MOVEMENT_TRACE], [self.cfg.MOVEMENT_DISTR])
        return True


class Space:
    def __init__(self, cfg: Cfg, rooms: List[Room], connection_dict, clock: Clock, source: Optional[Room] = None):
        self.cfg = cfg
        self.rooms = rooms
        self.connections_dict = connection_dict
        self.clock = clock
        self.source = source or rooms[0]
        self.source.setSource()
        for i, adjs in connection_dict.items():
            rooms[i].setAdjacentRooms([rooms[j] for j in adjs])
        self.availItems: List[Item] = []
        self.movingItems: List[Item] = []
        self.robotPositionDict: Dict[Robot, Room] = {}
        self._central_request_idx = 0
        self._central_requests = {}
        self._central_decisions = {}
        self._central_commands = {}
        self._peer_rescue_idx = 0
        self._peer_rescues = {}
        self._coordinator_available_at = 0.0
        self._fd_patrol_cursor = 0
        self._fd_patroller_cursor = 0
        self.central_coordination_stats = {
            'requests': 0,
            'commands_sent': 0,
            'commands_lost': 0,
            'coordinator_failures': 0,
            'queue_delay_s': 0.0,
        }
        self.privacy = PrivacyRuntime(cfg, connection_dict, self.source.getIdx())

    def getSource(self): return self.source
    def getRooms(self): return self.rooms
    def getClock(self): return self.clock
    def getAllRobots(self): return list(self.robotPositionDict.keys())

    def transmitCoordinationMessage(self, simTime, messageType, sender, receiver, destination, fields=None):
        destination_id = destination.getIdx() if hasattr(destination, 'getIdx') else int(destination)
        return self.privacy.transmit(
            simTime,
            messageType,
            sender,
            receiver,
            destination_id,
            fields,
        )

    def nextFDInspectionRoom(self, robot: Robot) -> Optional[Room]:
        """Return the next room in a shared, capacity-limited FD patrol."""
        candidates = [room for room in self.rooms if room != self.source]
        if not candidates:
            return None
        index = self._fd_patrol_cursor % len(candidates)
        self._fd_patrol_cursor += 1
        return candidates[index]

    def selectFDPatroller(self) -> Optional[Robot]:
        """Rotate finite FD patrol slots among currently idle, healthy robots."""
        candidates = [
            bot for bot in self.getAllRobots()
            if bot.isHealthy() and bot.isFree() and not bot.isRescuing() and not bot.optRoute
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda bot: bot.getIdx())
        index = self._fd_patroller_cursor % len(candidates)
        self._fd_patroller_cursor += 1
        return candidates[index]

    def setRobotPosition(self, robot: Robot, room: Room):
        self.robotPositionDict[robot] = room

    def getNearRobots(self, askingRobot: Robot) -> List[Robot]:
        targetRoom = askingRobot.getLocation()
        # SD coordinates within a bounded neighbourhood, rather than only
        # with robots occupying the same edge of the topology. The radius is
        # configurable and remains strictly smaller than global CE visibility.
        hops = max(1, int(getattr(self.cfg, 'SD_COORDINATION_HOPS', 1)))
        proximity = targetRoom.getProximity()
        outs = []
        for bot, room in self.robotPositionDict.items():
            if bot != askingRobot and proximity.get(room, float('inf')) <= hops:
                outs.append(bot)
        return outs

    def getRobotsByImportance(self, askingRobot: Robot, bots: List[Robot], itemImportance: int) -> List[Robot]:
        bots = [b for b in bots if b != askingRobot and b.isAvailableForRescue()]
        minImp = itemImportance
        for b in bots:
            if b.isAvailableForRescue():
                curr = b.getItemImportance()
                if curr == -1:
                    minImp = curr; break
                elif curr < minImp:
                    minImp = curr
        if minImp >= itemImportance: return []
        return [b for b in bots if b.isAvailableForRescue() and b.getItemImportance() == minImp]

    def getRobotsByProximity(self, askingRobot: Robot, bots: List[Robot], targetRoom: Room) -> List[Robot]:
        bots = [b for b in bots if b != askingRobot and b.isAvailableForRescue()]
        prox = targetRoom.getProximity()
        minH = min([prox[self.robotPositionDict[b]] for b in bots], default=10**9)
        return [b for b in bots if prox[self.robotPositionDict[b]] == minH]

    def schedulePeerRescue(self, requester: Robot, helper: Robot, itemImportance: int,
                           position: Room, simTime: float, fake: bool = False):
        """Deliver a peer-local SD rescue request after one communication hop."""
        message_lost = np.random.uniform() < max(
            0.0, min(1.0, float(getattr(self.cfg, 'COMM_FAIL_PROB', 0.0))),
        )
        if hasattr(self.cfg, 'record_coordination_message'):
            self.cfg.record_coordination_message(simTime, not message_lost)
        if message_lost:
            if self.cfg.LOG_HELP and not fake:
                requester._log(simTime, 'peerRequestLost')
            return

        self._peer_rescue_idx += 1
        rescue_id = self._peer_rescue_idx
        helper.rescueReserved = True
        self._peer_rescues[rescue_id] = {
            'requester': requester,
            'helper': helper,
            'importance': itemImportance,
            'position': position,
            'fake': fake,
        }
        privacy_delay = self.transmitCoordinationMessage(
            simTime,
            'peer_rescue_request',
            f'agent:{requester.getIdx()}',
            f'agent:{helper.getIdx()}',
            position,
            {'importance': itemImportance, 'fake': bool(fake)},
        )
        self.clock.scheduleEvent(
            f'peer-rescue-{rescue_id}',
            [self.cfg.COMM_TIME + privacy_delay],
            [self.cfg.COMM_TRACE],
            [self.cfg.COMM_DISTR],
        )

    def processPeerRescue(self, rescue_id: int, simTime: float):
        rescue = self._peer_rescues.pop(rescue_id, None)
        if rescue is None:
            return
        helper = rescue['helper']
        helper.rescueReserved = False
        helper._abortMission(
            rescue['importance'], rescue['position'], simTime, fake=rescue['fake']
        )

    def scheduleCentralRequest(self, requester: Robot, itemImportance: int, position: Room,
                               simTime: float, strategy: str, fake: bool = False):
        """Schedule the requester-to-coordinator hop before central dispatch."""
        message_lost = np.random.uniform() < max(
            0.0, min(1.0, float(getattr(self.cfg, 'COMM_FAIL_PROB', 0.0))),
        )
        if hasattr(self.cfg, 'record_coordination_message'):
            self.cfg.record_coordination_message(simTime, not message_lost)
        if message_lost:
            if self.cfg.LOG_HELP and not fake:
                requester._log(simTime, 'centralRequestLost')
            return

        self._central_request_idx += 1
        request_id = self._central_request_idx
        self._central_requests[request_id] = {
            'requester': requester,
            'importance': itemImportance,
            'position': position,
            'strategy': strategy,
            'fake': fake,
        }
        self.central_coordination_stats['requests'] += 1
        if self.cfg.LOG_HELP and not fake:
            requester._log(simTime, 'centralRequest')
        privacy_delay = self.transmitCoordinationMessage(
            simTime,
            'central_rescue_request',
            f'agent:{requester.getIdx()}',
            'coordinator',
            position,
            {'importance': itemImportance, 'fake': bool(fake)},
        )
        self.clock.scheduleEvent(
            f'central-request-{request_id}',
            [self.cfg.COMM_TIME + privacy_delay],
            [self.cfg.COMM_TRACE],
            [self.cfg.COMM_DISTR],
        )

    def _selectCentralHelper(self, requester: Robot, itemImportance: int, position: Room, strategy: str):
        bots = self.getAllRobots()
        if strategy == 'proximity':
            candidates = self.getRobotsByProximity(requester, bots, position)
        elif strategy == 'importance':
            candidates = self.getRobotsByImportance(requester, bots, itemImportance)
        elif strategy == 'proximp':
            nearby = self.getRobotsByProximity(requester, bots, position)
            candidates = self.getRobotsByImportance(requester, nearby, itemImportance) if nearby else []
        elif strategy == 'impprox':
            lower_priority = self.getRobotsByImportance(requester, bots, itemImportance)
            candidates = self.getRobotsByProximity(requester, lower_priority, position) if lower_priority else []
        else:
            print('Unsupported centralized strategy'); sys.exit(-1)
        return random.choice(candidates) if candidates else None

    def processCentralRequest(self, request_id: int, simTime: float):
        """Queue a request for finite-capacity central processing."""
        request = self._central_requests.pop(request_id, None)
        if request is None:
            return

        # CE has a single coordinator. If it is unavailable, the rescue cannot
        # be dispatched; SD and FD do not traverse this code path.
        coordinator_available = bool(getattr(self.cfg, 'COORDINATOR_AVAILABLE', True))
        if not coordinator_available:
            self.central_coordination_stats['coordinator_failures'] += 1
            if hasattr(self.cfg, 'record_coordination_message'):
                self.cfg.record_coordination_message(simTime, False)
            if hasattr(self.cfg, 'record_monitor_event'):
                self.cfg.record_monitor_event(simTime, 'coordinator_unavailable')
            if self.cfg.LOG_HELP and not request['fake']:
                request['requester']._log(simTime, 'centralCoordinatorUnavailable')
            return

        # Every received report, including a fake one, consumes a coordinator
        # service slot before the coordinator can determine whether a helper
        # is available. This is the intrinsic CE control-plane bottleneck.
        service_time_key = (
            'COORDINATOR_FAKE_REQUEST_SERVICE_TIME'
            if request['fake'] else 'COORDINATOR_SERVICE_TIME'
        )
        service_time = max(0.0, float(getattr(
            self.cfg, service_time_key, getattr(self.cfg, 'COORDINATOR_SERVICE_TIME', 0.0),
        )))
        service_start = max(simTime, self._coordinator_available_at)
        queue_delay = service_start - simTime
        self._coordinator_available_at = service_start + service_time
        self.central_coordination_stats['queue_delay_s'] += queue_delay
        self._central_decisions[request_id] = request
        self.clock.scheduleEvent(
            f'central-decision-{request_id}',
            [queue_delay + service_time],
            ['_'],
            ['deterministic'],
        )

    def processCentralDecision(self, request_id: int, simTime: float):
        """Finish a queued decision and dispatch a helper when possible."""
        request = self._central_decisions.pop(request_id, None)
        if request is None:
            return

        coordinator_available = bool(getattr(self.cfg, 'COORDINATOR_AVAILABLE', True))
        coordinator_failure_prob = float(getattr(self.cfg, 'COORDINATOR_FAILURE_PROB', 0.0))
        coordinator_failure_prob = min(1.0, max(0.0, coordinator_failure_prob))
        if not coordinator_available or np.random.uniform() < coordinator_failure_prob:
            self.central_coordination_stats['coordinator_failures'] += 1
            if hasattr(self.cfg, 'record_coordination_message'):
                self.cfg.record_coordination_message(simTime, False)
            if hasattr(self.cfg, 'record_monitor_event'):
                self.cfg.record_monitor_event(simTime, 'coordinator_unavailable')
            if self.cfg.LOG_HELP and not request['fake']:
                request['requester']._log(simTime, 'centralCoordinatorUnavailable')
            return

        helper = self._selectCentralHelper(
            request['requester'], request['importance'], request['position'], request['strategy']
        )
        if helper is None:
            return
        helper.rescueReserved = True

        command_loss_prob = float(getattr(self.cfg, 'COORDINATOR_COMMAND_LOSS_PROB', -1.0))
        if command_loss_prob < 0.0:
            command_loss_prob = float(self.cfg.COMM_FAIL_PROB)
        command_lost = np.random.uniform() < min(1.0, max(0.0, command_loss_prob))
        if hasattr(self.cfg, 'record_coordination_message'):
            self.cfg.record_coordination_message(simTime, not command_lost)
        if command_lost:
            helper.rescueReserved = False
            self.central_coordination_stats['commands_lost'] += 1
            if self.cfg.LOG_HELP and not request['fake']:
                request['requester']._log(simTime, 'centralCommandLost')
            return

        self._central_commands[request_id] = {
            'helper': helper,
            'importance': request['importance'],
            'position': request['position'],
            'requester': request['requester'],
            'fake': request['fake'],
        }
        self.central_coordination_stats['commands_sent'] += 1
        privacy_delay = self.transmitCoordinationMessage(
            simTime,
            'central_rescue_command',
            'coordinator',
            f'agent:{helper.getIdx()}',
            request['position'],
            {'importance': request['importance'], 'fake': bool(request['fake'])},
        )
        self.clock.scheduleEvent(
            f'central-command-{request_id}',
            [self.cfg.COMM_TIME + privacy_delay],
            [self.cfg.COMM_TRACE],
            [self.cfg.COMM_DISTR],
        )

    def processCentralCommand(self, request_id: int, simTime: float):
        command = self._central_commands.pop(request_id, None)
        if command is None:
            return
        if self.cfg.LOG_HELP and not command['fake']:
            command['requester']._log(simTime, 'centralCommand')
        command['helper'].rescueReserved = False
        command['helper']._abortMission(command['importance'], command['position'], simTime, fake=command['fake'])

    # items
    def newItem(self, item: Item):
        self.availItems.append(item)
        impIdx = item.getImportance()
        expireTime = self.cfg.EXPIRATION_TIME[impIdx]
        if expireTime != -1:
            expireDistr = self.cfg.EXPIRATION_DISTR[impIdx]
            self.clock.scheduleEvent(f'expire-{item.getIdx()}', [expireTime], ['_'], [expireDistr])
        self.clock.scheduleEvent('item', [self.cfg.ITEM_SPAWNING_TIME], [self.cfg.ITEM_SPAWNING_TRACE], [self.cfg.ITEM_SPAWNING_DISTR])

    def getItembyId(self, idx: int) -> Item:
        for item in self.availItems + self.movingItems:
            if item.getIdx() == idx:
                return item
        print('[ERROR] No item with id', idx); sys.exit(-1)

    def getItemsByImportance(self, imp=-1, room: Optional[Room]=None) -> List[Item]:
        pool = self.availItems if room is None else [it for it in self.availItems if it.getLocation() == room]
        if imp == -1: return pool
        return [it for it in pool if it.getImportance() == imp]

    def getItemsWithMoreImportance(self, imp=-1, room: Optional[Room]=None) -> List[Item]:
        pool = self.availItems if room is None else [it for it in self.availItems if it.getLocation() == room]
        if imp == -1: return pool
        return [it for it in pool if it.getImportance() > imp]

    def getMoreImportantItem(self, room: Optional[Room]=None) -> Optional[Item]:
        pool = self.availItems if room is None else [it for it in self.availItems if it.getLocation() == room]
        best = None; bestImp = -1
        for it in pool:
            ii = it.getImportance()
            if ii > bestImp:
                bestImp, best = ii, it
        return best

    def getMaxImportance(self, room: Optional[Room]=None) -> int:
        it = self.getMoreImportantItem(room)
        return -1 if it is None else it.getImportance()

    def deliverItem(self, item: Item):
        self.clock.removeEvent(f'expire-{item.getIdx()}')
        self.movingItems.remove(item)

    def expireItem(self, item: Item, simTime: float):
        if self.cfg.LOG_EXPIRE:
            item._log(simTime, 'expire')
        if item in self.availItems:
            self.availItems.remove(item)
        elif item in self.movingItems:
            self.movingItems.remove(item)
            bot = item.getUber()
            bot.dropItem(simTime, itemExpired=True)
        else:
            print('[ERROR] Expired item does not exist'); sys.exit(-1)

    def switchItem(self, item: Item):
        if item in self.availItems:
            self.availItems.remove(item); self.movingItems.append(item)
        elif item in self.movingItems:
            self.movingItems.remove(item); self.availItems.append(item)
        else:
            print('[ERROR] Switching unknown item'); sys.exit(-1)

    # routing
    def _routes_dfs(self, start: Room, target: Room, visited=None, routes=None):
        if visited is None: visited = []
        if routes is None: routes = {}
        visited = [*visited, start]
        if start == target:
            routes[str([r.getIdx() for r in visited])] = len(visited) - 1
        else:
            for r in start.getAdjacentRooms():
                if r not in visited:
                    routes = self._routes_dfs(r, target, visited, routes)
        return routes

    def _routes_bfs(self, start: Room, target: Room):
        q = queue.Queue()
        q.put([start])
        routes = {}
        while not q.empty():
            path = q.get()
            if target in path:
                cost = len(path) - 1
                if len(routes) == 0 or cost < min(routes.values()):
                    routes = {str([r.getIdx() for r in path]): cost}
                elif cost == min(routes.values()):
                    routes[str([r.getIdx() for r in path])] = cost
            elif len(routes) == 0:
                for adj in path[-1].getAdjacentRooms():
                    if adj not in path: q.put(path + [adj])
        return routes

    def findRoute(self, start: Room, target: Room, strategy='breadth') -> List[Room]:
        if strategy == 'breadth':
            routes = self._routes_bfs(start, target); poss = list(routes.keys())
        elif strategy == 'depth':
            routes = self._routes_dfs(start, target); 
            minc = min(routes.values()); poss = [k for k, v in routes.items() if v == minc]
        else:
            print('[ERROR] Unknown routing strategy'); sys.exit(-1)
        if len(poss) == 0:
            print(f'[ERROR] No route between {start.getIdx()} and {target.getIdx()}'); sys.exit(-1)
        chosen = random.choice(poss)[1:-1].split(', ')
        # Filter out empty strings and skip the first element (start room)
        chosen = [i for i in chosen if i]
        if len(chosen) > 0:
            chosen = chosen[1:]  # Skip start room
        return [self.rooms[int(i)] for i in chosen]
