import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Box, Button, Chip, CircularProgress, Paper, Stack, Typography } from '@mui/material';
import axios from 'axios';
import AnalyticsModal from './AnalyticsModal';
import AntSearchPanel from './AntSearchPanel';
import EventLog from './EventLog';
import Legend from './Legend';
import Visualizer from './Visualizer';

const API_BASE = '/api';

function formatSimClock(simTime) {
    const totalMinutes = Math.max(0, Math.floor(Number(simTime) || 0));
    const day = Math.floor(totalMinutes / 1440) + 1;
    const minutesOfDay = totalMinutes % 1440;
    const hours = String(Math.floor(minutesOfDay / 60)).padStart(2, '0');
    const minutes = String(minutesOfDay % 60).padStart(2, '0');
    return `Day ${day}, ${hours}:${minutes}`;
}

function LiveColonyView({ onBack }) {
    const [liveState, setLiveState] = useState(null);
    const [topology, setTopology] = useState(null);
    const [actionBusy, setActionBusy] = useState(false);
    const [error, setError] = useState(null);
    const [analyticsOpen, setAnalyticsOpen] = useState(false);
    const [historyLogs, setHistoryLogs] = useState([]);

    const refreshState = async () => {
        const res = await axios.get(`${API_BASE}/live/state`);
        setLiveState(res.data);
        setHistoryLogs((current) => {
            const seen = new Set(current.map((log) => `${log.simTime}-${log.antId}-${log.event}-${log.childId}`));
            const additions = (res.data.recentEvents || []).filter((log) => !seen.has(`${log.simTime}-${log.antId}-${log.event}-${log.childId}`));
            return [...current, ...additions].sort((a, b) => Number(a.simTime) - Number(b.simTime)).slice(-600);
        });
        return res.data;
    };

    useEffect(() => {
        refreshState().catch((err) => setError(err.response?.data?.error || err.message));
        const interval = setInterval(() => {
            refreshState().catch((err) => setError(err.response?.data?.error || err.message));
        }, 2000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        if (!liveState?.hasColony || !liveState?.topologyName) return;
        axios.get(`${API_BASE}/topology/${liveState.topologyName}`)
            .then((res) => setTopology(res.data))
            .catch((err) => setError(err.response?.data?.error || err.message));
    }, [liveState?.topologyName, liveState?.hasColony]);

    const runAction = async (route, body = {}) => {
        setActionBusy(true);
        setError(null);
        try {
            const res = await axios.post(`${API_BASE}/live/${route}`, body);
            setLiveState(res.data);
            if (route === 'start' && body.restart) {
                setHistoryLogs(res.data.recentEvents || []);
            }
        } catch (err) {
            setError(err.response?.data?.error || err.message);
        } finally {
            setActionBusy(false);
        }
    };

    const summary = liveState?.summary || {
        living: 0,
        births: 0,
        deaths: 0,
        matings: 0,
        meals: 0,
        drinks: 0,
        sleeping: 0,
        awakeFemaleRatio: 100,
        events: 0,
    };
    const status = liveState?.status || 'stopped';
    const currentClock = useMemo(() => formatSimClock(liveState?.simTime || 0), [liveState?.simTime]);

    return (
        <Box sx={{ width: '100vw', height: '100vh', position: 'relative', overflow: 'hidden', bgcolor: '#080b12' }}>
            {liveState?.hasColony && topology ? (
                <Visualizer
                    topology={topology}
                    topologyName={liveState.topologyName}
                    ants={liveState.ants}
                    specialChambers={liveState.specialChambers}
                />
            ) : (
                <Box
                    sx={{
                        position: 'absolute',
                        inset: 0,
                        background: `
                            radial-gradient(circle at top left, rgba(216,169,95,0.18), transparent 28%),
                            radial-gradient(circle at top right, rgba(141,193,107,0.16), transparent 24%),
                            linear-gradient(180deg, #151009 0%, #0d1016 55%, #070a10 100%)
                        `,
                    }}
                />
            )}

            <Box sx={{ position: 'absolute', top: 16, left: 16, zIndex: 8 }}>
                <Stack spacing={1.5}>
                    <Button
                        variant="outlined"
                        onClick={onBack}
                        sx={{
                            alignSelf: 'flex-start',
                            color: 'white',
                            borderColor: 'rgba(255,255,255,0.18)',
                            bgcolor: 'rgba(0,0,0,0.4)',
                            backdropFilter: 'blur(10px)',
                        }}
                    >
                        Back to home
                    </Button>

                    <Paper
                        sx={{
                            width: 'min(380px, calc(100vw - 32px))',
                            p: 2,
                            color: 'white',
                            bgcolor: 'rgba(0,0,0,0.62)',
                            backdropFilter: 'blur(12px)',
                            border: '1px solid rgba(255,255,255,0.12)',
                        }}
                    >
                        <Stack spacing={1.5}>
                            <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                                Live Colony
                            </Typography>
                            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.72)' }}>
                                This mode runs continuously with near-real pacing. By default, the colony advances 1 simulated minute every 5 real seconds.
                            </Typography>
                            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)' }}>
                                Ant maturity and lifespan are stretched across many simulated days, so the colony can be monitored over long sessions instead of finishing in minutes.
                            </Typography>
                            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                <Chip label={`Status: ${status}`} size="small" sx={{ bgcolor: 'rgba(255,255,255,0.08)', color: 'white' }} />
                                <Chip label={currentClock} size="small" sx={{ bgcolor: 'rgba(216,169,95,0.18)', color: '#f1d4a3' }} />
                            </Stack>
                            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                <Button variant="contained" onClick={() => runAction('start', { restart: status === 'stopped' })} disabled={actionBusy || status === 'running'}>
                                    {liveState?.hasColony ? 'Start / Restart' : 'Start live colony'}
                                </Button>
                                <Button variant="outlined" onClick={() => runAction('pause')} disabled={actionBusy || status !== 'running'}>
                                    Pause
                                </Button>
                                <Button variant="outlined" onClick={() => runAction('resume')} disabled={actionBusy || status !== 'paused'}>
                                    Resume
                                </Button>
                                <Button variant="outlined" color="error" onClick={() => runAction('stop')} disabled={actionBusy || !liveState?.hasColony}>
                                    Stop
                                </Button>
                            </Stack>
                        </Stack>
                    </Paper>
                </Stack>
            </Box>

            {liveState?.hasColony && (
                <>
                    <Box sx={{ position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 5 }}>
                        <Paper sx={{ p: 1.3, bgcolor: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(10px)', border: '1px solid rgba(255,255,255,0.1)', color: 'white' }}>
                            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} alignItems={{ xs: 'flex-start', md: 'center' }}>
                                <Box>
                                    <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                                        Live Dashboard
                                    </Typography>
                                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.68)' }}>
                                        Open the analytics popup to monitor charts while the colony keeps running.
                                    </Typography>
                                </Box>
                                <Button variant="contained" onClick={() => setAnalyticsOpen(true)} disabled={!liveState?.hasColony}>
                                    Open dashboard
                                </Button>
                            </Stack>
                        </Paper>
                    </Box>

                    <Stack spacing={2} sx={{ position: 'absolute', right: 16, top: 16, zIndex: 5 }}>
                        <Legend />
                        <AntSearchPanel liveMode liveAvailable={liveState?.hasColony} />
                        <EventLog logs={liveState?.recentEvents || []} simTime={liveState?.simTime || 0} />
                    </Stack>

                    <Paper
                        sx={{
                            position: 'absolute',
                            left: '50%',
                            bottom: 16,
                            transform: 'translateX(-50%)',
                            width: 'min(960px, calc(100vw - 32px))',
                            p: 2,
                            zIndex: 6,
                            bgcolor: 'rgba(0,0,0,0.62)',
                            backdropFilter: 'blur(12px)',
                            border: '1px solid rgba(255,255,255,0.12)',
                        }}
                    >
                        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} justifyContent="space-between">
                            <Box>
                                <Typography variant="subtitle2" sx={{ color: 'white', fontWeight: 'bold' }}>
                                    Persistent world clock
                                </Typography>
                                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.72)', display: 'block', mt: 0.6 }}>
                                    {currentClock}
                                </Typography>
                                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.55)', display: 'block', mt: 0.4 }}>
                                    {liveState?.simDay ? `${liveState.simDay} simulated days elapsed` : 'No live colony running yet'}
                                </Typography>
                            </Box>
                            <Box>
                                <Typography variant="subtitle2" sx={{ color: 'white', fontWeight: 'bold' }}>
                                    Real-time pacing
                                </Typography>
                                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.72)', display: 'block', mt: 0.6 }}>
                                    {liveState?.config
                                        ? `${liveState.config.SIM_MINUTES_PER_TICK} simulated minute(s) every ${liveState.config.LIVE_SECONDS_PER_TICK} real second(s)`
                                        : 'Waiting for colony configuration'}
                                </Typography>
                                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.55)', display: 'block', mt: 0.4 }}>
                                    Snapshot saved every {liveState?.config?.SNAPSHOT_INTERVAL_SECONDS || 60} seconds
                                </Typography>
                            </Box>
                        </Stack>
                    </Paper>
                </>
            )}

            {actionBusy && (
                <Box sx={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', zIndex: 10, bgcolor: 'rgba(5,8,12,0.42)' }}>
                    <Stack alignItems="center" spacing={2}>
                        <CircularProgress sx={{ color: '#d8a95f' }} />
                        <Typography sx={{ color: 'white' }}>Updating live colony...</Typography>
                    </Stack>
                </Box>
            )}

            {error && (
                <Alert severity="error" sx={{ position: 'absolute', left: 16, bottom: 140, zIndex: 8, maxWidth: 520 }}>
                    {error}
                </Alert>
            )}

            <AnalyticsModal
                open={analyticsOpen}
                onClose={() => setAnalyticsOpen(false)}
                logs={historyLogs}
                summary={summary}
                title="Live Colony Dashboard"
                subtitle="This popup updates while the live colony keeps advancing in the background."
            />
        </Box>
    );
}

export default LiveColonyView;
