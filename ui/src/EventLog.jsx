import React, { useMemo, useState, useEffect, useRef } from 'react';
import { Box, Typography, Paper } from '@mui/material';

function EventLog({ logs, simTime }) {
    const [isCollapsed, setIsCollapsed] = useState(true);
    const scrollRef = useRef(null);

    // Filter and format logs
    const events = useMemo(() => {
        if (!logs) return [];

        // Get events up to current simTime
        const currentEvents = logs.filter(log => log.simTime <= simTime);

        // Take last 50 events to avoid performance issues
        const recentEvents = currentEvents.slice(-50);

        return recentEvents.map((log, index) => {
            let message = '';
            const time = (typeof log.simTime === 'number' ? log.simTime : parseFloat(log.simTime) || 0).toFixed(1);

            switch (log.event) {
                case 'create':
                    const impLabel = { 0: 'L', 1: 'M', 2: 'H' }[log.itemImportance] || log.itemImportance;
                    message = `Task ${log.itemId} created (Priority: ${impLabel})`;
                    break;
                case 'startLoading':
                    message = `Agent ${log.robotId} started Task ${log.itemId}`;
                    break;
                case 'move':
                    message = `Agent ${log.robotId} moving to Room ${log.destination}`;
                    break;
                case 'deliver':
                    message = `Agent ${log.robotId} completed Task ${log.itemId}`;
                    break;
                case 'fail':
                    message = `Agent ${log.robotId} FAILED!`;
                    break;
                case 'recover':
                case 'recovery':
                    message = `Agent ${log.robotId} recovered`;
                    break;
                case 'expire':
                    message = `Task ${log.itemId} expired`;
                    break;
                default:
                    message = `${log.event} (Agent:${log.robotId}, Task:${log.itemId})`;
            }

            return {
                id: index,
                time,
                message,
                type: log.event
            };
        });
    }, [logs, simTime]);

    // Auto-scroll to bottom when events change
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [events, isCollapsed]);

    const getEventColor = (type) => {
        switch (type) {
            case 'fail': return '#ff5252';
            case 'deliver': return '#69f0ae';
            case 'create': return '#448aff';
            case 'expire': return '#ffab40';
            default: return 'rgba(255,255,255,0.7)';
        }
    };

    return (
        <Paper
            sx={{
                bgcolor: 'rgba(0, 0, 0, 0.6)',
                backdropFilter: 'blur(10px)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                minWidth: 250,
                maxWidth: 350,
                overflow: 'hidden',
                transition: 'all 0.3s ease',
                display: 'flex',
                flexDirection: 'column'
            }}
            elevation={8}
        >
            {/* Header (Always Visible at Top) */}
            <Box
                onClick={() => setIsCollapsed(!isCollapsed)}
                sx={{
                    p: 1.5,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    cursor: 'pointer',
                    borderBottom: isCollapsed ? 'none' : '1px solid rgba(255,255,255,0.1)',
                    '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' }
                }}
            >
                <Typography variant="subtitle2" sx={{ color: 'white', fontWeight: 'bold' }}>
                    Event Log
                </Typography>
                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)' }}>
                    {isCollapsed ? '▼' : '▲'}
                </Typography>
            </Box>

            {/* Content Area (Collapsible) */}
            <Box sx={{
                maxHeight: isCollapsed ? '0px' : '200px',
                opacity: isCollapsed ? 0 : 1,
                transition: 'all 0.3s ease',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column'
            }} ref={scrollRef}>
                <Box sx={{ p: 1 }}>
                    {events.length === 0 ? (
                        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)', fontStyle: 'italic' }}>
                            No events yet...
                        </Typography>
                    ) : (
                        events.map((evt) => (
                            <Box key={evt.id} sx={{ mb: 0.5, display: 'flex', gap: 1 }}>
                                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)', minWidth: '35px' }}>
                                    [{evt.time}s]
                                </Typography>
                                <Typography variant="caption" sx={{ color: getEventColor(evt.type) }}>
                                    {evt.message}
                                </Typography>
                            </Box>
                        ))
                    )}
                </Box>
            </Box>
        </Paper>
    );
}

export default EventLog;
