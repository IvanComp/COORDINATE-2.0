import React, { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera, Text } from '@react-three/drei';
import * as THREE from 'three';
import { Box } from '@mui/material';
import { calculateCorridors, calculateRoomPositions } from './layoutUtils';

function Chamber({ position, label, tone, isSpecial }) {
    return (
        <group position={[position.x, position.y, position.z]}>
            <mesh receiveShadow>
                <cylinderGeometry args={[2.6, 3.1, 1.4, 8]} />
                <meshStandardMaterial color={tone} roughness={0.92} metalness={0.1} />
            </mesh>
            <mesh position={[0, 0.85, 0]}>
                <cylinderGeometry args={[1.6, 1.6, 0.2, 8]} />
                <meshStandardMaterial color={isSpecial ? '#f2ddaf' : '#c9ab74'} emissive={isSpecial ? '#8f6b2b' : '#000000'} emissiveIntensity={0.35} />
            </mesh>
            <Text position={[0, 1.8, 0]} fontSize={0.55} color="white" anchorX="center" anchorY="middle">
                {label}
            </Text>
        </group>
    );
}

function Corridor({ start, end }) {
    const vector = new THREE.Vector3(end.x - start.x, end.y - start.y, end.z - start.z);
    const length = vector.length();
    const midpoint = [(start.x + end.x) / 2, 0.1, (start.z + end.z) / 2];
    const angle = Math.atan2(vector.z, vector.x);

    return (
        <mesh position={midpoint} rotation={[0, -angle, 0]} receiveShadow>
            <boxGeometry args={[length, 0.3, 1.2]} />
            <meshStandardMaterial color="#503820" roughness={0.96} />
        </mesh>
    );
}

function Ant({ ant, positions }) {
    const ref = useRef();
    const current = useRef(null);
    const target = positions[ant.position];
    const sleepMarkerRef = useRef(null);

    if (!target) return null;
    if (!current.current) current.current = { ...target };

    useFrame((state, delta) => {
        current.current.x += (target.x - current.current.x) * Math.min(1, delta * 4);
        current.current.y += (target.y - current.current.y) * Math.min(1, delta * 4);
        current.current.z += (target.z - current.current.z) * Math.min(1, delta * 4);
        if (ref.current) {
            ref.current.position.set(current.current.x, 1.2, current.current.z);
        }
        if (sleepMarkerRef.current && ant.state === 'sleeping') {
            const bob = Math.sin(state.clock.elapsedTime * 2.2) * 0.18;
            sleepMarkerRef.current.position.y = 1.45 + bob;
        }
    });

    const color = ant.state === 'dead'
        ? '#f08b7f'
        : ant.state === 'sleeping'
            ? '#a7b4cf'
            : ant.state === 'mating'
                ? '#cf95e8'
                : ant.sex === 'F'
                    ? '#f28bb3'
                    : '#7ca6ff';

    return (
        <group ref={ref} position={[target.x, 1.2, target.z]}>
            <mesh castShadow>
                <sphereGeometry args={[0.42, 18, 18]} />
                <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.25} />
            </mesh>
            <mesh position={[0.45, 0, 0]}>
                <sphereGeometry args={[0.28, 16, 16]} />
                <meshStandardMaterial color={color} />
            </mesh>
            <mesh position={[-0.45, 0, 0]}>
                <sphereGeometry args={[0.28, 16, 16]} />
                <meshStandardMaterial color={color} />
            </mesh>
            <Text position={[0, 0.9, 0]} fontSize={0.28} color="white" anchorX="center" anchorY="middle">
                {ant.id}
            </Text>
            {ant.state === 'sleeping' && (
                <Text
                    ref={sleepMarkerRef}
                    position={[0.7, 1.45, 0]}
                    fontSize={0.34}
                    color="#f6f3ff"
                    anchorX="center"
                    anchorY="middle"
                >
                    ZzZ
                </Text>
            )}
        </group>
    );
}

function Scene({ topology, topologyName, ants, specialChambers }) {
    const positions = useMemo(() => calculateRoomPositions(topology, topologyName), [topology, topologyName]);
    const corridors = useMemo(() => calculateCorridors(topology, positions), [topology, positions]);

    const chamberTone = (id) => {
        if (id === specialChambers.nest) return '#8b5a2b';
        if (specialChambers.food.includes(id)) return '#5d7b39';
        if (specialChambers.water.includes(id)) return '#366b8b';
        if (id === specialChambers.nursery) return '#765185';
        if (specialChambers.rest.includes(id)) return '#4f5565';
        return '#6e4b2a';
    };

    return (
        <>
            <PerspectiveCamera makeDefault position={[0, 55, 50]} fov={50} />
            <ambientLight intensity={1.4} />
            <directionalLight position={[20, 35, 10]} intensity={1.4} castShadow />
            <pointLight position={[-20, 20, -10]} intensity={0.6} color="#ffddaa" />

            <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow position={[0, -0.8, 0]}>
                <planeGeometry args={[220, 220]} />
                <meshStandardMaterial color="#24180f" />
            </mesh>

            {corridors.map((corridor) => (
                <Corridor key={`${corridor.source}-${corridor.target}`} start={corridor.start} end={corridor.end} />
            ))}

            {topology?.nodes?.map((node) => (
                <Chamber
                    key={node.id}
                    position={positions[node.id]}
                    label={node.id}
                    tone={chamberTone(node.id)}
                    isSpecial={node.id === specialChambers.nest || node.id === specialChambers.nursery}
                />
            ))}

            {Object.values(ants || {}).filter((ant) => ant.alive !== false).map((ant) => (
                <Ant key={ant.id} ant={ant} positions={positions} />
            ))}

            <OrbitControls enablePan enableZoom enableRotate />
        </>
    );
}

function Visualizer({ topology, topologyName, ants, specialChambers }) {
    return (
        <Box sx={{ position: 'absolute', inset: 0 }}>
            <Canvas shadows gl={{ antialias: true }}>
                <Scene topology={topology} topologyName={topologyName} ants={ants} specialChambers={specialChambers} />
            </Canvas>
        </Box>
    );
}

export default Visualizer;
