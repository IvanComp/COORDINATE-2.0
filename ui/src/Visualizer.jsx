import React, { useMemo, useRef, useState, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Grid, PerspectiveCamera, Text, Billboard } from '@react-three/drei';
import { Box } from '@mui/material';
import * as THREE from 'three';
import { calculateRoomPositions, calculateCorridors } from './layoutUtils';

// Delivery Stamp Animation Component
function DeliveryStamp({ position, timestamp }) {
    const groupRef = useRef();
    const [opacity, setOpacity] = useState(1);
    const [yOffset, setYOffset] = useState(0);

    useFrame((state, delta) => {
        // Animate upward and fade out over 2 seconds
        const elapsed = (state.clock.getElapsedTime() * 1000 - timestamp) / 1000;
        if (elapsed < 2) {
            setYOffset(elapsed * 2); // Move up 4 units over 2 seconds
            setOpacity(1 - elapsed / 2); // Fade out over 2 seconds
        }
    });

    if (opacity <= 0) return null;

    return (
        <group ref={groupRef} position={[position.x, position.y + 2 + yOffset, position.z]}>
            <Text
                fontSize={1.2}
                color="#4CAF50"
                anchorX="center"
                anchorY="middle"
                outlineWidth={0.1}
                outlineColor="#000000"
                fillOpacity={opacity}
                outlineOpacity={opacity}
            >
                Delivered!
            </Text>
        </group>
    );
}

// 3D Room Component with realistic walls
function Room({ position, isSource, hasItems, itemCount, roomId }) {
    const meshRef = useRef();

    const floorColor = isSource ? '#2d5016' : '#1a3a52';
    const wallColor = isSource ? '#4CAF50' : '#2196F3';
    const emissive = isSource ? '#2E7D32' : '#1565C0';

    // Memoize text components to prevent flickering on camera movement
    const sourceRoomLabel = useMemo(() => {
        if (!isSource) return null;
        return (
            <Text
                position={[0, 2.5, -2.85]}
                fontSize={0.4}
                color="white"
                anchorX="center"
                anchorY="middle"
                outlineWidth={0.02}
                outlineColor="#000000"
            >
                SOURCE ROOM
            </Text>
        );
    }, [isSource]);

    const roomNumberLabel = useMemo(() => {
        return (
            <Text
                position={[2.2, 0.1, -2.2]}
                rotation={[-Math.PI / 2, 0, 0]}
                fontSize={0.8}
                color="white"
                fillOpacity={0.6}
                anchorX="center"
                anchorY="middle"
            >
                {roomId}
            </Text>
        );
    }, [roomId]);

    return (
        <group position={[position.x, position.y, position.z]}>
            {/* Floor with grid pattern */}
            <mesh position={[0, 0.05, 0]} receiveShadow>
                <boxGeometry args={[5.8, 0.1, 5.8]} />
                <meshStandardMaterial
                    color={floorColor}
                    roughness={0.8}
                    metalness={0.2}
                />
            </mesh>

            {/* Wall frames - only corner posts and top beams for open view */}
            {/* Corner posts */}
            <mesh position={[-2.9, 1.5, -2.9]} castShadow>
                <boxGeometry args={[0.2, 3, 0.2]} />
                <meshStandardMaterial color={wallColor} metalness={0.3} roughness={0.7} />
            </mesh>
            <mesh position={[2.9, 1.5, -2.9]} castShadow>
                <boxGeometry args={[0.2, 3, 0.2]} />
                <meshStandardMaterial color={wallColor} metalness={0.3} roughness={0.7} />
            </mesh>
            <mesh position={[-2.9, 1.5, 2.9]} castShadow>
                <boxGeometry args={[0.2, 3, 0.2]} />
                <meshStandardMaterial color={wallColor} metalness={0.3} roughness={0.7} />
            </mesh>
            <mesh position={[2.9, 1.5, 2.9]} castShadow>
                <boxGeometry args={[0.2, 3, 0.2]} />
                <meshStandardMaterial color={wallColor} metalness={0.3} roughness={0.7} />
            </mesh>

            {/* Top beams connecting corners */}
            <mesh position={[0, 3, -2.9]} castShadow>
                <boxGeometry args={[5.8, 0.2, 0.2]} />
                <meshStandardMaterial color={wallColor} metalness={0.3} roughness={0.7} />
            </mesh>
            <mesh position={[0, 3, 2.9]} castShadow>
                <boxGeometry args={[5.8, 0.2, 0.2]} />
                <meshStandardMaterial color={wallColor} metalness={0.3} roughness={0.7} />
            </mesh>
            <mesh position={[-2.9, 3, 0]} castShadow>
                <boxGeometry args={[0.2, 0.2, 5.8]} />
                <meshStandardMaterial color={wallColor} metalness={0.3} roughness={0.7} />
            </mesh>
            <mesh position={[2.9, 3, 0]} castShadow>
                <boxGeometry args={[0.2, 0.2, 5.8]} />
                <meshStandardMaterial color={wallColor} metalness={0.3} roughness={0.7} />
            </mesh>

            {/* Glass/transparent wall panels */}
            <mesh position={[0, 1.5, -2.9]} castShadow>
                <boxGeometry args={[5.6, 2.8, 0.1]} />
                <meshStandardMaterial
                    color={wallColor}
                    transparent
                    opacity={0.15}
                    emissive={emissive}
                    emissiveIntensity={0.3}
                    roughness={0.1}
                    metalness={0.9}
                />
            </mesh>
            <mesh position={[0, 1.5, 2.9]} castShadow>
                <boxGeometry args={[5.6, 2.8, 0.1]} />
                <meshStandardMaterial
                    color={wallColor}
                    transparent
                    opacity={0.15}
                    emissive={emissive}
                    emissiveIntensity={0.3}
                    roughness={0.1}
                    metalness={0.9}
                />
            </mesh>
            <mesh position={[-2.9, 1.5, 0]} castShadow>
                <boxGeometry args={[0.1, 2.8, 5.6]} />
                <meshStandardMaterial
                    color={wallColor}
                    transparent
                    opacity={0.15}
                    emissive={emissive}
                    emissiveIntensity={0.3}
                    roughness={0.1}
                    metalness={0.9}
                />
            </mesh>
            <mesh position={[2.9, 1.5, 0]} castShadow>
                <boxGeometry args={[0.1, 2.8, 5.6]} />
                <meshStandardMaterial
                    color={wallColor}
                    transparent
                    opacity={0.15}
                    emissive={emissive}
                    emissiveIntensity={0.3}
                    roughness={0.1}
                    metalness={0.9}
                />
            </mesh>

            {/* Source Room Label - attached to back wall */}
            {sourceRoomLabel}

            {/* Room Number on Floor (Visible) */}
            {roomNumberLabel}
        </group>
    );
}

// 3D Robot Component with smooth movement
function Robot({ id, position, hasItem, itemImportance, isFailed, isRescuing, lastDeliveryTime, lastFailTime, lastRescueTime }) {
    const groupRef = useRef();
    const itemRef = useRef();
    const currentPosRef = useRef({ ...position });
    const itemScaleRef = useRef(hasItem ? 1 : 0);

    // Smooth movement animation
    useFrame((_, delta) => {
        if (!groupRef.current) return;

        // Interpolate position for smooth movement
        const lerpFactor = Math.min(delta * 3, 1); // Smooth interpolation
        currentPosRef.current.x += (position.x - currentPosRef.current.x) * lerpFactor;
        currentPosRef.current.y += (position.y - currentPosRef.current.y) * lerpFactor;
        currentPosRef.current.z += (position.z - currentPosRef.current.z) * lerpFactor;

        // Animate item pickup/drop
        const targetScale = hasItem ? 1 : 0;
        const scaleDelta = (targetScale - itemScaleRef.current) * delta * 5;
        itemScaleRef.current = Math.abs(targetScale - itemScaleRef.current) < 0.01
            ? targetScale
            : itemScaleRef.current + scaleDelta;

        // Update group position - Lift up by 0.5 to sit on floor
        groupRef.current.position.set(
            currentPosRef.current.x,
            currentPosRef.current.y + 0.5,
            currentPosRef.current.z
        );

        if (itemRef.current) {
            itemRef.current.scale.set(itemScaleRef.current, itemScaleRef.current, itemScaleRef.current);
        }
    });

    const now = Date.now();
    const deliveryElapsed = lastDeliveryTime ? (now - lastDeliveryTime) / 1000 : Infinity;
    const failElapsed = lastFailTime ? (now - lastFailTime) / 1000 : Infinity;
    const rescueElapsed = lastRescueTime ? (now - lastRescueTime) / 1000 : Infinity;
    const deliveryTextOpacity = deliveryElapsed < 2 ? (1 - deliveryElapsed / 2) : 0;
    const deliveryTextOffset = deliveryElapsed < 2 ? deliveryElapsed * 1.5 : 0;
    const failTextOpacity = failElapsed < 2 ? (1 - failElapsed / 2) : 0;
    const failTextOffset = failElapsed < 2 ? failElapsed * 1.5 : 0;
    const rescueTextOpacity = rescueElapsed < 2 ? (1 - rescueElapsed / 2) : 0;
    const rescueTextOffset = rescueElapsed < 2 ? rescueElapsed * 1.5 : 0;

    // Robot colors: Blue (rescuing), Red (failed), Green (carrying), Gray (idle)
    const bodyColor = isFailed ? '#F44336' : (isRescuing ? '#2196F3' : (hasItem ? '#4CAF50' : '#9E9E9E'));

    return (
        <group ref={groupRef} position={[position.x, 0.5, position.z]}>
            {/* Robot ID Label */}
            <Billboard
                position={[0, 1.8, 0]}
                follow={true}
                lockX={false}
                lockY={false}
                lockZ={false}
            >
                <Text
                    fontSize={0.4}
                    color="white"
                    anchorX="center"
                    anchorY="middle"
                    outlineWidth={0.04}
                    outlineColor="#000000"
                    renderOrder={9999}
                    depthTest={false}
                    material-depthTest={false}
                    material-toneMapped={false}
                >
                    {id}
                </Text>
            </Billboard>

            {/* Delivery Text Animation */}
            {deliveryTextOpacity > 0 && (
                <Billboard
                    position={[0, 2.5 + deliveryTextOffset, 0]}
                    follow={true}
                    lockX={false}
                    lockY={false}
                    lockZ={false}
                >
                    <Text
                        fontSize={1.3}
                        color="#4CAF50"
                        anchorX="center"
                        anchorY="middle"
                        outlineWidth={0.08}
                        outlineColor="#000000"
                        fillOpacity={deliveryTextOpacity}
                        outlineOpacity={deliveryTextOpacity}
                        fontWeight="bold"
                    >
                        Delivered!
                    </Text>
                </Billboard>
            )}

            {/* Fail Text Animation */}
            {failTextOpacity > 0 && (
                <Billboard
                    position={[0, 2.5 + failTextOffset, 0]}
                    follow={true}
                    lockX={false}
                    lockY={false}
                    lockZ={false}
                >
                    <Text
                        fontSize={1.3}
                        color="#F44336"
                        anchorX="center"
                        anchorY="middle"
                        outlineWidth={0.08}
                        outlineColor="#000000"
                        fillOpacity={failTextOpacity}
                        outlineOpacity={failTextOpacity}
                        fontWeight="bold"
                    >
                        Fail!
                    </Text>
                </Billboard>
            )}

            {/* Rescue Text Animation */}
            {rescueTextOpacity > 0 && (
                <Billboard
                    position={[0, 2.5 + rescueTextOffset, 0]}
                    follow={true}
                    lockX={false}
                    lockY={false}
                    lockZ={false}
                >
                    <Text
                        fontSize={1.3}
                        color="#2196F3"
                        anchorX="center"
                        anchorY="middle"
                        outlineWidth={0.08}
                        outlineColor="#000000"
                        fillOpacity={rescueTextOpacity}
                        outlineOpacity={rescueTextOpacity}
                        fontWeight="bold"
                    >
                        Recovered
                    </Text>
                </Billboard>
            )}

            {/* Robot body (box) */}
            <mesh castShadow>
                <boxGeometry args={[0.8, 1.0, 0.8]} />
                <meshStandardMaterial color={bodyColor} metalness={0.3} roughness={0.7} />
            </mesh>

            {/* Robot head (sphere) */}
            <mesh position={[0, 0.7, 0]} castShadow>
                <sphereGeometry args={[0.4, 16, 16]} />
                <meshStandardMaterial color={bodyColor} metalness={0.5} roughness={0.5} />
            </mesh>

            {/* Eyes */}
            <mesh position={[0.18, 0.75, 0.32]} castShadow>
                <sphereGeometry args={[0.07, 8, 8]} />
                <meshStandardMaterial color="#ffffff" emissive="#ffffff" emissiveIntensity={0.5} />
            </mesh>
            <mesh position={[-0.18, 0.75, 0.32]} castShadow>
                <sphereGeometry args={[0.07, 8, 8]} />
                <meshStandardMaterial color="#ffffff" emissive="#ffffff" emissiveIntensity={0.5} />
            </mesh>

            {/* Item indicator with scale animation */}
            {!isFailed && (() => {
                const colors = ['#4CAF50', '#FFC107', '#FF5722'];
                const itemColor = colors[itemImportance] || '#9E9E9E';
                return (
                    <mesh ref={itemRef} position={[0, 1.4, 0]} scale={[itemScaleRef.current, itemScaleRef.current, itemScaleRef.current]} castShadow>
                        <boxGeometry args={[0.5, 0.5, 0.5]} />
                        <meshStandardMaterial color={itemColor} />
                    </mesh>
                );
            })()}

            {/* Failure indicator */}
            {isFailed && (
                <mesh position={[0, 1.4, 0]} castShadow>
                    <coneGeometry args={[0.4, 0.7, 3]} />
                    <meshStandardMaterial color="#FF5722" emissive="#FF5722" emissiveIntensity={0.5} />
                </mesh>
            )}
        </group>
    );
}

// 3D Item Component with smooth appear/disappear
function Item({ position, importance, isNew }) {
    const meshRef = useRef();
    const scaleRef = useRef(isNew ? 0 : 1);
    const colors = ['#4CAF50', '#FFC107', '#FF5722'];
    const color = colors[importance] || '#9E9E9E';

    // Smooth scale animation for appearing
    useFrame((_, delta) => {
        if (!meshRef.current) return;
        if (scaleRef.current < 1) {
            scaleRef.current = Math.min(scaleRef.current + delta * 3, 1);
            meshRef.current.scale.set(scaleRef.current, scaleRef.current, scaleRef.current);
        }
    });

    return (
        <mesh
            ref={meshRef}
            position={[position.x, 0.3, position.z]}
            scale={[scaleRef.current, scaleRef.current, scaleRef.current]}
            castShadow
        >
            <boxGeometry args={[0.5, 0.5, 0.5]} />
            <meshStandardMaterial color={color} metalness={0.2} roughness={0.8} />
        </mesh>
    );
}

// Corridor Component - realistic walkway between rooms
function Corridor({ start, end }) {
    const midpoint = {
        x: (start.x + end.x) / 2,
        y: 0.15,
        z: (start.z + end.z) / 2
    };

    const length = Math.sqrt(
        Math.pow(end.x - start.x, 2) +
        Math.pow(end.z - start.z, 2)
    );

    const angle = Math.atan2(end.z - start.z, end.x - start.x);

    return (
        <group position={[midpoint.x, 0, midpoint.z]} rotation={[0, angle, 0]}>
            {/* Corridor floor */}
            <mesh position={[0, 0.1, 0]} receiveShadow>
                <boxGeometry args={[length, 0.1, 2]} />
                <meshStandardMaterial
                    color="#3a3a3a"
                    roughness={0.7}
                    metalness={0.3}
                />
            </mesh>

            {/* Side rails/guides */}
            <mesh position={[0, 0.3, -0.95]} castShadow>
                <boxGeometry args={[length, 0.1, 0.1]} />
                <meshStandardMaterial color="#666666" metalness={0.5} roughness={0.5} />
            </mesh>
            <mesh position={[0, 0.3, 0.95]} castShadow>
                <boxGeometry args={[length, 0.1, 0.1]} />
                <meshStandardMaterial color="#666666" metalness={0.5} roughness={0.5} />
            </mesh>

            {/* Support posts every few units */}
            {Array.from({ length: Math.floor(length / 3) }).map((_, i) => {
                const offset = (i - Math.floor(length / 6)) * 3;
                return (
                    <React.Fragment key={i}>
                        <mesh position={[offset, 0.5, -0.95]} castShadow>
                            <boxGeometry args={[0.1, 1, 0.1]} />
                            <meshStandardMaterial color="#555555" metalness={0.4} roughness={0.6} />
                        </mesh>
                        <mesh position={[offset, 0.5, 0.95]} castShadow>
                            <boxGeometry args={[0.1, 1, 0.1]} />
                            <meshStandardMaterial color="#555555" metalness={0.4} roughness={0.6} />
                        </mesh>
                    </React.Fragment>
                );
            })}
        </group>
    );
}

function Visualizer({ topology, robots, items, topologyName = 'mesh25', logs = [], simTime = 0 }) {
    const [deliveredStamps, setDeliveredStamps] = useState([]);
    const [robotDeliveryTimes, setRobotDeliveryTimes] = useState({});
    const [robotFailTimes, setRobotFailTimes] = useState({});
    const [robotRescueTimes, setRobotRescueTimes] = useState({});
    const prevItemsRef = useRef({});
    const prevRobotsRef = useRef({});
    const prevSimTimeRef = useRef(0);

    const roomPositions = useMemo(() => {
        return calculateRoomPositions(topology, topologyName);
    }, [topology, topologyName]);

    const corridors = useMemo(() => {
        return calculateCorridors(topology, roomPositions);
    }, [topology, roomPositions]);

    // Track delivered items and robot failures from logs
    useEffect(() => {
        // Only run if topology is loaded and roomPositions are available
        if (!topology || !roomPositions || Object.keys(roomPositions).length === 0) {
            return;
        }

        const prevItems = prevItemsRef.current;
        const prevRobots = prevRobotsRef.current;
        const prevSimTime = prevSimTimeRef.current;
        const currentTime = Date.now();

        // Track deliveries
        Object.values(items).forEach(item => {
            const prevItem = prevItems[item.id];
            // Check if item was just delivered
            if (prevItem && prevItem.status !== 'delivered' && item.status === 'delivered') {
                // Get the source room position (room 0)
                const sourcePos = roomPositions[0];
                if (sourcePos) {
                    setDeliveredStamps(prev => [...prev, {
                        id: `${item.id}-${currentTime}`,
                        position: sourcePos,
                        timestamp: currentTime
                    }]);

                    // Find which robot delivered it
                    const deliveringRobot = Object.values(prevRobots).find(r => r.item === item.id);
                    if (deliveringRobot) {
                        setRobotDeliveryTimes(prev => ({
                            ...prev,
                            [deliveringRobot.id]: currentTime
                        }));
                    }
                }
            }
        });

        // Track robot failures and rescues from logs
        // Look for events that just happened (between prevSimTime and current simTime)
        if (logs && logs.length > 0) {
            logs.forEach(event => {
                if (event.simTime > prevSimTime && event.simTime <= simTime) {
                    const robotId = event.robotId;
                    if (robotId !== -1) {
                        if (event.event === 'fail') {
                            setRobotFailTimes(prev => ({
                                ...prev,
                                [robotId]: currentTime
                            }));
                        } else if (event.event === 'recover' || event.event === 'recovery' || event.event === 'rescue') {
                            setRobotRescueTimes(prev => ({
                                ...prev,
                                [robotId]: currentTime
                            }));
                        }
                    }
                }
            });
        }
        // Also handle persistent failure state from robots object
        Object.values(robots).forEach(robot => {
            if (robot.failed) {
                // If we don't already have a fail timestamp for this robot, set it now
                setRobotFailTimes(prev => {
                    if (prev[robot.id] !== undefined) return prev;
                    return { ...prev, [robot.id]: currentTime };
                });
            }
        });

        // Clean up old stamps (older than 3 seconds)
        setDeliveredStamps(prev => prev.filter(stamp => currentTime - stamp.timestamp < 3000));

        prevItemsRef.current = { ...items };
        prevRobotsRef.current = { ...robots };
        prevSimTimeRef.current = simTime;
    }, [items, robots, roomPositions, topology, logs, simTime]);

    if (!topology) {
        return (
            <Box sx={{
                width: '100%',
                height: '100%',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center'
            }}>
                Loading topology...
            </Box>
        );
    }

    return (
        <Box sx={{ width: '100%', height: '100%' }}>
            <Canvas shadows>
                <PerspectiveCamera makeDefault position={[20, 20, 20]} fov={60} />
                <OrbitControls
                    enablePan={true}
                    enableZoom={true}
                    enableRotate={true}
                    minDistance={5}
                    maxDistance={100}
                />

                {/* Lighting */}
                <ambientLight intensity={0.4} />
                <directionalLight
                    position={[10, 20, 10]}
                    intensity={1}
                    castShadow
                    shadow-mapSize-width={2048}
                    shadow-mapSize-height={2048}
                />
                <pointLight position={[-10, 10, -10]} intensity={0.5} />

                {/* Ground Grid */}
                <Grid
                    args={[100, 100]}
                    cellSize={2}
                    cellThickness={0.5}
                    cellColor="#6f6f6f"
                    sectionSize={10}
                    sectionThickness={1}
                    sectionColor="#9d4b4b"
                    fadeDistance={100}
                    fadeStrength={1}
                    followCamera={false}
                    infiniteGrid={true}
                />

                {/* Corridors */}
                {corridors.map((corridor, idx) => (
                    <Corridor key={`corridor-${idx}`} start={corridor.start} end={corridor.end} />
                ))}

                {/* Rooms */}
                {topology.nodes.map(node => {
                    const pos = roomPositions[node.id];
                    if (!pos) return null;

                    const roomItems = Object.values(items).filter(
                        item => item.position === node.id && item.status === 'available'
                    );

                    return (
                        <Room
                            key={`room-${node.id}`}
                            position={pos}
                            isSource={node.id === 0}
                            hasItems={roomItems.length > 0}
                            itemCount={roomItems.length}
                            roomId={node.id}
                        />
                    );
                })}

                {/* Items */}
                {Object.values(items).map(item => {
                    if (item.status !== 'available' || item.position === -1) return null;

                    const roomPos = roomPositions[item.position];
                    if (!roomPos) return null;

                    const offset = (item.id % 5) * 0.6 - 1.2;

                    return (
                        <Item
                            key={`item-${item.id}`}
                            position={{ x: roomPos.x + offset, y: roomPos.y, z: roomPos.z }}
                            importance={item.importance}
                        />
                    );
                })}

                {/* Robots */}
                {Object.values(robots).map(robot => {
                    if (robot.position === -1) return null;

                    const roomPos = roomPositions[robot.position];
                    if (!roomPos) return null;

                    // Calculate index of this robot in its room
                    const roomRobots = Object.values(robots)
                        .filter(r => r.position === robot.position)
                        .sort((a, b) => a.id - b.id);
                    const index = roomRobots.findIndex(r => r.id === robot.id);

                    // Calculate offset based on room type
                    let offsetX = 0;
                    let offsetZ = 0;

                    if (robot.position === 0) {
                        // Source room: Grid layout
                        const cols = 4;
                        const row = Math.floor(index / cols);
                        const col = index % cols;
                        offsetX = (col - 1.5) * 0.8;
                        offsetZ = (row - 1.5) * 0.8;
                    } else {
                        // Other rooms: Simple line or smaller grid
                        offsetX = (index % 3) * 0.6 - 0.6;
                        offsetZ = Math.floor(index / 3) * 0.6 - 0.6;
                    }

                    return (
                        <Robot
                            key={`robot-${robot.id}`}
                            id={robot.id}
                            position={{ x: roomPos.x + offsetX, y: roomPos.y, z: roomPos.z + offsetZ }}
                            hasItem={robot.item !== null}
                            itemImportance={robot.itemImportance}
                            isFailed={robot.failed || false}
                            isRescuing={robot.rescuing || false}
                            lastDeliveryTime={robotDeliveryTimes[robot.id]}
                            lastFailTime={robotFailTimes[robot.id]}
                            lastRescueTime={robotRescueTimes[robot.id]}
                        />
                    );
                })}

                {/* Delivery Stamps */}
                {deliveredStamps.map(stamp => (
                    <DeliveryStamp
                        key={stamp.id}
                        position={stamp.position}
                        timestamp={stamp.timestamp}
                    />
                ))}
            </Canvas>
        </Box>
    );
}

export default Visualizer;
