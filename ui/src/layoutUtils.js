function seededNoise(seed) {
    const value = Math.sin(seed * 12.9898) * 43758.5453;
    return value - Math.floor(value);
}

function organicOrbit(index, total, radiusBase = 16) {
    if (index === 0) {
        return { x: 0, y: 0, z: 0 };
    }

    const goldenAngle = Math.PI * (3 - Math.sqrt(5));
    const ring = Math.floor(Math.sqrt(index));
    const angle = (index * goldenAngle) + (seededNoise(index * 4.1) - 0.5) * 0.75;
    const radius = radiusBase + (ring * 10) + (seededNoise(index * 7.3) - 0.5) * 6;

    return {
        x: Math.cos(angle) * radius,
        y: 0,
        z: Math.sin(angle) * radius,
    };
}

function buildOrganicMesh(topology) {
    const positions = {};

    topology.nodes.forEach((node, idx) => {
        const orbit = organicOrbit(idx, topology.nodes.length, 15);
        positions[node.id] = {
            x: orbit.x + ((idx % 2 === 0 ? 1 : -1) * seededNoise(idx + 1) * 4),
            y: 0,
            z: orbit.z + ((idx % 3 === 0 ? -1 : 1) * seededNoise(idx + 9) * 4),
        };
    });

    return positions;
}

function buildOrganicRing(topology) {
    const positions = {};
    const count = topology.nodes.length;
    const radius = Math.max(22, count * 3.6);

    topology.nodes.forEach((node, idx) => {
        const angle = (idx / count) * Math.PI * 2;
        const wobble = (seededNoise(idx * 5.2) - 0.5) * 5;
        positions[node.id] = {
            x: Math.cos(angle) * (radius + wobble),
            y: 0,
            z: Math.sin(angle) * (radius - wobble),
        };
    });

    return positions;
}

function buildOrganicTree(topology) {
    const levels = buildTreeLevels(topology);
    const positions = {};

    levels.forEach((level, levelIdx) => {
        const depthRadius = 10 + (levelIdx * 14);
        level.forEach((nodeId, posIdx) => {
            const spread = Math.max(1, level.length - 1);
            const progress = spread === 0 ? 0.5 : posIdx / spread;
            const angle = (-Math.PI / 2) + (progress * Math.PI) + ((seededNoise(nodeId + 3) - 0.5) * 0.24);
            positions[nodeId] = {
                x: Math.cos(angle) * depthRadius * 1.3,
                y: 0,
                z: Math.sin(angle) * depthRadius + (levelIdx * 6),
            };
        });
    });

    return positions;
}

export function calculateRoomPositions(topology, topologyName) {
    if (!topology || !topology.nodes) return {};

    if (topologyName.startsWith('mesh')) {
        return buildOrganicMesh(topology);
    }

    if (topologyName.startsWith('ring')) {
        return buildOrganicRing(topology);
    }

    if (topologyName.startsWith('tree')) {
        return buildOrganicTree(topology);
    }

    return buildOrganicMesh(topology);
}

function buildTreeLevels(topology) {
    const levels = [];
    const visited = new Set();
    const queue = [0];
    visited.add(0);

    while (queue.length > 0) {
        const levelSize = queue.length;
        const currentLevel = [];

        for (let i = 0; i < levelSize; i += 1) {
            const nodeId = queue.shift();
            currentLevel.push(nodeId);

            const edges = topology.edges.filter((edge) => edge.source === nodeId || edge.target === nodeId);
            edges.forEach((edge) => {
                const neighbor = edge.source === nodeId ? edge.target : edge.source;
                if (!visited.has(neighbor)) {
                    visited.add(neighbor);
                    queue.push(neighbor);
                }
            });
        }

        levels.push(currentLevel);
    }

    return levels;
}

export function calculateCorridors(topology, positions) {
    if (!topology || !topology.edges) return [];

    return topology.edges.flatMap((edge, index) => {
        const sourcePos = positions[edge.source];
        const targetPos = positions[edge.target];

        if (!sourcePos || !targetPos) return [];

        const midpoint = {
            x: (sourcePos.x + targetPos.x) / 2 + ((seededNoise(index + 20) - 0.5) * 6),
            y: 0,
            z: (sourcePos.z + targetPos.z) / 2 + ((seededNoise(index + 40) - 0.5) * 6),
        };

        return [{
            start: sourcePos,
            control: midpoint,
            end: targetPos,
            source: edge.source,
            target: edge.target,
        }];
    });
}
