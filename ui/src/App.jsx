import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Box, Button, Chip, CircularProgress, Paper, Slider, Snackbar, Stack, Typography } from '@mui/material';
import GitHubIcon from '@mui/icons-material/GitHub';
import axios from 'axios';
import AnalyticsModal from './AnalyticsModal';
import AntSearchPanel from './AntSearchPanel';
import ConfigForm from './ConfigForm';
import EventLog from './EventLog';
import Legend from './Legend';
import LiveColonyView from './LiveColonyView';
import Visualizer from './Visualizer';

const API_BASE = '/api';

const SIMULATION_MODES = [
    {
        id: 'batch-simulation',
        title: 'Batch Colony',
        subtitle: 'Finite analysis run',
        description: 'Launch a classic colony run with a clear beginning and end, then inspect the full history after it completes.',
        available: true,
    },
    {
        id: 'live-colony',
        title: 'Live Colony',
        subtitle: 'Persistent real-time monitoring',
        description: 'Run a colony continuously with slow life rhythms, long lifespans, and a live dashboard you can watch over time.',
        available: true,
    },
];

function deriveSpecialChambers(topology) {
    const roomCount = topology?.nodes?.length || 0;
    if (!roomCount) {
        return { nest: 0, nursery: 0, food: [], water: [], rest: [] };
    }
    return {
        nest: 0,
        nursery: Math.min(roomCount - 1, Math.max(1, Math.floor(roomCount / 2))),
        food: Array.from(new Set([Math.min(roomCount - 1, 1), Math.min(roomCount - 1, Math.floor(roomCount / 3) || 1)])),
        water: Array.from(new Set([Math.min(roomCount - 1, 2), Math.min(roomCount - 1, Math.floor((roomCount * 2) / 3))])),
        rest: Array.from(new Set([Math.max(0, roomCount - 1), Math.max(0, roomCount - 2)])),
    };
}

function HomePage({ onEnter }) {
    return (
        <Box
            sx={{
                minHeight: '100vh',
                px: { xs: 2, md: 5 },
                py: { xs: 3, md: 5 },
                color: 'white',
                background: `
                    radial-gradient(circle at top left, rgba(216,169,95,0.22), transparent 28%),
                    radial-gradient(circle at top right, rgba(141,193,107,0.18), transparent 24%),
                    linear-gradient(180deg, #151009 0%, #0d1016 55%, #070a10 100%)
                `,
            }}
        >
            <Stack spacing={4} sx={{ maxWidth: 1240, mx: 'auto' }}>
                <Paper
                    sx={{
                        p: { xs: 3, md: 5 },
                        borderRadius: 4,
                        color: 'white',
                        bgcolor: 'rgba(14, 12, 10, 0.72)',
                        border: '1px solid rgba(255,255,255,0.08)',
                        backdropFilter: 'blur(14px)',
                        overflow: 'hidden',
                        position: 'relative',
                    }}
                >
                    <Box
                        sx={{
                            position: 'absolute',
                            inset: 0,
                            background: 'linear-gradient(120deg, rgba(216,169,95,0.18), transparent 36%, rgba(141,193,107,0.12) 100%)',
                            pointerEvents: 'none',
                        }}
                    />
                    <Box
                        sx={{
                            position: 'relative',
                            display: 'grid',
                            gridTemplateColumns: { xs: '1fr', xl: 'minmax(0, 1.45fr) minmax(300px, 0.75fr)' },
                            gap: 2.5,
                            alignItems: 'stretch',
                        }}
                    >
                        <Stack spacing={2}>
                            <Typography
                                variant="h2"
                                sx={{
                                    fontSize: { xs: '2.05rem', md: '3.85rem' },
                                    lineHeight: 0.95,
                                    fontWeight: 800,
                                    maxWidth: 980,
                                }}
                            >
                                <Box component="span" sx={{ display: 'block' }}>
                                    Choose which anthill simulation
                                </Box>
                                <Box component="span" sx={{ display: 'block', whiteSpace: 'nowrap' }}>
                                    you want to open.
                                </Box>
                            </Typography>
                            <Typography sx={{ maxWidth: 760, color: 'rgba(255,255,255,0.74)', fontSize: { xs: '1rem', md: '1.08rem' } }}>
                                The app no longer drops you straight into the technical panel. You now enter through a dedicated launcher with multiple simulation families visible, including both the classic finite run and a persistent live colony.
                            </Typography>
                        </Stack>

                        <Paper
                            component="a"
                            href="https://github.com/IvanComp/AgANT-of-Empire"
                            target="_blank"
                            rel="noreferrer"
                            sx={{
                                p: 3,
                                minHeight: { xs: 180, xl: '100%' },
                                display: 'flex',
                                flexDirection: 'column',
                                justifyContent: 'space-between',
                                textDecoration: 'none',
                                color: 'white',
                                bgcolor: 'rgba(18, 21, 25, 0.78)',
                                border: '1px solid rgba(216,169,95,0.24)',
                                borderRadius: 3,
                                boxShadow: '0 20px 80px rgba(0,0,0,0.22)',
                                transition: 'transform 160ms ease, border-color 160ms ease, background-color 160ms ease',
                                '&:hover': {
                                    transform: 'translateY(-2px)',
                                    borderColor: 'rgba(216,169,95,0.45)',
                                    bgcolor: 'rgba(22, 26, 31, 0.9)',
                                },
                            }}
                        >
                            <Stack spacing={1.5}>
                                <Stack direction="row" spacing={1.2} alignItems="center">
                                    <GitHubIcon sx={{ color: '#f1d4a3' }} />
                                    <Typography variant="overline" sx={{ letterSpacing: '0.16em', color: '#f1d4a3' }}>
                                        Repository
                                    </Typography>
                                </Stack>
                                <Typography variant="h5" sx={{ fontWeight: 800 }}>
                                    GitHub
                                </Typography>
                                <Typography sx={{ color: 'rgba(255,255,255,0.72)', lineHeight: 1.65 }}>
                                    Open the official source repository and browse the current release.
                                </Typography>
                            </Stack>

                            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 2 }}>
                                <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.65)' }}>
                                    v1.0.0
                                </Typography>
                                <Typography variant="body2" sx={{ color: '#f1d4a3', fontWeight: 700 }}>
                                    github.com/IvanComp/AgANT-of-Empire
                                </Typography>
                            </Stack>
                        </Paper>
                    </Box>
                </Paper>

                <Box
                    sx={{
                        display: 'grid',
                        gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, minmax(0, 1fr))' },
                        gap: 3,
                        maxWidth: 980,
                        mx: 'auto',
                    }}
                >
                    {SIMULATION_MODES.map((mode) => (
                        <Paper
                            key={mode.id}
                            sx={{
                                p: 3,
                                minHeight: 280,
                                display: 'flex',
                                flexDirection: 'column',
                                justifyContent: 'space-between',
                                borderRadius: 4,
                                color: 'white',
                                bgcolor: mode.available ? 'rgba(18, 21, 25, 0.82)' : 'rgba(15, 16, 20, 0.55)',
                                border: mode.available ? '1px solid rgba(216,169,95,0.28)' : '1px solid rgba(255,255,255,0.07)',
                                boxShadow: mode.available ? '0 20px 80px rgba(0,0,0,0.26)' : 'none',
                            }}
                        >
                            <Stack spacing={2}>
                                <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1.5}>
                                    <Box>
                                        <Typography variant="h5" sx={{ fontWeight: 700 }}>
                                            {mode.title}
                                        </Typography>
                                        <Typography variant="body2" sx={{ color: mode.available ? '#d8a95f' : 'rgba(255,255,255,0.48)' }}>
                                            {mode.subtitle}
                                        </Typography>
                                    </Box>
                                </Stack>
                                <Typography sx={{ color: 'rgba(255,255,255,0.74)', lineHeight: 1.65 }}>
                                    {mode.description}
                                </Typography>
                            </Stack>

                            <Button
                                variant={mode.available ? 'contained' : 'outlined'}
                                disabled={!mode.available}
                                onClick={() => mode.available && onEnter(mode.id)}
                                sx={{
                                    mt: 3,
                                    alignSelf: 'flex-start',
                                    px: 2.2,
                                    py: 1,
                                    color: mode.available ? '#14110d' : 'rgba(255,255,255,0.45)',
                                    bgcolor: mode.available ? '#d8a95f' : 'transparent',
                                    borderColor: 'rgba(255,255,255,0.12)',
                                    '&:hover': mode.available ? { bgcolor: '#e4bb78' } : undefined,
                                }}
                            >
                                {mode.available ? 'Open simulation' : 'Coming soon'}
                            </Button>
                        </Paper>
                    ))}
                </Box>
            </Stack>
        </Box>
    );
}

function SimulationView({
    topology,
    topologyName,
    currentState,
    specialChambers,
    handleRun,
    loading,
    hasSimulation,
    logs,
    simTime,
    maxTime,
    setSimTime,
    isPlaying,
    setIsPlaying,
    playbackSpeed,
    setPlaybackSpeed,
    downloadFile,
    lineageFile,
    error,
    snackbarOpen,
    setSnackbarOpen,
    snackbarMessage,
    onBack,
    finalStats,
}) {
    const [analyticsOpen, setAnalyticsOpen] = useState(false);
    const [renderEnabled, setRenderEnabled] = useState(true);

    return (
        <Box sx={{ width: '100vw', height: '100vh', position: 'relative', overflow: 'hidden', bgcolor: '#080b12' }}>
            <Visualizer
                topology={topology}
                topologyName={topologyName}
                ants={currentState.ants}
                specialChambers={specialChambers}
                renderEnabled={renderEnabled}
            />

            <Box sx={{ position: 'absolute', top: 16, left: 16, zIndex: 8 }}>
                <Stack spacing={1.5}>
                    <Button
                        variant="outlined"
                        onClick={onBack}
                        sx={{
                            color: 'white',
                            borderColor: 'rgba(255,255,255,0.18)',
                            bgcolor: 'rgba(0,0,0,0.4)',
                            backdropFilter: 'blur(10px)',
                        }}
                    >
                        Back to home
                    </Button>
                    <Button
                        variant={renderEnabled ? 'contained' : 'outlined'}
                        onClick={() => setRenderEnabled((value) => !value)}
                        sx={{
                            alignSelf: 'flex-start',
                            color: renderEnabled ? '#1a130e' : 'white',
                            borderColor: 'rgba(255,255,255,0.18)',
                            bgcolor: renderEnabled ? '#d8a95f' : 'rgba(0,0,0,0.4)',
                            backdropFilter: 'blur(10px)',
                            '&:hover': {
                                bgcolor: renderEnabled ? '#e4bb78' : 'rgba(255,255,255,0.08)',
                            },
                        }}
                    >
                        {renderEnabled ? 'Pause 3D view' : 'Resume 3D view'}
                    </Button>
                </Stack>
            </Box>

            <ConfigForm onRun={handleRun} loading={loading} hasSimulation={hasSimulation} />

            <Stack spacing={2} sx={{ position: 'absolute', right: 16, top: 16, zIndex: 5 }}>
                <Legend />
                <AntSearchPanel lineageFile={lineageFile} />
                <EventLog logs={logs} simTime={simTime} />
            </Stack>

            <Box sx={{ position: 'absolute', right: 16, bottom: 120, zIndex: 7 }}>
                <Button
                    variant="contained"
                    onClick={() => setAnalyticsOpen(true)}
                    disabled={!hasSimulation}
                    sx={{
                        px: 2.4,
                        py: 1.1,
                        color: '#1a130e',
                        bgcolor: '#d8a95f',
                        '&:hover': { bgcolor: '#e4bb78' },
                    }}
                >
                    Open dashboard
                </Button>
            </Box>

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
                <Stack spacing={1.5}>
                    <Typography variant="subtitle2" sx={{ color: 'white', fontWeight: 'bold' }}>
                        Colony timeline
                    </Typography>
                    <Slider
                        value={simTime}
                        min={0}
                        max={maxTime}
                        step={0.25}
                        onChange={(_, value) => setSimTime(value)}
                        sx={{ color: '#d8a95f' }}
                    />
                    <Stack direction="row" spacing={1.5} alignItems="center" justifyContent="space-between">
                        <Stack direction="row" spacing={1}>
                            <Button variant="contained" onClick={() => setIsPlaying((v) => !v)} disabled={!hasSimulation}>
                                {isPlaying ? 'Pause' : 'Play'}
                            </Button>
                            <Button variant="outlined" onClick={() => { setSimTime(0); setIsPlaying(false); }} disabled={!hasSimulation}>
                                Reset
                            </Button>
                            {downloadFile && (
                                <Button variant="outlined" href={`${API_BASE}/download/${downloadFile}`}>
                                    CSV
                                </Button>
                            )}
                        </Stack>
                        <Stack direction="row" spacing={2} alignItems="center">
                            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                                t = {simTime.toFixed(1)} min
                            </Typography>
                            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                                Speed x{playbackSpeed.toFixed(1)}
                            </Typography>
                            <Slider
                                min={0.5}
                                max={6}
                                step={0.5}
                                value={playbackSpeed}
                                onChange={(_, value) => setPlaybackSpeed(value)}
                                sx={{ width: 140, color: '#8dc16b' }}
                            />
                        </Stack>
                    </Stack>
                </Stack>
            </Paper>

            {loading && (
                <Box sx={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', zIndex: 10, bgcolor: 'rgba(5,8,12,0.55)' }}>
                    <Stack alignItems="center" spacing={2}>
                        <CircularProgress sx={{ color: '#d8a95f' }} />
                        <Typography sx={{ color: 'white' }}>The colony is evolving...</Typography>
                    </Stack>
                </Box>
            )}

            {error && (
                <Alert severity="error" sx={{ position: 'absolute', left: 16, bottom: 140, zIndex: 8 }}>
                    {error}
                </Alert>
            )}

            <Snackbar
                open={snackbarOpen}
                autoHideDuration={5000}
                onClose={() => setSnackbarOpen(false)}
                message={snackbarMessage}
            />

            <AnalyticsModal
                open={analyticsOpen}
                onClose={() => setAnalyticsOpen(false)}
                logs={logs}
                summary={finalStats}
                title="Batch Colony Dashboard"
                subtitle={hasSimulation ? `Final snapshot at ${finalStats.finalTime} simulated minutes.` : ''}
            />
        </Box>
    );
}

function App() {
    const [screen, setScreen] = useState('home');
    const [topologyName, setTopologyName] = useState('mesh9');
    const [topology, setTopology] = useState(null);
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [simTime, setSimTime] = useState(0);
    const [maxTime, setMaxTime] = useState(100);
    const [isPlaying, setIsPlaying] = useState(false);
    const [playbackSpeed, setPlaybackSpeed] = useState(1);
    const [hasSimulation, setHasSimulation] = useState(false);
    const [lineageFile, setLineageFile] = useState(null);
    const [downloadFile, setDownloadFile] = useState(null);
    const [snackbarOpen, setSnackbarOpen] = useState(false);
    const [snackbarMessage, setSnackbarMessage] = useState('');

    useEffect(() => {
        if (screen !== 'batch-simulation') return undefined;
        axios.get(`${API_BASE}/topology/${topologyName}`)
            .then((res) => setTopology(res.data))
            .catch((err) => console.error(err));
        return undefined;
    }, [topologyName, screen]);

    const handleRun = async (config) => {
        setLoading(true);
        setError(null);
        setHasSimulation(false);
        setLineageFile(null);
        setDownloadFile(null);
        setTopologyName(config.TOPOLOGY_NAME);

        try {
            const runRes = await axios.post(`${API_BASE}/run`, config);
            const logRes = await axios.get(`${API_BASE}/log/${runRes.data.logfile}`);
            const data = logRes.data;
            setLogs(data);
            setSimTime(0);
            setMaxTime(Math.max(1, Math.ceil(Number(data.at(-1)?.simTime || config.SIM_TIME || 1))));
            setIsPlaying(false);
            setHasSimulation(true);
            setLineageFile(runRes.data.lineageFile);
            setDownloadFile(runRes.data.aggregateLogfile || runRes.data.logfile);
                setSnackbarMessage(
                    runRes.data.repetitions > 1
                    ? `Average of ${runRes.data.repetitions} runs ready (${Number(runRes.data.wallTime).toFixed(3)}s, ${Number(runRes.data.eventCount).toFixed(0)} average events)`
                    : `Simulation completed in ${Number(runRes.data.wallTime).toFixed(3)}s with ${Number(runRes.data.eventCount).toFixed(0)} events`
                );
            setSnackbarOpen(true);
        } catch (err) {
            setError(err.response?.data?.error || err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!isPlaying) return undefined;
        const interval = setInterval(() => {
            setSimTime((current) => {
                const next = current + (0.25 * playbackSpeed);
                if (next >= maxTime) {
                    setIsPlaying(false);
                    return maxTime;
                }
                return next;
            });
        }, 100);
        return () => clearInterval(interval);
    }, [isPlaying, playbackSpeed, maxTime]);

    const currentState = useMemo(() => {
        const ants = {};
        const events = [];
        for (const rawLog of logs) {
            const log = {
                ...rawLog,
                simTime: Number(rawLog.simTime),
                antId: Number(rawLog.antId),
                position: Number(rawLog.position),
                destination: Number(rawLog.destination),
                partnerId: Number(rawLog.partnerId),
                childId: Number(rawLog.childId),
                hunger: Number(rawLog.hunger),
                thirst: Number(rawLog.thirst),
                energy: Number(rawLog.energy),
                generation: Number(rawLog.generation),
            };

            if (log.simTime > simTime) break;
            events.push(log);
            if (log.antId < 0) continue;

            ants[log.antId] ??= {
                id: log.antId,
                sex: log.sex,
                position: log.position,
                destination: log.destination,
                hunger: log.hunger,
                thirst: log.thirst,
                energy: log.energy,
                generation: log.generation,
                state: 'active',
                alive: true,
            };

            ants[log.antId] = {
                ...ants[log.antId],
                sex: log.sex,
                position: log.position,
                destination: log.destination,
                hunger: log.hunger,
                thirst: log.thirst,
                energy: log.energy,
                generation: log.generation,
            };

            if (log.event === 'nap_start') ants[log.antId].state = 'sleeping';
            if (log.event === 'nap_end') ants[log.antId].state = 'active';
            if (log.event === 'mate') ants[log.antId].state = 'mating';
            if (log.event === 'death') {
                ants[log.antId].state = 'dead';
                ants[log.antId].alive = false;
            }
        }

        return { ants, events };
    }, [logs, simTime]);

    const finalStats = useMemo(() => {
        const relevant = logs || [];
        const ants = {};
        for (const rawLog of relevant) {
            const antId = Number(rawLog.antId);
            if (antId < 0) continue;
            ants[antId] = {
                sex: rawLog.sex,
                state: rawLog.event === 'death' ? 'dead' : rawLog.event === 'nap_start' ? 'sleeping' : rawLog.event === 'nap_end' ? 'active' : ants[antId]?.state || 'active',
                alive: rawLog.event !== 'death',
            };
            if (rawLog.event !== 'death' && ants[antId]?.alive === false) {
                ants[antId].alive = false;
            }
        }
        const living = Object.values(ants).filter((ant) => ant.alive !== false).length;
        const sleeping = Object.values(ants).filter((ant) => ant.alive !== false && ant.state === 'sleeping').length;
        const females = Object.values(ants).filter((ant) => ant.sex === 'F' && ant.alive !== false).length;
        const awakeFemales = Object.values(ants).filter((ant) => ant.sex === 'F' && ant.alive !== false && ant.state !== 'sleeping').length;
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
            finalTime: relevant.length ? Number(relevant.at(-1)?.simTime || 0).toFixed(1) : '0.0',
        };
    }, [logs]);

    const specialChambers = useMemo(() => deriveSpecialChambers(topology), [topology]);

    if (screen === 'home') {
        return <HomePage onEnter={(modeId) => setScreen(modeId)} />;
    }

    if (screen === 'live-colony') {
        return <LiveColonyView onBack={() => setScreen('home')} />;
    }

    return (
        <SimulationView
            topology={topology}
            topologyName={topologyName}
            currentState={currentState}
            specialChambers={specialChambers}
            handleRun={handleRun}
            loading={loading}
            hasSimulation={hasSimulation}
            logs={logs}
            simTime={simTime}
            maxTime={maxTime}
            setSimTime={setSimTime}
            isPlaying={isPlaying}
            setIsPlaying={setIsPlaying}
            playbackSpeed={playbackSpeed}
            setPlaybackSpeed={setPlaybackSpeed}
            downloadFile={downloadFile}
            lineageFile={lineageFile}
            error={error}
            snackbarOpen={snackbarOpen}
            setSnackbarOpen={setSnackbarOpen}
            snackbarMessage={snackbarMessage}
            onBack={() => setScreen('home')}
            finalStats={finalStats}
        />
    );
}

export default App;
