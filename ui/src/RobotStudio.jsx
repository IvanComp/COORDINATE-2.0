import React, { useRef, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { PerspectiveCamera, OrbitControls, Environment } from '@react-three/drei';
import { Box } from '@mui/material';

// 3D Robot Component (Copied from Visualizer.jsx)
function Robot({ id, position, hasItem, isFailed, colorOverride }) {
    const groupRef = useRef();

    // Robot colors: Gray (empty), Green (carrying), Red (failed)
    const bodyColor = colorOverride || (isFailed ? '#F44336' : (hasItem ? '#4CAF50' : '#9E9E9E'));

    return (
        <group ref={groupRef} position={[position.x, 0.5, position.z]}>
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

            {/* Item indicator if carrying */}
            {hasItem && (
                <mesh position={[0, 1.4, 0]} castShadow>
                    <boxGeometry args={[0.5, 0.5, 0.5]} />
                    <meshStandardMaterial color="#FFC107" />
                </mesh>
            )}
        </group>
    );
}

export default function RobotStudio() {
    return (
        <Box sx={{ width: '100vw', height: '100vh', bgcolor: 'transparent' }}>
            <Canvas gl={{ alpha: true }} shadows>
                <PerspectiveCamera makeDefault position={[3, 3, 4]} fov={50} />
                <OrbitControls />

                <ambientLight intensity={0.8} />
                <directionalLight position={[5, 10, 5]} intensity={1.5} castShadow />
                <pointLight position={[-5, 5, -5]} intensity={0.5} />

                {/* Front View Robot */}
                <group position={[-2, 0, 0]}>
                    <Robot id={1} position={{ x: 0, y: 0, z: 0 }} hasItem={false} isFailed={false} />
                </group>

                {/* Isometric/Angle Robot */}
                <group position={[0, 0, 0]} rotation={[0, -Math.PI / 6, 0]}>
                    <Robot id={2} position={{ x: 0, y: 0, z: 0 }} hasItem={false} isFailed={false} />
                </group>

                {/* Side View Robot */}
                <group position={[2, 0, 0]} rotation={[0, -Math.PI / 2, 0]}>
                    <Robot id={3} position={{ x: 0, y: 0, z: 0 }} hasItem={false} isFailed={false} />
                </group>

            </Canvas>
        </Box>
    );
}
