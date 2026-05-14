// Utility to convert topology graph to 3D room positions

export function calculateRoomPositions(topology, topologyName) {
    if (!topology || !topology.nodes) return {};

    // Custom layout for GUH73
    if (topologyName === 'GUH73') {
        return calculateGUH73Positions(topology);
    }

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
    } else if (topologyName.startsWith('line')) {
        // Single corridor layout for line topologies
        const spacing = 7;
        const midpoint = (numRooms - 1) / 2;

        topology.nodes.forEach((node, idx) => {
            positions[node.id] = {
                x: (idx - midpoint) * spacing,
                y: 0,
                z: 0
            };
        });
    } else if (topologyName.startsWith('star')) {
        // Central room with all other rooms around it
        const radius = Math.max(10, numRooms * 1.1);

        topology.nodes.forEach((node, idx) => {
            if (idx === 0) {
                positions[node.id] = { x: 0, y: 0, z: 0 };
                return;
            }

            const angle = ((idx - 1) / (numRooms - 1)) * Math.PI * 2;
            positions[node.id] = {
                x: Math.cos(angle) * radius,
                y: 0,
                z: Math.sin(angle) * radius
            };
        });
    } else if (topologyName.startsWith('fully_connected')) {
        // Circular layout keeps the dense complete graph readable
        const radius = Math.max(10, numRooms * 1.2);

        topology.nodes.forEach((node, idx) => {
            const angle = (idx / numRooms) * Math.PI * 2;
            positions[node.id] = {
                x: Math.cos(angle) * radius,
                y: 0,
                z: Math.sin(angle) * radius
            };
        });
    } else if (topologyName.startsWith('bus')) {
        // Central corridor with rooms branching on both sides
        const corridorLength = Math.max(2, Math.floor(Math.sqrt(numRooms)));
        const corridorSpacing = 8;
        const sideSpacing = 7;
        const midpoint = (corridorLength - 1) / 2;

        topology.nodes.forEach((node, idx) => {
            if (idx < corridorLength) {
                positions[node.id] = {
                    x: (idx - midpoint) * corridorSpacing,
                    y: 0,
                    z: 0
                };
                return;
            }

            const offset = idx - corridorLength;
            const corridorIdx = offset % corridorLength;
            const branchIdx = Math.floor(offset / corridorLength);
            const side = branchIdx % 2 === 0 ? -1 : 1;
            const depth = Math.floor(branchIdx / 2) + 1;

            positions[node.id] = {
                x: (corridorIdx - midpoint) * corridorSpacing,
                y: 0,
                z: side * depth * sideSpacing
            };
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

function calculateGUH73Positions(topology) {
    const positions = {};
    const S = 6; // Spacing unit

    // Helper to set position
    const setPos = (id, x, z) => {
        positions[id] = { x: x * S, y: 0, z: z * S };
    };

    // --- Main Spine (0-17) ---
    for (let i = 0; i <= 17; i++) {
        setPos(i, i, 0);
    }

    // --- Upper Row (23-38) ---
    // 23 is above 0, 38 is above 15
    for (let i = 23; i <= 38; i++) {
        setPos(i, i - 23, -1);
    }

    // --- Right Section (Elevators/Stairs) ---
    // 39 connects to 16, 17. Placed between them but up.
    setPos(39, 16.5, -1.5);
    setPos(40, 16, -2.5);
    setPos(41, 17, -2.5);

    // --- Lower Section ---

    // Leftmost (below 0-2)
    setPos(42, 0, 1);
    setPos(43, 0, 2);
    setPos(44, 1, 1);
    setPos(45, 2, 1);
    setPos(46, 2.5, 2);

    // Cluster below 4-6
    setPos(47, 4, 1);
    setPos(48, 4, 2);
    setPos(49, 3, 2);
    setPos(50, 5, 1.5);
    setPos(51, 6, 2);
    setPos(53, 6, 3); // 53 below 51
    setPos(52, 7, 2); // 52 connects to 51 and 19

    setPos(54, 6, 1); // Below 6
    setPos(55, 7, 1); // Below 7

    // Vertical Spine (8 -> 18 -> 19 -> 20 -> 21 -> 22)
    setPos(18, 8, 1);
    setPos(19, 8, 2);
    setPos(20, 8, 3);
    setPos(21, 8, 4);
    setPos(22, 8, 5.5); // Gap for 21-22 corridor

    // Bottom Cluster (67-69 below 22)
    setPos(67, 7, 6.5);
    setPos(68, 8, 6.5);
    setPos(69, 9, 6.5);

    // Horizontal offshoot from 20 (70-72)
    setPos(70, 9, 3);
    setPos(71, 10, 3);
    setPos(72, 11, 3);

    // Middle Right (below 9-12)
    setPos(56, 9, 1);
    setPos(57, 10, 2);
    setPos(58, 11, 1);
    setPos(59, 12, 2);
    setPos(60, 11, 2);

    // Below 13-14
    setPos(61, 13, 2);
    setPos(62, 14, 1);
    setPos(63, 15, 1.5);
    setPos(64, 14.5, 2.5);

    // Source Area (below 16-17)
    setPos(65, 16, 1);
    setPos(66, 17, 1); // Source Room

    // Fill in any missing nodes with a default fallback (just in case)
    topology.nodes.forEach(node => {
        if (!positions[node.id]) {
            positions[node.id] = { x: 0, y: 0, z: 0 };
        }
    });

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
