import React, { useState } from 'react';
import { Box, Paper, Typography } from '@mui/material';

function Dot({ color }) {
    return <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: color }} />;
}

function Row({ color, label }) {
    return (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.7 }}>
            <Dot color={color} />
            <Typography variant="caption" sx={{ color: 'white' }}>{label}</Typography>
        </Box>
    );
}

function Legend() {
    const [expanded, setExpanded] = useState(false);

    return (
        <Paper sx={{ width: 320, bgcolor: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(10px)', border: '1px solid rgba(255,255,255,0.1)' }}>
            <Box sx={{ p: 1.5, display: 'flex', justifyContent: 'space-between', cursor: 'pointer' }} onClick={() => setExpanded((value) => !value)}>
                <Typography variant="subtitle2" sx={{ color: 'white', fontWeight: 'bold' }}>Legend</Typography>
                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.65)' }}>{expanded ? '▲' : '▼'}</Typography>
            </Box>
            {expanded && (
                <Box sx={{ px: 1.5, pb: 1.5 }}>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)', display: 'block', mb: 1 }}>Ants</Typography>
                    <Row color="#d8a95f" label="Active female" />
                    <Row color="#7ca6ff" label="Active male" />
                    <Row color="#a7b4cf" label="Micro-nap" />
                    <Row color="#f08b7f" label="Dead ant" />
                    <Row color="#cf95e8" label="Mating in progress" />

                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)', display: 'block', my: 1 }}>Chambers</Typography>
                    <Row color="#8b5a2b" label="Central nest" />
                    <Row color="#8fcf65" label="Food chamber" />
                    <Row color="#6ab3e7" label="Water chamber" />
                    <Row color="#d89ee8" label="Nursery" />
                    <Row color="#7a8498" label="Rest zone" />
                </Box>
            )}
        </Paper>
    );
}

export default Legend;
