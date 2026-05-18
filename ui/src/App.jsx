import React, { useState, useEffect, useMemo } from 'react';
import { Box, Typography, Slider, Button, CircularProgress, Paper, Alert, Snackbar, IconButton, Tooltip } from '@mui/material';
import { GitHub, CheckCircle, Close, Flag } from '@mui/icons-material';
import ConfigForm from './ConfigForm';
import Visualizer from './Visualizer';
import StatsPanel from './StatsPanel';
import Legend from './Legend';
import EventLog from './EventLog';
import AnimatedRobots from './AnimatedRobots';
import RobotStudio from './RobotStudio';
import AnalyticsModal from './AnalyticsModal';
import axios from 'axios';

const API_BASE = '/api';
const ARCHITECTURE_SWITCH_VISIBLE_SECONDS = 8;

const architectureSwitchMessage = (fromArch, toArch) => `Architecture changed from ${fromArch} to ${toArch}`;

function App() {
  // Check for studio mode
  const isStudio = new URLSearchParams(window.location.search).has('studio');

  if (isStudio) {
    return <RobotStudio />;
  }

  const [topologyName, setTopologyName] = useState('mesh25');
  const [topology, setTopology] = useState(null);
  const [customTopology, setCustomTopology] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [simTime, setSimTime] = useState(0);
  const [maxTime, setMaxTime] = useState(100);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);

  const [hasSimulation, setHasSimulation] = useState(false);
  const [currentLogfile, setCurrentLogfile] = useState(null);
  const [currentDownloadFile, setCurrentDownloadFile] = useState(null);
  const [currentConfig, setCurrentConfig] = useState(null);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [analyticsOpen, setAnalyticsOpen] = useState(false);

  // MOCK LOGS FOR VERIFICATION - Disabled for production/homepage view
  /*
  useEffect(() => {
    setLogs([
      { simTime: 1.0, event: 'create', itemId: 1, itemImportance: 0, position: 0, robotId: -1 },
      { simTime: 2.0, event: 'create', itemId: 2, itemImportance: 1, position: 0, robotId: -1 },
      { simTime: 3.0, event: 'create', itemId: 3, itemImportance: 2, position: 0, robotId: -1 },
    ]);
    setSimTime(5.0);
    setTopologyName('mesh25'); // Ensure topology is set so Visualizer doesn't crash if it tries to render
  }, []);
  */

  // Fetch topology when name changes
  useEffect(() => {
    if (topologyName === 'custom') {
      if (customTopology) {
        setTopology(customTopology);
      }
      return;
    }

    axios.get(`${API_BASE}/topology/${topologyName}`)
      .then(res => setTopology(res.data))
      .catch(err => console.error(err));
  }, [topologyName, customTopology]);

  // Run simulation
  const handleRun = async (config) => {
    setLoading(true);
    setError(null);
    setCustomTopology(config.CUSTOM_TOPOLOGY || null);
    if (config.CUSTOM_TOPOLOGY) {
      setTopology(config.CUSTOM_TOPOLOGY);
    }
    setTopologyName(config.TOPOLOGY_NAME);
    setHasSimulation(false);
    setCurrentConfig(config);
    setCurrentDownloadFile(null);

    try {
      const res = await axios.post(`${API_BASE}/run`, config);
      if (res.data.success) {
        const logRes = await axios.get(`${API_BASE}/log/${res.data.logfile}`);
        const data = logRes.data;
        setLogs(data);
        if (data.length > 0) {
          const last = data[data.length - 1];
          setMaxTime(Math.ceil(last.simTime));
        }
        setSimTime(0);
        setIsPlaying(false);
        setHasSimulation(true);
        setCurrentLogfile(res.data.logfile);
        setCurrentDownloadFile(res.data.aggregateLogfile || res.data.logfile);
        // Show execution time and event count
        setSnackbarMessage(
          res.data.repetitions > 1
            ? `Average over ${res.data.repetitions} runs ready (${Number(res.data.wallTime).toFixed(4)}s avg wall time, ${Number(res.data.eventCount).toFixed(1)} avg events)`
            : `Simulation completed in ${Number(res.data.wallTime).toFixed(4)}s (${Number(res.data.eventCount).toFixed(0)} events processed)`
        );
        setSnackbarOpen(true);
      } else {
        setError('Simulation failed: ' + (res.data.error || 'Unknown error'));
      }
    } catch (err) {
      console.error(err);
      setError('Simulation failed: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoading(false);
    }
  };

  // Playback loop
  useEffect(() => {
    let interval;
    if (isPlaying) {
      interval = setInterval(() => {
        setSimTime(prev => {
          const next = prev + (0.1 * playbackSpeed);
          if (next >= maxTime) {
            setIsPlaying(false);
            return maxTime;
          }
          return next;
        });
      }, 100);
    }
    return () => clearInterval(interval);
  }, [isPlaying, maxTime, playbackSpeed]);

  const architectureSwitches = useMemo(() => {
    if (!logs || logs.length === 0 || !currentConfig) return [];

    const switches = [];
    let prevArch = currentConfig.INITIAL_ARCHITECTURE || 'semi-decentralized';

    logs.forEach(event => {
      if (event.event && event.event.startsWith('switch_architecture_')) {
        const newArch = event.event.replace('switch_architecture_', '');
        switches.push({
          time: event.simTime,
          from: prevArch,
          to: newArch,
          message: architectureSwitchMessage(prevArch, newArch)
        });
        prevArch = newArch;
      }
    });
    return switches;
  }, [logs, currentConfig]);

  // Calculate all architecture switches for the timeline
  const archSwitchMarks = useMemo(() => {
    return architectureSwitches.map((architectureSwitch) => ({
      value: architectureSwitch.time,
      label: (
        <Tooltip title={architectureSwitch.message} arrow>
          <Box
            sx={{
              color: 'error.main',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              mt: -4.5, // Move it up to sit on the slider
              cursor: 'help',
              zIndex: 5
            }}
          >
            <Flag fontSize="small" />
          </Box>
        </Tooltip>
      )
    }));
  }, [architectureSwitches]);

  const activeArchitectureSwitch = useMemo(() => {
    if (currentConfig?.ARCHITECTURE !== 'dynamic-adaptation') return null;

    return [...architectureSwitches]
      .reverse()
      .find((architectureSwitch) => (
        simTime >= architectureSwitch.time
        && simTime - architectureSwitch.time <= ARCHITECTURE_SWITCH_VISIBLE_SECONDS
      )) || null;
  }, [architectureSwitches, currentConfig, simTime]);

  // Filter logs for current time
  const currentState = useMemo(() => {
    if (!logs || logs.length === 0) return { robots: {}, items: {}, currentArchitecture: null, archSwitches: [] };

    const robots = {};
    const items = {};
    let currentArchitecture = null;
    let prevArchitecture = null;
    const archSwitches = [];

    for (const event of logs) {
      // Always process all logs to find all switches, but only return state up to simTime
      // Wait, for the timeline markers we need ALL switches across the entire simulation, 
      // not just up to simTime. But currentState is re-calculated when simTime changes.
      // Actually, for the markers to be static on the timeline, we should calculate archSwitches 
      // once based on `logs` and not depend on `simTime` for the array itself.
      // However, to keep it simple and consistent with existing code structure, I'll calculate it here.
      // But wait, if I break at simTime, I won't see future switches.
      // I should separate archSwitches calculation or iterate through all logs for it.

      // Let's iterate through all logs for switches, but only process robots/items up to simTime.

      const { robotId, itemId, itemImportance, position, destination, event: evtType } = event;

      // Track architecture switches for dynamic-adaptation (process ALL events)
      if (evtType && evtType.startsWith('switch_architecture_')) {
        const newArch = evtType.replace('switch_architecture_', '');
        const fromArch = prevArchitecture || currentConfig?.INITIAL_ARCHITECTURE || 'semi-decentralized';
        archSwitches.push({ time: event.simTime, from: fromArch, to: newArch });
        prevArchitecture = newArch;

        // Only update currentArchitecture if this event is in the past relative to simTime
        if (event.simTime <= simTime) {
          currentArchitecture = newArch;
        }
      }

      if (event.simTime > simTime) continue; // Skip state processing for future events

      // ... rest of state processing ...

      if (robotId !== -1) {
        if (!robots[robotId]) robots[robotId] = { id: robotId, position: -1, destination: -1, item: null, itemImportance: null, failed: false, rescuing: false };

        robots[robotId].position = position;
        robots[robotId].destination = destination;

        // Track robot failure state - stays failed until recovery
        if (evtType === 'fail') {
          robots[robotId].failed = true;
          robots[robotId].rescuing = false;
        } else if (evtType === 'recovery' || evtType === 'recover') {
          // This is the failed robot being recovered
          robots[robotId].failed = false;
          robots[robotId].rescuing = false;
        } else if (evtType === 'rescue') {
          // This robot is going to rescue another robot
          robots[robotId].rescuing = true;
        }

        // Clear rescuing state when robot picks up an item (rescue complete)
        if (evtType === 'startLoading' && robots[robotId].rescuing) {
          robots[robotId].rescuing = false;
        }

        // If the agent reaches the rescue target and there is no task to load,
        // it leaves the rescue phase and starts returning to the source.
        if (evtType === 'move' && robots[robotId].rescuing && itemId === -1 && position === destination) {
          robots[robotId].rescuing = false;
        }

        if (evtType === 'deliver' || evtType === 'drop' || evtType === 'recovery' || evtType === 'recover') {
          robots[robotId].item = null;
          robots[robotId].itemImportance = null;
        } else if (itemId !== -1) {
          robots[robotId].item = itemId;
          robots[robotId].itemImportance = itemImportance;
        } else if (evtType === 'move') {
          robots[robotId].item = null;
          robots[robotId].itemImportance = null;
        }
      }

      if (itemId !== -1) {
        if (!items[itemId]) items[itemId] = { id: itemId, position: -1, importance: itemImportance, status: 'created' };

        if (evtType === 'create') {
          items[itemId].position = position;
          items[itemId].status = 'available';
        } else if (evtType === 'expire') {
          items[itemId].status = 'expired';
        } else if (evtType === 'deliver') {
          items[itemId].status = 'delivered';
          items[itemId].position = -1;
        } else if (evtType === 'drop') {
          items[itemId].position = position;
          items[itemId].status = 'available';
        } else if (evtType === 'startLoading') {
          items[itemId].status = 'moving';
          items[itemId].position = -1;
        }
      }
    }
    return { robots, items, currentArchitecture };
  }, [logs, simTime]);

  return (
    <Box sx={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Main 3D View */}
      <Box sx={{ flex: 1, position: 'relative', bgcolor: '#1a1a1a' }}>
        {loading && (
          <Box sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 2000,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 2
          }}>
            <CircularProgress size={60} />
            <Typography variant="h6" sx={{ color: 'white', fontWeight: 'bold' }}>Simulation is Running...</Typography>
            <Typography variant="body2" sx={{ color: 'rgba(255, 255, 255, 0.7)' }}>Please Wait!</Typography>
          </Box>
        )}

        {error && (
          <Alert
            severity="error"
            onClose={() => setError(null)}
            sx={{ position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 2000, minWidth: 400 }}
          >
            {error}
          </Alert>
        )}

        {hasSimulation && activeArchitectureSwitch && (
          <Box
            sx={{
              position: 'absolute',
              top: 18,
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 1500,
              px: 2,
              py: 0.9,
              borderRadius: 1.5,
              bgcolor: 'rgba(255, 193, 7, 0.18)',
              border: '1px solid rgba(255, 193, 7, 0.75)',
              boxShadow: '0 10px 30px rgba(0, 0, 0, 0.28)',
              pointerEvents: 'none'
            }}
          >
            <Typography
              variant="body2"
              sx={{
                color: '#FFD54F',
                fontWeight: 800,
                textShadow: '0 1px 2px rgba(0,0,0,0.7)',
                letterSpacing: 0.2
              }}
            >
              {activeArchitectureSwitch.message}
            </Typography>
          </Box>
        )}

        {!hasSimulation && !loading && (
          <>
            <AnimatedRobots />
            <Box sx={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              textAlign: 'center',
              color: 'white',
              zIndex: 1
            }}>
              <img src="/logo.png" alt="COORDINATE 2.0" style={{ maxWidth: '300px', width: '100%', height: 'auto' }} />
              <Typography variant="body1" sx={{ mt: 2, opacity: 0.9, maxWidth: 820, fontSize: '0.95rem' }}>
                A Lightweight, Customizable, and Interactive Discrete Event Simulator for Fault-Tolerant Multi-Agent Systems.
              </Typography>
              <Box sx={{
                mt: 2.5,
                p: 1.5,
                borderRadius: 1,
                bgcolor: 'rgba(0, 0, 0, 0.35)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                display: 'inline-flex',
                flexDirection: 'column',
                gap: 0.5,
                textAlign: 'center'
              }}>
                <Typography variant="body2" sx={{ opacity: 0.95 }}>1. Define your simulation scenario</Typography>
                <Typography variant="body2" sx={{ opacity: 0.95 }}>2. Run the simulation</Typography>
                <Typography variant="body2" sx={{ opacity: 0.95 }}>3. Review the timeline and outcomes</Typography>
              </Box>
            </Box>

            {/* GitHub Footer */}
            <Box
              component="a"
              href="https://github.com/IvanComp/COORDINATE-2.0"
              target="_blank"
              rel="noopener noreferrer"
              sx={{
                position: 'absolute',
                bottom: 16,
                left: '50%',
                transform: 'translateX(-50%)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 0.3,
                color: 'rgba(255, 255, 255, 0.6)',
                textDecoration: 'none',
                cursor: 'pointer',
                transition: 'color 0.2s',
                '&:hover': {
                  color: 'rgba(255, 255, 255, 0.9)'
                },
                zIndex: 1
              }}
            >
              <GitHub fontSize="small" />
              <Typography variant="caption" sx={{ fontFamily: 'monospace', lineHeight: 1 }}>v1.0.1</Typography>
            </Box>
          </>
        )}

        {topology && hasSimulation && (
          <Visualizer
            topology={topology}
            robots={currentState.robots}
            items={currentState.items}
            topologyName={topologyName}
            logs={logs}
            simTime={simTime}
          />
        )}

        {/* Config Panel Overlay */}
        <ConfigForm onRun={handleRun} loading={loading} hasSimulation={hasSimulation} />

        {/* Top-Left Container (Stats, Legend, Event Log) */}
        {hasSimulation && (
          <Box sx={{
            position: 'absolute',
            top: 16,
            left: 16,
            display: 'flex',
            flexDirection: 'column',
            gap: 1, // Consistent 8px spacing
            zIndex: 1000,
            alignItems: 'flex-start',
            maxWidth: 'calc(100vw - 400px)'
          }}>
            {/* Stats Panel */}
            <Box
              sx={{
                p: 2,
                bgcolor: 'rgba(0, 0, 0, 0.6)',
                backdropFilter: 'blur(10px)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: 1,
                display: 'flex',
                alignItems: 'center',
                gap: 2,
                width: 'fit-content'
              }}
            >
              <img
                src="/logo.png"
                alt="COORDINATE 2.0"
                onClick={() => {
                  setHasSimulation(false);
                  setLogs([]);
                  setSimTime(0);
                  setMaxTime(100);
                  setCurrentLogfile(null);
                  setCurrentDownloadFile(null);
                  setCurrentConfig(null);
                  setIsPlaying(false);
                  setError(null);
                }}
                style={{ height: '32px', width: 'auto', cursor: 'pointer' }}
                title="Back to Home"
              />
              <StatsPanel logs={logs} simTime={simTime} />
            </Box>

            {/* Legend */}
            <Legend />

            {/* Event Log */}
            <EventLog logs={logs} simTime={simTime} />
          </Box>
        )}
      </Box>

      {/* Timeline Controls */}
      {hasSimulation && (
        <Paper
          sx={{
            p: 2,
            borderRadius: 0,
            bgcolor: 'rgba(255, 255, 255, 0.95)',
            backdropFilter: 'blur(10px)',
            position: 'relative'
          }}
          elevation={8}
        >
          <Typography gutterBottom>Time: {simTime.toFixed(1)}s / {maxTime.toFixed(1)}s</Typography>
          <Slider
            value={simTime}
            min={0}
            max={maxTime}
            step={0.1}
            marks={archSwitchMarks}
            onChange={(_, v) => { setIsPlaying(false); setSimTime(v); }}
          />
          <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center' }}>
            <Button variant="contained" onClick={() => setIsPlaying(!isPlaying)}>
              {isPlaying ? 'Pause' : 'Play'}
            </Button>
            <Button onClick={() => setSimTime(0)}>Reset</Button>
            <Button
              variant={playbackSpeed === 0.1 ? 'contained' : 'outlined'}
              onClick={() => setPlaybackSpeed(0.1)}
            >
              0.1x
            </Button>
            <Button
              variant={playbackSpeed === 0.5 ? 'contained' : 'outlined'}
              onClick={() => setPlaybackSpeed(0.5)}
            >
              0.5x
            </Button>
            <Button
              variant={playbackSpeed === 1 ? 'contained' : 'outlined'}
              onClick={() => setPlaybackSpeed(1)}
            >
              1x
            </Button>
            <Button
              variant={playbackSpeed === 5 ? 'contained' : 'outlined'}
              onClick={() => setPlaybackSpeed(5)}
            >
              5x
            </Button>
            <Button
              variant={playbackSpeed === 10 ? 'contained' : 'outlined'}
              onClick={() => setPlaybackSpeed(10)}
            >
              10x
            </Button>
          </Box>

          {/* Coordination Mechanism Display */}
          {currentConfig?.ARCHITECTURE && (
            <Box sx={{
              position: 'absolute',
              left: 16,
              bottom: 16,
              display: 'flex',
              alignItems: 'center',
              gap: 1.5,
              color: 'rgba(0, 0, 0, 0.7)'
            }}>
              <Box sx={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                bgcolor: isPlaying ? '#4CAF50' : '#9E9E9E',
                animation: isPlaying ? 'flash 1.5s infinite ease-in-out' : 'none',
                boxShadow: isPlaying ? '0 0 8px #4CAF50' : 'none'
              }} />
              <Typography variant="body2" sx={{ fontWeight: 'bold', fontSize: '0.9rem' }}>
                Coordination Mechanism: <span style={{ color: '#1976D2' }}>
                  {currentConfig.ARCHITECTURE === 'dynamic-adaptation'
                    ? `${currentState.currentArchitecture || currentConfig.INITIAL_ARCHITECTURE || 'semi-decentralized'} (dynamic)`
                    : currentConfig.ARCHITECTURE}
                </span>
              </Typography>
            </Box>
          )}

          {/* Download Button */}
          <Box sx={{ position: 'absolute', right: 16, bottom: 16, display: 'flex', gap: 1 }}>
            <Button
              variant="outlined"
              color="primary"
              size="small"
              onClick={() => setAnalyticsOpen(true)}
            >
              📊 Dashboard
            </Button>
            <Button
              variant="contained"
              color="primary"
              size="small"
              onClick={() => {
                if (currentDownloadFile) {
                  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
                  const repetitions = currentConfig?.N_REPETITIONS ?? 1;
                  const friendlyName = repetitions > 1
                    ? `simulation_average_${timestamp}.csv`
                    : `simulation_results_${timestamp}.csv`;
                  window.location.href = `${API_BASE}/download/${currentDownloadFile}?name=${friendlyName}`;
                }
              }}
            >
              📋 {currentConfig?.N_REPETITIONS > 1 ? 'Download Average CSV' : 'Download Simulation Log'}
            </Button>
          </Box>
        </Paper>
      )}

      <AnalyticsModal
        open={analyticsOpen}
        onClose={() => setAnalyticsOpen(false)}
        logs={logs}
        topology={topology}
        topologyName={topologyName}
        nAgents={currentConfig?.N_ROBOTS ?? null}
      />

      {/* Success Snackbar */}
      <Snackbar
        open={snackbarOpen}
        autoHideDuration={6000}
        onClose={() => setSnackbarOpen(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setSnackbarOpen(false)}
          severity="success"
          icon={<CheckCircle />}
          sx={{ width: '100%', fontSize: '1rem', fontWeight: 'bold' }}
        >
          {snackbarMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
}

export default App;
