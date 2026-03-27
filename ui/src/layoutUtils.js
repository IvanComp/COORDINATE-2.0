// Utility to convert topology graph to 3D room positions

export function calculateRoomPositions(topology, topologyName) {
    if (!topology || !topology.nodes) return {};

    const positions = {};
    const numRooms = topology.nodes.length;

    // Determine layout strategy based on topology name
    if (topologyName.startsWith('mesh')) {
        // Grid layout for mesh topologies
        const gridSize = Math.ceil(Math.sqrt(numRooms));
        const spacing = 8; // Distance between rooms

        topology.nodes.forEach((node, idx) => {
            const row = Math.floor(idx / gridSize);
            const col = idx % gridSize;
            positions[node.id] = {
                x: (col - gridSize / 2) * spacing,
                y: 0,
                z: (row - gridSize / 2) * spacing
            };
        });
    } else if (topologyName.startsWith('ring')) {
        // Circular layout for ring topologies
        const radius = numRooms * 1.5;

        topology.nodes.forEach((node, idx) => {
            const angle = (idx / numRooms) * Math.PI * 2;
            positions[node.id] = {
                x: Math.cos(angle) * radius,
                y: 0,
                z: Math.sin(angle) * radius
            };
        });
    } else if (topologyName.startsWith('tree')) {
        // Hierarchical layout for tree topologies
        const levels = buildTreeLevels(topology);
        const spacing = 8;

        levels.forEach((level, levelIdx) => {
            const levelWidth = level.length;
            level.forEach((nodeId, posIdx) => {
                positions[nodeId] = {
                    x: (posIdx - levelWidth / 2) * spacing,
                    y: 0,
                    z: levelIdx * spacing
                };
            });
        });
    } else {
        // Default: force-directed-like layout (simplified)
        // Just use a grid as fallback
        const gridSize = Math.ceil(Math.sqrt(numRooms));
        const spacing = 8;

        topology.nodes.forEach((node, idx) => {
            const row = Math.floor(idx / gridSize);
            const col = idx % gridSize;
            positions[node.id] = {
                x: (col - gridSize / 2) * spacing,
                y: 0,
                z: (row - gridSize / 2) * spacing
            };
        });
    }

    return positions;
}

function buildTreeLevels(topology) {
    // BFS to build tree levels
    const levels = [];
    const visited = new Set();
    const queue = [0]; // Start from root (node 0)
    visited.add(0);

    while (queue.length > 0) {
        const levelSize = queue.length;
        const currentLevel = [];

        for (let i = 0; i < levelSize; i++) {
            const nodeId = queue.shift();
            currentLevel.push(nodeId);

            // Find neighbors
            const node = topology.nodes.find(n => n.id === nodeId);
            if (node) {
                const edges = topology.edges.filter(e =>
                    e.source === nodeId || e.target === nodeId
                );

                edges.forEach(edge => {
                    const neighbor = edge.source === nodeId ? edge.target : edge.source;
                    if (!visited.has(neighbor)) {
                        visited.add(neighbor);
                        queue.push(neighbor);
                    }
                });
            }
        }

        levels.push(currentLevel);
    }

    return levels;
}

export function calculateCorridors(topology, positions) {
    // Generate corridor data for rendering connections between rooms
    if (!topology || !topology.edges) return [];

    const corridors = [];

    topology.edges.forEach(edge => {
        const sourcePos = positions[edge.source];
        const targetPos = positions[edge.target];

        if (sourcePos && targetPos) {
            corridors.push({
                start: sourcePos,
                end: targetPos,
                source: edge.source,
                target: edge.target
            });
        }
    });

    return corridors;
}
