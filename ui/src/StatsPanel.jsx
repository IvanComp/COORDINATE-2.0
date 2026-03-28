import React, { useMemo } from 'react';
import { Box, Typography, Chip } from '@mui/material';

function StatsPanel({ logs, simTime }) {
    const stats = useMemo(() => {
        if (!logs || logs.length === 0) {
            return {
                totalEvents: 0,
                deliveries: 0,
                failures: 0,
                expirations: 0,
                activeRobots: 0,
                itemsCreated: 0
            };
        }

        const relevantLogs = logs.filter(log => log.simTime <= simTime);

        const deliveries = relevantLogs.filter(log => log.event === 'deliver').length;
        const failures = relevantLogs.filter(log => log.event === 'fail').length;
        const expirations = relevantLogs.filter(log => log.event === 'expire').length;
        const itemsCreated = relevantLogs.filter(log => log.event === 'create').length;

        const robotIds = new Set(relevantLogs.filter(log => log.robotId !== -1).map(log => log.robotId));
        const activeRobots = robotIds.size;

        return {
            totalEvents: relevantLogs.length,
            deliveries,
            failures,
            expirations,
            activeRobots,
            itemsCreated
        };
    }, [logs, simTime]);

    return (
        <Box sx={{
            display: 'flex',
            gap: 2,
            alignItems: 'center',
            flexWrap: 'wrap'
        }}>
            <Chip
                label={`Events: ${stats.totalEvents}`}
                size="small"
                sx={{ bgcolor: 'rgba(255,255,255,0.2)', color: 'white', fontWeight: 'bold' }}
            />
            <Chip
                label={`Created: ${stats.itemsCreated}`}
                size="small"
                sx={{ bgcolor: 'rgba(33, 150, 243, 0.3)', color: 'white', fontWeight: 'bold' }}
            />
            <Chip
                label={`Delivered: ${stats.deliveries}`}
                size="small"
                sx={{ bgcolor: 'rgba(76, 175, 80, 0.3)', color: 'white', fontWeight: 'bold' }}
            />
            <Chip
                label={`Expired: ${stats.expirations}`}
                size="small"
                sx={{ bgcolor: 'rgba(255, 152, 0, 0.3)', color: 'white', fontWeight: 'bold' }}
            />
            <Chip
                label={`Failures: ${stats.failures}`}
                size="small"
                sx={{ bgcolor: 'rgba(244, 67, 54, 0.3)', color: 'white', fontWeight: 'bold' }}
            />
            <Chip
                label={`Agents: ${stats.activeRobots}`}
                size="small"
                sx={{ bgcolor: 'rgba(156, 39, 176, 0.3)', color: 'white', fontWeight: 'bold' }}
            />
        </Box>
    );
}

export default StatsPanel;
