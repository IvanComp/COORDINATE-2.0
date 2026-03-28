import React, { useMemo } from 'react';
import { Box } from '@mui/material';

function AgentSprite({ x, y, dx, dy, duration, delay, color }) {
    return (
        <Box
            sx={{
                position: 'absolute',
                left: `${x}%`,
                top: `${y}%`,
                width: '34px',
                height: '34px',
                opacity: 0.22,
                zIndex: 0,
                willChange: 'transform',
                animation: `floatAgent ${duration}s linear ${delay}s infinite alternate`,
                '@keyframes floatAgent': {
                    '0%': { transform: 'translate(0px, 0px)' },
                    '100%': { transform: `translate(${dx}px, ${dy}px)` }
                }
            }}
        >
            <svg width="34" height="34" viewBox="0 0 40 40" aria-hidden="true">
                <rect x="12" y="15" width="16" height="18" fill={color} rx="2" />
                <circle cx="20" cy="10" r="6" fill={color} />
                <circle cx="17" cy="10" r="1.5" fill="white" />
                <circle cx="23" cy="10" r="1.5" fill="white" />
                <line x1="20" y1="4" x2="20" y2="1" stroke={color} strokeWidth="2" />
                <circle cx="20" cy="1" r="2" fill={color} />
            </svg>
        </Box>
    );
}

function AnimatedRobots() {
    const agents = useMemo(() => {
        const count = 10;
        const colors = ['#9E9E9E', '#4CAF50', '#F44336', '#2196F3', '#FFC107'];
        return Array.from({ length: count }).map((_, i) => ({
            id: i,
            x: Math.random() * 100,
            y: Math.random() * 100,
            dx: (Math.random() - 0.5) * 400,
            dy: (Math.random() - 0.5) * 280,
            duration: 9 + Math.random() * 6,
            delay: Math.random() * 2,
            color: colors[Math.floor(Math.random() * colors.length)]
        }));
    }, []);

    return (
        <Box
            sx={{
                position: 'absolute',
                inset: 0,
                overflow: 'hidden',
                pointerEvents: 'none'
            }}
        >
            {agents.map((a) => (
                <AgentSprite
                    key={a.id}
                    x={a.x}
                    y={a.y}
                    dx={a.dx}
                    dy={a.dy}
                    duration={a.duration}
                    delay={a.delay}
                    color={a.color}
                />
            ))}
        </Box>
    );
}

export default AnimatedRobots;
