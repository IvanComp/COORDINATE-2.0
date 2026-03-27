import React, { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera, Text } from '@react-three/drei';
import * as THREE from 'three';
import { Box, Stack, Typography } from '@mui/material';
import { calculateRoomPositions } from './layoutUtils';

function seededNoise(seed) {
    const value = Math.sin(seed * 91.173) * 43758.5453123;
    return value - Math.floor(value);
}

function statusTint(ant) {
    if (ant.state === 'dead') return '#7b5954';
    if (ant.state === 'sleeping') return '#9a8bc9';
    if (ant.state === 'mating') return '#cf95e8';
    return ant.sex === 'F' ? '#f28bb3' : '#7ca6ff';
}

function mixHex(colorA, colorB, ratio = 0.5) {
    const a = colorA.replace('#', '');
    const b = colorB.replace('#', '');
    const clamp = Math.max(0, Math.min(1, ratio));
    const mix = [0, 2, 4].map((index) => {
        const av = Number.parseInt(a.slice(index, index + 2), 16);
        const bv = Number.parseInt(b.slice(index, index + 2), 16);
        return Math.round((av * (1 - clamp)) + (bv * clamp)).toString(16).padStart(2, '0');
    });
    return `#${mix.join('')}`;
}

function buildAppearance(ant) {
    const seed = Number(ant.id || 0) + (Number(ant.generation || 0) * 17);
    return {
        shellMix: 0.64 + (seededNoise(seed + 1) * 0.18),
        accentMix: 0.12 + (seededNoise(seed + 2) * 0.28),
        stripeScale: 0.6 + (seededNoise(seed + 3) * 0.35),
        antennaTilt: 0.32 + (seededNoise(seed + 4) * 0.4),
        legSpread: 3.15 + (seededNoise(seed + 5) * 0.7),
        eyeScale: 0.85 + (seededNoise(seed + 6) * 0.4),
        bodyLean: (seededNoise(seed + 7) - 0.5) * 0.14,
    };
}

function GroundDecor({ positions }) {
    const props = useMemo(() => {
        const center = Object.values(positions || {});
        const tufts = [];
        center.forEach((position, index) => {
            for (let tuft = 0; tuft < 5; tuft += 1) {
                const seed = (index * 11) + tuft;
                tufts.push({
                    id: `grass-${index}-${tuft}`,
                    x: position.x + ((seededNoise(seed + 3) - 0.5) * 18),
                    z: position.z + ((seededNoise(seed + 30) - 0.5) * 18),
                    scale: 0.55 + (seededNoise(seed + 50) * 0.95),
                    hue: seed % 4,
                });
            }
        });
        for (let ambient = 0; ambient < 48; ambient += 1) {
            tufts.push({
                id: `ambient-${ambient}`,
                x: (seededNoise(ambient + 100) - 0.5) * 120,
                z: (seededNoise(ambient + 180) - 0.5) * 120,
                scale: 0.45 + (seededNoise(ambient + 220) * 0.75),
                hue: ambient % 4,
            });
        }
        return tufts;
    }, [positions]);

    return (
        <>
            {props.map((prop) => (
                <group key={prop.id} position={[prop.x, -0.46, prop.z]} scale={prop.scale}>
                    <mesh rotation={[0, 0, 0.16]}>
                        <coneGeometry args={[0.34, 1.2, 5]} />
                        <meshStandardMaterial color={prop.hue === 0 ? '#77ab59' : prop.hue === 1 ? '#8fbe6a' : '#5f914d'} roughness={1} />
                    </mesh>
                    <mesh rotation={[0, 0, -0.12]}>
                        <coneGeometry args={[0.28, 0.94, 5]} />
                        <meshStandardMaterial color={prop.hue === 2 ? '#96c46d' : '#6f9f51'} roughness={1} />
                    </mesh>
                </group>
            ))}
        </>
    );
}

function NestLandmark({ position, label, glow }) {
    return (
        <group position={[position.x, 0, position.z]}>
            <mesh receiveShadow position={[0, -0.1, 0]}>
                <cylinderGeometry args={[4.6, 5.2, 0.8, 24]} />
                <meshStandardMaterial color="#8a5a33" roughness={1} />
            </mesh>
            <mesh receiveShadow position={[0, 1.2, 0]}>
                <sphereGeometry args={[2.9, 24, 20]} />
                <meshStandardMaterial color="#9f6938" roughness={1} />
            </mesh>
            <mesh position={[0.55, 1.05, 0]}>
                <cylinderGeometry args={[0.56, 0.82, 1.2, 16]} />
                <meshStandardMaterial color="#352115" roughness={1} />
            </mesh>
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
                <ringGeometry args={[4.8, 5.8, 36]} />
                <meshStandardMaterial color={glow} emissive={glow} emissiveIntensity={0.18} transparent opacity={0.55} />
            </mesh>
            <Text position={[0, 4.6, 0]} fontSize={0.95} color="#fff5e1" anchorX="center" anchorY="middle">
                {label}
            </Text>
        </group>
    );
}

function PondLandmark({ position, label, glow }) {
    return (
        <group position={[position.x, 0, position.z]}>
            <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow position={[0, -0.08, 0]}>
                <circleGeometry args={[4.1, 32]} />
                <meshStandardMaterial color="#567a42" roughness={1} />
            </mesh>
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
                <circleGeometry args={[3.2, 32]} />
                <meshStandardMaterial color="#7ad8ea" emissive="#77d8ea" emissiveIntensity={0.2} roughness={0.35} metalness={0.08} />
            </mesh>
            <mesh position={[-1.1, 0.2, 1.3]}>
                <sphereGeometry args={[0.4, 12, 12]} />
                <meshStandardMaterial color="#f1dba3" roughness={1} />
            </mesh>
            <Text position={[0, 2.2, 0]} fontSize={0.82} color="#eefcff" anchorX="center" anchorY="middle">
                {label}
            </Text>
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
                <ringGeometry args={[3.35, 4.1, 36]} />
                <meshStandardMaterial color={glow} emissive={glow} emissiveIntensity={0.18} transparent opacity={0.55} />
            </mesh>
        </group>
    );
}

function FoodLandmark({ position, label, glow }) {
    return (
        <group position={[position.x, 0, position.z]}>
            <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow position={[0, -0.06, 0]}>
                <circleGeometry args={[3.8, 30]} />
                <meshStandardMaterial color="#6d8a43" roughness={1} />
            </mesh>
            {[
                [-0.8, 0.3, -0.3, '#8fbe4e'],
                [0.7, 0.42, 0.2, '#6ea937'],
                [0.15, 0.35, 1.0, '#aacd6f'],
            ].map(([x, y, z, color], index) => (
                <mesh key={index} position={[x, y, z]} rotation={[0, index * 0.6, 0]} castShadow>
                    <coneGeometry args={[0.9, 1.6, 5]} />
                    <meshStandardMaterial color={color} roughness={1} />
                </mesh>
            ))}
            <Text position={[0, 2.45, 0]} fontSize={0.82} color="#f3ffe8" anchorX="center" anchorY="middle">
                {label}
            </Text>
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
                <ringGeometry args={[3.15, 3.95, 36]} />
                <meshStandardMaterial color={glow} emissive={glow} emissiveIntensity={0.18} transparent opacity={0.52} />
            </mesh>
        </group>
    );
}

function NurseryLandmark({ position, label, glow }) {
    return (
        <group position={[position.x, 0, position.z]}>
            <mesh receiveShadow position={[0, 0.2, 0]}>
                <cylinderGeometry args={[3.8, 4.3, 0.5, 24]} />
                <meshStandardMaterial color="#b38759" roughness={1} />
            </mesh>
            {[
                [-1.1, 0.75, 0.2],
                [0.2, 0.65, -0.4],
                [1.0, 0.78, 0.8],
                [-0.1, 0.7, 1.0],
            ].map(([x, y, z], index) => (
                <mesh key={index} position={[x, y, z]} castShadow>
                    <sphereGeometry args={[0.48, 14, 14]} />
                    <meshStandardMaterial color="#f7e7c1" roughness={0.92} />
                </mesh>
            ))}
            <Text position={[0, 2.55, 0]} fontSize={0.82} color="#fff4de" anchorX="center" anchorY="middle">
                {label}
            </Text>
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
                <ringGeometry args={[3.2, 4.05, 36]} />
                <meshStandardMaterial color={glow} emissive={glow} emissiveIntensity={0.16} transparent opacity={0.52} />
            </mesh>
        </group>
    );
}

function RestLandmark({ position, label, glow }) {
    return (
        <group position={[position.x, 0, position.z]}>
            <mesh receiveShadow position={[0, 0, 0]}>
                <cylinderGeometry args={[3.7, 3.9, 0.35, 24]} />
                <meshStandardMaterial color="#78956d" roughness={1} />
            </mesh>
            <mesh receiveShadow position={[0.2, 0.55, 0]}>
                <boxGeometry args={[2.6, 0.45, 1.5]} />
                <meshStandardMaterial color="#6d7f58" roughness={1} />
            </mesh>
            <mesh receiveShadow position={[-1.2, 0.42, 0.8]}>
                <sphereGeometry args={[0.5, 12, 12]} />
                <meshStandardMaterial color="#8e9c7e" roughness={1} />
            </mesh>
            <Text position={[0, 2.25, 0]} fontSize={0.78} color="#f0fff0" anchorX="center" anchorY="middle">
                {label}
            </Text>
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
                <ringGeometry args={[3.0, 3.8, 36]} />
                <meshStandardMaterial color={glow} emissive={glow} emissiveIntensity={0.15} transparent opacity={0.48} />
            </mesh>
        </group>
    );
}

function GenericLandmark({ position }) {
    return (
        <group position={[position.x, 0, position.z]}>
            <mesh receiveShadow position={[0, 0.1, 0]}>
                <cylinderGeometry args={[2.4, 2.8, 0.3, 18]} />
                <meshStandardMaterial color="#9a6739" roughness={1} />
            </mesh>
            <mesh receiveShadow position={[0, 0.6, 0]}>
                <sphereGeometry args={[1.4, 16, 14]} />
                <meshStandardMaterial color="#af7843" roughness={1} />
            </mesh>
        </group>
    );
}

function Ant({ ant, positions, slotOffset }) {
    const ref = useRef();
    const current = useRef(null);
    const sleepMarkerRef = useRef(null);
    const appearance = useMemo(() => buildAppearance(ant), [ant]);

    const anchor = positions[ant.position];
    if (!anchor) return null;
    if (!current.current) current.current = { x: anchor.x, y: 0, z: anchor.z };

    useFrame((state, delta) => {
        const phase = (state.clock.elapsedTime * 0.24) + (ant.id * 0.17);
        const wanderRadius = ant.state === 'sleeping' ? 0.08 : ant.state === 'mating' ? 0.42 : 0.24;
        const livelyFactor = ant.state === 'dead' ? 0 : ant.state === 'sleeping' ? 0.25 : 1;
        const targetX = anchor.x + (slotOffset?.x || 0) + (Math.cos(phase) * wanderRadius * livelyFactor);
        const targetZ = anchor.z + (slotOffset?.z || 0) + (Math.sin((phase * 1.15) + appearance.bodyLean) * wanderRadius * livelyFactor);
        const smoothing = ant.state === 'sleeping' ? 0.55 : 0.72;

        current.current.x += (targetX - current.current.x) * Math.min(1, delta * smoothing);
        current.current.z += (targetZ - current.current.z) * Math.min(1, delta * smoothing);

        if (ref.current) {
            const bob = ant.state === 'dead' ? -0.12 : Math.sin((state.clock.elapsedTime * 3.4) + ant.id) * 0.035;
            ref.current.position.set(current.current.x, 0.72 + bob, current.current.z);
            if (ant.state !== 'dead') {
                ref.current.rotation.y = Math.atan2(targetZ - current.current.z, targetX - current.current.x);
            } else {
                ref.current.rotation.z = Math.PI / 2.8;
            }
        }

        if (sleepMarkerRef.current && ant.state === 'sleeping') {
            sleepMarkerRef.current.position.y = 1.5 + (Math.sin(state.clock.elapsedTime * 1.8) * 0.18);
        }
    });

    const color = statusTint(ant);
    const shellColor = ant.state === 'dead' ? '#503631' : mixHex(color, '#2a1f19', appearance.shellMix);
    const limbColor = ant.state === 'sleeping' ? '#ddd4f4' : mixHex(shellColor, '#eadfc7', 0.18);
    const accentColor = ant.state === 'dead' ? '#7b5954' : mixHex(color, '#ffffff', appearance.accentMix);
    const eyeColor = ant.state === 'sleeping' ? '#efe9ff' : '#0f0b09';
    const stripeColor = ant.state === 'dead' ? '#6b4f49' : color;

    return (
        <group ref={ref} position={[anchor.x, 0.72, anchor.z]}>
            <mesh castShadow position={[-0.45, 0.04, 0]} scale={ant.sex === 'F' ? [1.18, 1.0, 0.9] : [1.06, 0.94, 0.84]}>
                <sphereGeometry args={[0.48, 18, 18]} />
                <meshStandardMaterial color={shellColor} roughness={0.58} metalness={0.08} emissive={shellColor} emissiveIntensity={0.04} />
            </mesh>
            <mesh castShadow position={[-0.49, 0.13, 0]} scale={[0.48 + (appearance.stripeScale * 0.26), 0.2, 0.42 + (appearance.stripeScale * 0.18)]}>
                <sphereGeometry args={[0.34, 16, 16]} />
                <meshStandardMaterial color={stripeColor} roughness={0.7} emissive={stripeColor} emissiveIntensity={0.08} />
            </mesh>
            <mesh castShadow position={[0.02, 0.05, 0]} scale={[1.18, 0.98, 1.02]}>
                <sphereGeometry args={[0.32, 16, 16]} />
                <meshStandardMaterial color={shellColor} roughness={0.52} metalness={0.07} />
            </mesh>
            <mesh castShadow position={[0.5, 0.12, 0]} scale={[0.94, 0.88, 0.9]}>
                <sphereGeometry args={[0.24, 14, 14]} />
                <meshStandardMaterial color={shellColor} roughness={0.46} metalness={0.06} />
            </mesh>
            <mesh castShadow position={[0.66, 0.08, 0]} scale={[0.36, 0.28, 0.52]}>
                <sphereGeometry args={[0.2, 12, 12]} />
                <meshStandardMaterial color={accentColor} roughness={0.76} emissive={accentColor} emissiveIntensity={0.06} />
            </mesh>
            {[-0.28, 0, 0.28].map((offset, index) => (
                <group key={offset} position={[-0.04, -0.04, offset]}>
                    <mesh rotation={[0, 0, Math.PI / (appearance.legSpread + (index * 0.22))]}>
                        <cylinderGeometry args={[0.022, 0.028, 1.08, 8]} />
                        <meshStandardMaterial color={limbColor} />
                    </mesh>
                    <mesh rotation={[0, 0, -Math.PI / (appearance.legSpread + (index * 0.22))]}>
                        <cylinderGeometry args={[0.022, 0.028, 1.08, 8]} />
                        <meshStandardMaterial color={limbColor} />
                    </mesh>
                </group>
            ))}
            <group position={[0.56, 0.24, 0]}>
                <mesh rotation={[appearance.antennaTilt, 0.12, Math.PI / 4.2]}>
                    <cylinderGeometry args={[0.016, 0.018, 0.82, 8]} />
                    <meshStandardMaterial color={limbColor} />
                </mesh>
                <mesh rotation={[-appearance.antennaTilt, -0.12, -Math.PI / 4.2]}>
                    <cylinderGeometry args={[0.016, 0.018, 0.82, 8]} />
                    <meshStandardMaterial color={limbColor} />
                </mesh>
            </group>
            <mesh position={[0.57, 0.17, 0.12]}>
                <sphereGeometry args={[0.04 + (0.02 * appearance.eyeScale), 10, 10]} />
                <meshStandardMaterial color={eyeColor} emissive={eyeColor} emissiveIntensity={0.18} />
            </mesh>
            <mesh position={[0.57, 0.17, -0.12]}>
                <sphereGeometry args={[0.04 + (0.02 * appearance.eyeScale), 10, 10]} />
                <meshStandardMaterial color={eyeColor} emissive={eyeColor} emissiveIntensity={0.18} />
            </mesh>
            <group position={[0.7, 0.26, 0]}>
                <mesh rotation={[0.75, 0, Math.PI / 4.5]}>
                    <cylinderGeometry args={[0.012, 0.014, 0.7, 8]} />
                    <meshStandardMaterial color={limbColor} />
                </mesh>
                <mesh rotation={[-0.75, 0, -Math.PI / 4.5]}>
                    <cylinderGeometry args={[0.012, 0.014, 0.7, 8]} />
                    <meshStandardMaterial color={limbColor} />
                </mesh>
            </group>
            <mesh position={[0.8, 0.02, 0.08]} rotation={[0, 0.2, Math.PI / 5]}>
                <capsuleGeometry args={[0.022, 0.18, 4, 8]} />
                <meshStandardMaterial color={limbColor} />
            </mesh>
            <mesh position={[0.8, 0.02, -0.08]} rotation={[0, -0.2, -Math.PI / 5]}>
                <capsuleGeometry args={[0.022, 0.18, 4, 8]} />
                <meshStandardMaterial color={limbColor} />
            </mesh>
            {ant.state === 'sleeping' && (
                <Text
                    ref={sleepMarkerRef}
                    position={[0.85, 1.5, 0]}
                    fontSize={0.42}
                    color="#fff7ff"
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
    const livingAnts = useMemo(
        () => Object.values(ants || {}).filter((ant) => ant.alive !== false).sort((a, b) => a.id - b.id),
        [ants]
    );
    const slotOffsets = useMemo(() => {
        const byRoom = new Map();
        livingAnts.forEach((ant) => {
            const room = ant.position;
            const current = byRoom.get(room) || [];
            current.push(ant.id);
            byRoom.set(room, current);
        });

        const offsets = {};
        byRoom.forEach((ids) => {
            ids.forEach((antId, index) => {
                if (index === 0) {
                    offsets[antId] = { x: 0, z: 0 };
                    return;
                }
                const ring = Math.floor((Math.sqrt(index * 1.9) + 1) / 1.45);
                const radius = 1.45 + (ring * 0.95);
                const angle = (index * 2.399963229728653) + (seededNoise(antId) * 0.4);
                offsets[antId] = {
                    x: Math.cos(angle) * radius,
                    z: Math.sin(angle) * radius,
                };
            });
        });
        return offsets;
    }, [livingAnts]);

    return (
        <>
            <color attach="background" args={['#8fc16b']} />
            <PerspectiveCamera makeDefault position={[0, 52, 46]} fov={36} />
            <ambientLight intensity={1.35} />
            <directionalLight position={[24, 38, 18]} intensity={1.6} castShadow />
            <pointLight position={[-30, 14, -22]} intensity={0.65} color="#ffefc9" />

            <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow position={[0, -0.65, 0]}>
                <planeGeometry args={[280, 280]} />
                <meshStandardMaterial color="#89be63" roughness={1} />
            </mesh>
            <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow position={[0, -0.56, 0]}>
                <circleGeometry args={[58, 48]} />
                <meshStandardMaterial color="#bc8650" roughness={1} />
            </mesh>
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.53, 0]}>
                <circleGeometry args={[50, 48]} />
                <meshStandardMaterial color="#9f6939" roughness={1} />
            </mesh>

            <GroundDecor positions={positions} />

            {topology?.nodes?.map((node) => {
                if (node.id === specialChambers.nest) {
                    return <NestLandmark key={node.id} position={positions[node.id]} label="Nest" glow="#ffd26b" />;
                }
                if (node.id === specialChambers.nursery) {
                    return <NurseryLandmark key={node.id} position={positions[node.id]} label="Nursery" glow="#ffe0b8" />;
                }
                if (specialChambers.food.includes(node.id)) {
                    return <FoodLandmark key={node.id} position={positions[node.id]} label="Food" glow="#b8ef7b" />;
                }
                if (specialChambers.water.includes(node.id)) {
                    return <PondLandmark key={node.id} position={positions[node.id]} label="Water" glow="#93e7ff" />;
                }
                if (specialChambers.rest.includes(node.id)) {
                    return <RestLandmark key={node.id} position={positions[node.id]} label="Rest" glow="#d3c9ff" />;
                }
                return <GenericLandmark key={node.id} position={positions[node.id]} />;
            })}

            {livingAnts.map((ant) => (
                <Ant key={ant.id} ant={ant} positions={positions} slotOffset={slotOffsets[ant.id]} />
            ))}

            <OrbitControls enablePan enableZoom enableRotate minPolarAngle={0.72} maxPolarAngle={1.08} />
        </>
    );
}

function RenderPausedOverlay() {
    return (
        <Box
            sx={{
                position: 'absolute',
                inset: 0,
                display: 'grid',
                placeItems: 'center',
                background: `
                    radial-gradient(circle at 20% 18%, rgba(255,244,200,0.26), transparent 24%),
                    radial-gradient(circle at 80% 24%, rgba(146,207,117,0.20), transparent 20%),
                    linear-gradient(180deg, #8cbfe5 0%, #78b06b 35%, #533722 100%)
                `,
            }}
        >
            <Stack
                spacing={1}
                sx={{
                    px: 3,
                    py: 2.5,
                    borderRadius: 3,
                    color: '#fff8ed',
                    bgcolor: 'rgba(18,16,11,0.4)',
                    border: '1px solid rgba(255,255,255,0.12)',
                    backdropFilter: 'blur(10px)',
                    textAlign: 'center',
                }}
            >
                <Typography variant="h6" sx={{ fontWeight: 800 }}>
                    3D view paused
                </Typography>
                <Typography variant="body2" sx={{ maxWidth: 420, color: 'rgba(255,248,237,0.8)' }}>
                    The colony keeps running in the background. Only the visual scene is paused to save resources.
                </Typography>
            </Stack>
        </Box>
    );
}

function Visualizer({ topology, topologyName, ants, specialChambers, renderEnabled = true }) {
    if (!renderEnabled) {
        return <RenderPausedOverlay />;
    }

    return (
        <Box sx={{ position: 'absolute', inset: 0 }}>
            <Canvas shadows gl={{ antialias: true }}>
                <Scene topology={topology} topologyName={topologyName} ants={ants} specialChambers={specialChambers} />
            </Canvas>
        </Box>
    );
}

export default Visualizer;
