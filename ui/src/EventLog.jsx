import React, { useMemo, useState } from 'react';
import { Box, Paper, Typography } from '@mui/material';

function EventLog({ logs, simTime }) {
    const [expanded, setExpanded] = useState(true);

    const events = useMemo(() => {
        return (logs || [])
            .filter((log) => Number(log.simTime) <= simTime)
            .slice(-40)
            .map((log, index) => {
                const time = Number(log.simTime).toFixed(1);
                const ant = Number(log.antId);
                const partner = Number(log.partnerId);
                const messages = {
                    birth: `Ant ${ant} is born (${log.sex})`,
                    move: `Ant ${ant} moves toward chamber ${log.destination}`,
                    eat: `Ant ${ant} eats`,
                    drink: `Ant ${ant} drinks`,
                    mate: `Ant ${ant} mates with ${partner}`,
                    nap_start: `Ant ${ant} enters a micro-nap`,
                    nap_end: `Ant ${ant} becomes active again`,
                    death: `Ant ${ant} dies: ${log.details}`,
                    resource_spawn: `New resource pulse (${log.details})`,
                };
                return { id: `${index}-${time}`, time, text: messages[log.event] || `${log.event} (${ant})`, type: log.event };
            });
    }, [logs, simTime]);

    const colors = {
        birth: '#d8a95f',
        move: '#9ac46e',
        eat: '#8fcf65',
        drink: '#6ab3e7',
        mate: '#cf95e8',
        nap_start: '#a7b4cf',
        nap_end: '#d1dae8',
        death: '#f08b7f',
        resource_spawn: '#f7d77b',
    };

    return (
        <Paper sx={{ width: 320, bgcolor: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(10px)', border: '1px solid rgba(255,255,255,0.1)' }}>
            <Box sx={{ p: 1.5, display: 'flex', justifyContent: 'space-between', cursor: 'pointer' }} onClick={() => setExpanded((value) => !value)}>
                <Typography variant="subtitle2" sx={{ color: 'white', fontWeight: 'bold' }}>Event Log</Typography>
                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.65)' }}>{expanded ? '▲' : '▼'}</Typography>
            </Box>
            {expanded && (
                <Box sx={{ px: 1.5, pb: 1.5, maxHeight: 280, overflowY: 'auto' }}>
                    {events.length === 0 ? (
                        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)' }}>No events yet.</Typography>
                    ) : (
                        events.map((event) => (
                            <Box key={event.id} sx={{ display: 'flex', gap: 1, mb: 0.7 }}>
                                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.55)', minWidth: 42 }}>
                                    [{event.time}]
                                </Typography>
                                <Typography variant="caption" sx={{ color: colors[event.type] || 'white' }}>
                                    {event.text}
                                </Typography>
                            </Box>
                        ))
                    )}
                </Box>
            )}
        </Paper>
    );
}

export default EventLog;
