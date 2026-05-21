import React from 'react';
import { Box, Typography, Paper } from '@mui/material';
import { Circle, Square } from '@mui/icons-material';

// Simple SVG Robot Icon
function RobotIcon({ hasItem, isFailed, isRescuing }) {
    const bodyColor = isFailed ? '#F44336' : (isRescuing ? '#2196F3' : (hasItem ? '#4CAF50' : '#9E9E9E'));

    return (
        <svg width="16" height="16" viewBox="0 0 16 16" style={{ display: 'block' }}>
            {/* Robot body */}
            <rect x="5" y="6" width="6" height="7" fill={bodyColor} rx="1" />
            {/* Robot head */}
            <circle cx="8" cy="4" r="2.5" fill={bodyColor} />
            {/* Eyes */}
            <circle cx="7" cy="4" r="0.5" fill="white" />
            <circle cx="9" cy="4" r="0.5" fill="white" />
            {/* Item on top if carrying */}
            {hasItem && !isFailed && (
                <rect x="6.5" y="1" width="3" height="3" fill="#FFC107" rx="0.5" />
            )}
            {/* Warning triangle if failed */}
            {isFailed && (
                <polygon points="8,1 10,4 6,4" fill="#FF5722" />
            )}
        </svg>
    );
}

function Legend() {
    const [expanded, setExpanded] = React.useState(false);

    const handleExpandClick = () => {
        setExpanded(!expanded);
    };

    const LegendItem = ({ icon, label }) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            {icon}
            <Typography variant="caption" sx={{ color: 'white', fontSize: '0.75rem' }}>
                {label}
            </Typography>
        </Box>
    );

    return (
        <Paper
            sx={{
                bgcolor: 'rgba(0, 0, 0, 0.6)',
                backdropFilter: 'blur(10px)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                minWidth: 200,
                overflow: 'hidden',
                transition: 'all 0.3s ease',
                display: 'flex',
                flexDirection: 'column'
            }}
            elevation={8}
        >
            {/* Header (Always Visible at Top) */}
            <Box
                onClick={handleExpandClick}
                sx={{
                    p: 2,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    cursor: 'pointer',
                    borderBottom: expanded ? '1px solid rgba(255,255,255,0.1)' : 'none',
                    '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' }
                }}
            >
                <Typography variant="subtitle2" sx={{ color: 'white', fontWeight: 'bold' }}>
                    Legend
                </Typography>
                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)' }}>
                    {expanded ? '▲' : '▼'}
                </Typography>
            </Box>

            {/* Content Area (Collapsible) */}
            <Box sx={{
                maxHeight: expanded ? '500px' : '0px',
                opacity: expanded ? 1 : 0,
                transition: 'all 0.3s ease',
                overflow: 'hidden'
            }}>
                <Box sx={{ p: 2, pt: 0 }}>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)', display: 'block', mb: 1 }}>
                        Rooms
                    </Typography>
                    <LegendItem
                        icon={<Square sx={{ fontSize: 16, color: '#4CAF50' }} />}
                        label="Source Room"
                    />
                    <LegendItem
                        icon={<Square sx={{ fontSize: 16, color: '#2196F3' }} />}
                        label="Regular Room"
                    />

                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)', display: 'block', mt: 1.5, mb: 1 }}>
                        Agents
                    </Typography>
                    <LegendItem
                        icon={<RobotIcon hasItem={false} isFailed={false} />}
                        label="Agent (Waiting)"
                    />
                    <LegendItem
                        icon={<RobotIcon hasItem={true} isFailed={false} />}
                        label="Agent (Carrying)"
                    />
                    <LegendItem
                        icon={<RobotIcon hasItem={false} isFailed={true} isRescuing={false} />}
                        label="Agent (Failed)"
                    />
                    <LegendItem
                        icon={<RobotIcon hasItem={false} isFailed={false} isRescuing={true} />}
                        label="Agent (Rescuing)"
                    />

                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)', display: 'block', mt: 1.5, mb: 1 }}>
                        Tasks
                    </Typography>
                    <LegendItem
                        icon={<Square sx={{ fontSize: 16, color: '#4CAF50' }} />}
                        label="Low Priority"
                    />
                    <LegendItem
                        icon={<Square sx={{ fontSize: 16, color: '#FFC107' }} />}
                        label="Medium Priority"
                    />
                    <LegendItem
                        icon={<Square sx={{ fontSize: 16, color: '#FF5722' }} />}
                        label="High Priority"
                    />
                </Box>
            </Box>
        </Paper>
    );
}

export default Legend;
