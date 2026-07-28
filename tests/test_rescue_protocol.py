import unittest

from sim.core import Cfg, Clock, Item, Robot, Room, Space


def build_cfg():
    return Cfg({
        'ARCHITECTURE': 'centralized-impprox',
        'CURRENT_ARCHITECTURE': 'centralized-impprox',
        'IMPORTANCE_PROBABILITIES': [0.5, 0.1, 0.4],
        'LOAD_TIME': 0.0,
        'LOAD_DISTR': 'deterministic',
        'LOAD_TRACE': '_',
        'MOVEMENT_TIME': 1.0,
        'MOVEMENT_DISTR': 'deterministic',
        'MOVEMENT_TRACE': '_',
        'DROP_TIME': 0.0,
        'DROP_DISTR': 'deterministic',
        'DROP_TRACE': '_',
        'COMP_TIME': 0.0,
        'COMP_DISTR': 'deterministic',
        'COMP_TRACE': '_',
        'COMM_TIME': 0.0,
        'COMM_DISTR': 'deterministic',
        'COMM_TRACE': '_',
        'RESCUE_VERIFICATION_TIME': 0.0,
        'COORDINATOR_SERVICE_TIME': 0.0,
        'COORDINATOR_FAILURE_PROB': 0.0,
        'FD_INSPECTION_INTERVAL': 1.0,
        'FIND_ROUTE_STRATEGY': 'breadth',
        'LOG_ITEM': False,
        'LOG_DELIVERY': False,
        'LOG_LOAD': False,
        'LOG_DROP': False,
        'LOG_EXPIRE': False,
        'LOG_MOVE': False,
        'LOG_FAIL': False,
        'LOG_RECOVERY': False,
        'LOG_HELP': False,
        'LOG_FAKE': False,
        'LOG_RESCUE': False,
        'FAIL_PROB': 0.0,
        'MALICIOUS_FAKE_FAILURES': False,
    })


class RescueProtocolTest(unittest.TestCase):
    def test_fd_inspection_moves_a_free_robot_without_a_rescue_message(self):
        cfg = build_cfg()
        cfg.current_architecture = 'decentralized'
        clock = Clock()
        rooms = [Room(i) for i in range(3)]
        space = Space(cfg, rooms, {0: [1], 1: [0, 2], 2: [1]}, clock, source=rooms[0])
        robot = Robot(cfg, 0, False, space, '')

        robot.beginFDInspection(0.0)
        _, event = clock.getNextEvent()

        self.assertEqual(event, 'move-0')
        self.assertEqual(robot.destination, rooms[1])

    def test_unavailable_central_coordinator_does_not_dispatch_a_rescue(self):
        cfg = build_cfg()
        cfg.COORDINATOR_FAILURE_PROB = 1.0
        clock = Clock()
        rooms = [Room(i) for i in range(2)]
        space = Space(cfg, rooms, {0: [1], 1: [0]}, clock, source=rooms[0])
        requester = Robot(cfg, 0, False, space, '')
        helper = Robot(cfg, 1, False, space, '')
        requester.setLocation(rooms[0])
        helper.setLocation(rooms[1])

        space.scheduleCentralRequest(requester, 1, rooms[0], 0.0, 'impprox')
        timestamp, event = clock.getNextEvent()
        self.assertEqual(event, 'central-request-1')
        space.processCentralRequest(1, timestamp)

        timestamp, event = clock.getNextEvent()
        self.assertEqual(event, 'central-decision-1')
        space.processCentralDecision(1, timestamp)

        self.assertEqual(space.central_coordination_stats['coordinator_failures'], 1)
        self.assertFalse(helper.rescueReserved)
        self.assertEqual(space._central_commands, {})

    def test_fake_rescue_reaches_reported_room_then_resumes_interrupted_task(self):
        cfg = build_cfg()
        clock = Clock()
        rooms = [Room(i) for i in range(3)]
        space = Space(cfg, rooms, {0: [1], 1: [0, 2], 2: [1]}, clock, source=rooms[0])
        helper = Robot(cfg, 0, False, space, '')
        requester = Robot(cfg, 1, True, space, '')
        requester.setLocation(rooms[2])

        original = Item(cfg, '', 1, space, 0.0, imp=0, target=rooms[2])
        original.setLocation(rooms[0])
        space.movingItems.append(original)
        helper.setItem(original)
        helper.destination = rooms[2]
        helper.optRoute = space.findRoute(rooms[0], rooms[2])

        helper._abortMission(4, rooms[2], 0.0, fake=True)
        visited = []
        while True:
            ts, event = clock.getNextEvent()
            if event is None:
                break
            if event == 'move-0':
                helper.move(ts)
                visited.append(helper.getLocation().getIdx())
                if helper.getItem() is original and not helper.isRescuing():
                    break
            elif event.startswith('rescue-verification-0-'):
                helper.completeRescueVerification(ts)

        self.assertIn(2, visited)
        self.assertIs(helper.getItem(), original)
        self.assertEqual(helper.destination, rooms[2])

    def test_sd_fake_request_reaches_a_nearby_peer(self):
        cfg = build_cfg()
        cfg.current_architecture = 'semi-decentralized'
        clock = Clock()
        rooms = [Room(i) for i in range(2)]
        space = Space(cfg, rooms, {0: [1], 1: [0]}, clock, source=rooms[0])
        requester = Robot(cfg, 0, True, space, '')
        helper = Robot(cfg, 1, False, space, '')
        requester.setLocation(rooms[0])
        helper.setLocation(rooms[1])

        requester._sendPeers(4, rooms[0], 0.0, fake=True)

        _, event = clock.getNextEvent()
        self.assertEqual(event, 'peer-rescue-1')
        self.assertTrue(helper.rescueReserved)

    def test_sd_request_is_lost_when_the_communication_hop_fails(self):
        cfg = build_cfg()
        cfg.current_architecture = 'semi-decentralized'
        cfg.COMM_FAIL_PROB = 1.0
        clock = Clock()
        rooms = [Room(i) for i in range(2)]
        space = Space(cfg, rooms, {0: [1], 1: [0]}, clock, source=rooms[0])
        requester = Robot(cfg, 0, False, space, '')
        helper = Robot(cfg, 1, False, space, '')
        requester.setLocation(rooms[0])
        helper.setLocation(rooms[1])

        requester._sendPeers(1, rooms[0], 0.0)

        _, event = clock.getNextEvent()
        self.assertIsNone(event)
        self.assertFalse(helper.rescueReserved)

    def test_fake_rescue_verification_is_idempotent(self):
        cfg = build_cfg()
        clock = Clock()
        rooms = [Room(i) for i in range(2)]
        space = Space(cfg, rooms, {0: [1], 1: [0]}, clock, source=rooms[0])
        helper = Robot(cfg, 0, False, space, '')

        helper._abortMission(4, rooms[0], 0.0, fake=True)
        # A repeated completion signal must not resume the same mission twice.
        helper.completeRescueVerification(0.0)
        helper.completeRescueVerification(0.0)

        move_events = [
            event
            for events in clock.eventDict.values()
            for event in events
            if event == 'move-0'
        ]
        self.assertLessEqual(len(move_events), 1)


if __name__ == '__main__':
    unittest.main()
