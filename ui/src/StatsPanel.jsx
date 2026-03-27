import React, { useMemo } from 'react';
import { Box, Chip } from '@mui/material';

function StatsPanel({ logs, simTime, currentAnts }) {
    const stats = useMemo(() => {
        const relevant = (logs || []).filter((log) => Number(log.simTime) <= simTime);
        const living = Object.values(currentAnts || {}).filter((ant) => ant.alive !== false).length;
        const sleeping = Object.values(currentAnts || {}).filter((ant) => ant.state === 'sleeping').length;
        const females = Object.values(currentAnts || {}).filter((ant) => ant.sex === 'F' && ant.alive !== false).length;
        const awakeFemales = Object.values(currentAnts || {}).filter((ant) => ant.sex === 'F' && ant.state !== 'sleeping' && ant.alive !== false).length;
        return {
            events: relevant.length,
            births: relevant.filter((log) => log.event === 'birth').length,
            deaths: relevant.filter((log) => log.event === 'death').length,
            matings: relevant.filter((log) => log.event === 'mate').length,
            meals: relevant.filter((log) => log.event === 'eat').length,
            drinks: relevant.filter((log) => log.event === 'drink').length,
            living,
            sleeping,
            awakeRatio: females ? Math.round((awakeFemales / females) * 100) : 100,
        };
    }, [logs, simTime, currentAnts]);

    const chipSx = { color: 'white', fontWeight: 'bold', bgcolor: 'rgba(255,255,255,0.12)' };

    return (
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', justifyContent: 'center' }}>
            <Chip label={`Events ${stats.events}`} size="small" sx={chipSx} />
            <Chip label={`Alive ${stats.living}`} size="small" sx={{ ...chipSx, bgcolor: 'rgba(141,193,107,0.28)' }} />
            <Chip label={`Births ${stats.births}`} size="small" sx={{ ...chipSx, bgcolor: 'rgba(216,169,95,0.28)' }} />
            <Chip label={`Deaths ${stats.deaths}`} size="small" sx={{ ...chipSx, bgcolor: 'rgba(204,96,96,0.28)' }} />
            <Chip label={`Matings ${stats.matings}`} size="small" sx={{ ...chipSx, bgcolor: 'rgba(131,124,214,0.28)' }} />
            <Chip label={`Meals ${stats.meals}`} size="small" sx={{ ...chipSx, bgcolor: 'rgba(110,171,89,0.28)' }} />
            <Chip label={`Drinks ${stats.drinks}`} size="small" sx={{ ...chipSx, bgcolor: 'rgba(85,166,222,0.28)' }} />
            <Chip label={`Sleeping ${stats.sleeping}`} size="small" sx={{ ...chipSx, bgcolor: 'rgba(99,111,137,0.28)' }} />
            <Chip label={`Awake workers ${stats.awakeRatio}%`} size="small" sx={{ ...chipSx, bgcolor: 'rgba(244,200,115,0.28)' }} />
        </Box>
    );
}

export default StatsPanel;
