import React, { useState, useEffect } from 'react';
import {
    TextField,
    Button,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    Typography,
    Box,
    Divider,
    Paper,
    IconButton,
    Collapse,
    Tabs,
    Tab
} from '@mui/material';
import { Settings, ExpandMore, ExpandLess, HelpOutline, Tune, Add, DeleteOutline, Bolt } from '@mui/icons-material';
import { InputAdornment, Tooltip } from '@mui/material';
import axios from 'axios';
import RTLolaEditor from './RTLolaEditor';

const API_BASE = '/api';

const DEFAULTS = {
    RESULTS_DIR: "results",
    SIM_TIME: 1000,
    ARCHITECTURE: "decentralized",
    TOPOLOGY_NAME: "mesh25",
    N_ROOMS: 25,
    SOURCE: 0,
    TARGETS: -1,
    ITEM_SPAWNING_TIME: 120,
    ITEM_SPAWNING_DISTR: "exponential",
    ITEM_SPAWNING_TRACE: "_",
    IMPORTANCE_PROBABILITIES: [0.5, 0.1, 0.4],
    EXPIRATION_TIME: [-1, -1, -1],
    EXPIRATION_DISTR: ["exponential", "exponential", "exponential"],
    N_ROBOTS: 20,
    N_MALICIOUS: 0,
    MALICIOUS_FAKE_FAILURES: false,
    FIND_ROUTE_STRATEGY: "breadth",
    N_REPETITIONS: 1,
    FAIL_PROB: 0.05,
    COMM_FAIL_PROB: 0.003,
    LOAD_TIME: 1.0, LOAD_DISTR: "exponential", LOAD_TRACE: "_",
    MOVEMENT_TIME: 5.0, MOVEMENT_DISTR: "exponential", MOVEMENT_TRACE: "_",
    DROP_TIME: 1.0, DROP_DISTR: "exponential", DROP_TRACE: "_",
    COMP_TIME: 0.1, COMP_DISTR: "exponential", COMP_TRACE: "_",
    COMM_TIME: 0.03, COMM_DISTR: "exponential", COMM_TRACE: "_",
    RECOVERY_TIME: 1800.0, RECOVERY_DISTR: "exponential", RECOVERY_TRACE: "_",
    PHASES: [],
    LOG_ITEM: true,
    LOG_DELIVERY: true,
    LOG_LOAD: true,
    LOG_DROP: true,
    LOG_EXPIRE: true,
    LOG_MOVE: true,
    LOG_FAIL: true,
    LOG_RECOVERY: true,
    LOG_HELP: true,
    LOG_FAKE: true,
    LOG_RESCUE: true,
};

const FIELD_METADATA = {
    N_ROOMS: { label: "Number of Rooms", description: "Total number of rooms in the hospital layout." },
    TOPOLOGY_NAME: { label: "Topology", description: "The physical layout of the hospital floor." },
    ARCHITECTURE: { label: "Coordination Mechanism", description: "The strategy agents use to coordinate tasks." },
    N_ROBOTS: { label: "Number of Agents", description: "Total number of agents in the fleet." },
    N_MALICIOUS: { label: "Number of Malicious Agent", description: "Number of agents that may fail or act maliciously." },
    SIM_TIME: { label: "Simulation Window (s)", description: "Duration of the simulation in seconds." },
    N_REPETITIONS: { label: "N° Repetitions", description: "Number of independent simulation runs used to compute the final average CSV." },
    FAIL_PROB: { label: "Failure Probability", description: "Probability of an agent failing during operation (0-1)." },
    ITEM_SPAWNING_TIME: { label: "Item Spawning Time", description: "Average time (in seconds) between new item requests." },
    ITEM_SPAWNING_DISTR: { label: "Event Arrival Distribution", description: "Distribution used to generate new item requests over time." },
    LOAD_TIME: { label: "Load Time", description: "Average time to load an item." },
    MOVEMENT_TIME: { label: "Movement Time", description: "Average time to move between adjacent rooms." },
    DROP_TIME: { label: "Drop Time", description: "Average time to drop an item." },
    COMP_TIME: { label: "Computation Time", description: "Decision-making overhead per action." },
    COMM_TIME: { label: "Communication Time", description: "Communication overhead per interaction." },
    RECOVERY_TIME: { label: "Recovery Time", description: "Average time to recover after a failure." },
};

const ARCHITECTURES = [
    "decentralized",
    "semi-decentralized",
    "centralized-proximity",
    "centralized-importance",
    "centralized-proximp",
    "centralized-impprox",
    "dynamic-adaptation",
];

const DISTRIBUTION_OPTIONS = [
    { value: 'exponential', label: 'Exponential' },
    { value: 'uniform', label: 'Uniform' },
    { value: 'deterministic', label: 'Deterministic' },
];

// Map N_ROOMS to appropriate topology
const TOPOLOGY_MAP = {
    4: ['mesh4', 'ring4', 'tree4'],
    9: ['mesh9', 'ring9', 'tree9'],
    16: ['mesh16', 'ring16', 'tree16'],
    25: ['mesh25', 'ring25', 'tree25'],
    36: ['mesh36', 'ring36', 'tree36'],
    49: ['mesh49', 'ring49', 'tree49'],
    73: ['GUH73']
};

function AgentTabIcon() {
    return (
        <svg width="16" height="16" viewBox="0 0 16 16" style={{ display: 'block' }} aria-hidden="true">
            <rect x="5" y="6" width="6" height="7" fill="#9E9E9E" rx="1" />
            <circle cx="8" cy="4" r="2.5" fill="#9E9E9E" />
            <circle cx="7" cy="4" r="0.5" fill="white" />
            <circle cx="9" cy="4" r="0.5" fill="white" />
        </svg>
    );
}

function topologyLabel(topologyName) {
    if (topologyName.startsWith('mesh')) return 'mesh';
    if (topologyName.startsWith('ring')) return 'ring';
    if (topologyName.startsWith('tree')) return 'tree';
    return topologyName;
}

function ConfigForm({ onRun, loading, hasSimulation = false }) {
    const [config, setConfig] = useState(DEFAULTS);
    const [topologies, setTopologies] = useState([]);
    const [expanded, setExpanded] = useState(true);
    const [rtlolaEditorOpen, setRtlolaEditorOpen] = useState(false);
    const [activeTab, setActiveTab] = useState('configuration');

    useEffect(() => {
        axios.get(`${API_BASE}/topologies`)
            .then(res => setTopologies(res.data))
            .catch(err => console.error(err));
    }, []);

    useEffect(() => {
        setExpanded(!hasSimulation);
    }, [hasSimulation]);

    const handleChange = (field, value) => {
        const newConfig = { ...config, [field]: value };

        // Auto-update topology when N_ROOMS changes
        if (field === 'N_ROOMS') {
            const validTopologies = TOPOLOGY_MAP[value];
            if (validTopologies && validTopologies.length > 0) {
                // Pick the first mesh topology if available
                const meshTopo = validTopologies.find(t => t.startsWith('mesh'));
                newConfig.TOPOLOGY_NAME = meshTopo || validTopologies[0];
            }
        }

        setConfig(newConfig);
    };

    const handlePhaseChange = (index, field, value) => {
        setConfig(prev => ({
            ...prev,
            PHASES: prev.PHASES.map((phase, i) => (
                i === index ? { ...phase, [field]: value } : phase
            ))
        }));
    };

    const addPhase = () => {
        const fallbackStart = config.PHASES.length > 0
            ? Number(config.PHASES[config.PHASES.length - 1].end || 0)
            : 0;
        const fallbackEnd = Math.min(config.SIM_TIME, fallbackStart + Math.max(1, Math.round(config.SIM_TIME / 2)));
        setConfig(prev => ({
            ...prev,
            PHASES: [
                ...prev.PHASES,
                {
                    start: fallbackStart,
                    end: fallbackEnd,
                    FAIL_PROB: prev.FAIL_PROB,
                    COMM_FAIL_PROB: prev.COMM_FAIL_PROB,
                    RECOVERY_TIME: prev.RECOVERY_TIME,
                }
            ]
        }));
    };

    const removePhase = (index) => {
        setConfig(prev => ({
            ...prev,
            PHASES: prev.PHASES.filter((_, i) => i !== index)
        }));
    };

    const sanitizePhases = (phases) => phases
        .map(phase => ({
            start: Number(phase.start),
            end: Number(phase.end),
            FAIL_PROB: Number(phase.FAIL_PROB),
            COMM_FAIL_PROB: Number(phase.COMM_FAIL_PROB),
            RECOVERY_TIME: Number(phase.RECOVERY_TIME),
        }))
        .filter(phase => Number.isFinite(phase.start)
            && Number.isFinite(phase.end)
            && phase.end > phase.start
            && Number.isFinite(phase.FAIL_PROB)
            && Number.isFinite(phase.COMM_FAIL_PROB)
            && Number.isFinite(phase.RECOVERY_TIME));

    const handleSubmit = () => {
        const configToRun = {
            ...config,
            PHASES: sanitizePhases(config.PHASES),
        };
        // If dynamic-adaptation is selected, open RTLola editor first
        if (configToRun.ARCHITECTURE === 'dynamic-adaptation') {
            setRtlolaEditorOpen(true);
        } else {
            // For other architectures, run immediately
            onRun(configToRun);
        }
    };

    const handleRtlolaSave = (specFile) => {
        // Close editor and run simulation with custom spec file
        setRtlolaEditorOpen(false);
        const configWithSpec = {
            ...config,
            PHASES: sanitizePhases(config.PHASES),
            RTLOLA_SPEC_FILE: specFile
        };
        onRun(configWithSpec);
    };

    const handleRtlolaClose = () => {
        setRtlolaEditorOpen(false);
    };

    // Get valid topologies for current N_ROOMS
    const validTopologies = TOPOLOGY_MAP[config.N_ROOMS] || [];
    const availableTopologies =
        topologies.length > 0
            ? topologies.filter(t => validTopologies.includes(t))
            : validTopologies;

    useEffect(() => {
        if (availableTopologies.length > 0 && !availableTopologies.includes(config.TOPOLOGY_NAME)) {
            setConfig(prev => ({ ...prev, TOPOLOGY_NAME: availableTopologies[0] }));
        }
    }, [availableTopologies, config.TOPOLOGY_NAME]);

    return (
        <Paper
            sx={{
                position: 'absolute',
                top: 16,
                right: 16,
                width: 320,
                maxHeight: 'calc(100vh - 100px)',
                overflow: 'auto',
                zIndex: 1000,
                bgcolor: 'rgba(0, 0, 0, 0.6)',
                backdropFilter: 'blur(10px)',
                border: '1px solid rgba(255, 255, 255, 0.1)'
            }}
            elevation={8}
        >
            <Box sx={{
                p: 2,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                bgcolor: 'rgba(0, 0, 0, 0.6)',
                backdropFilter: 'blur(10px)',
                color: 'white'
            }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Settings />
                    <Typography variant="h6">Configure Simulation</Typography>
                </Box>
                <IconButton size="small" onClick={() => setExpanded(!expanded)} sx={{ color: 'white' }}>
                    {expanded ? <ExpandLess /> : <ExpandMore />}
                </IconButton>
            </Box>

            <Collapse in={expanded}>
                <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <Tabs
                        value={activeTab}
                        onChange={(_, v) => setActiveTab(v)}
                        variant="fullWidth"
                        sx={{
                            minHeight: 28,
                            '& .MuiTab-root': {
                                minHeight: 28,
                                color: 'rgba(255,255,255,0.7)',
                                textTransform: 'none',
                                fontSize: '0.75rem',
                                py: 0.25
                            },
                            '& .MuiTab-root.Mui-selected': { color: '#fff' },
                            '& .MuiTabs-indicator': { backgroundColor: '#fff' }
                        }}
                    >
                        <Tab label="System" value="configuration" icon={<Tune fontSize="small" />} iconPosition="start" />
                        <Tab label="Runtime" value="runtime" icon={<Bolt fontSize="small" />} iconPosition="start" />
                        <Tab label="Agent" value="timing" icon={<AgentTabIcon />} iconPosition="start" />
                    </Tabs>

                    {activeTab === 'configuration' && (
                        <>
                    <FormControl fullWidth size="small" sx={{
                        '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                        '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                        '& .MuiOutlinedInput-root': {
                            color: '#fff',
                            '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                            '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                            '&.Mui-focused fieldset': { borderColor: '#fff' }
                        },
                        '& .MuiSelect-icon': { color: 'rgba(255,255,255,0.7)' }
                    }}>
                        <InputLabel>
                            <Box display="flex" alignItems="center" gap={0.5}>
                                Number of Rooms
                                <Box component="span" title={FIELD_METADATA.N_ROOMS.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                    <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                </Box>
                            </Box>
                        </InputLabel>
                        <Select
                            value={config.N_ROOMS}
                            label="Number of Rooms"
                            onChange={(e) => handleChange('N_ROOMS', parseInt(e.target.value))}
                        >
                            {Object.keys(TOPOLOGY_MAP).map(n => (
                                <MenuItem key={n} value={parseInt(n)}>{n} rooms</MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <FormControl fullWidth size="small" sx={{
                        '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                        '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                        '& .MuiOutlinedInput-root': {
                            color: '#fff',
                            '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                            '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                            '&.Mui-focused fieldset': { borderColor: '#fff' }
                        },
                        '& .MuiSelect-icon': { color: 'rgba(255,255,255,0.7)' }
                    }}>
                        <InputLabel>
                            <Box display="flex" alignItems="center" gap={0.5}>
                                Topology
                                <Box component="span" title={FIELD_METADATA.TOPOLOGY_NAME.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                    <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                </Box>
                            </Box>
                        </InputLabel>
                        <Select
                            value={config.TOPOLOGY_NAME}
                            label="Topology"
                            onChange={(e) => handleChange('TOPOLOGY_NAME', e.target.value)}
                        >
                            {availableTopologies.map(t => (
                                <MenuItem key={t} value={t}>{topologyLabel(t)}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <FormControl fullWidth size="small" sx={{
                        '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                        '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                        '& .MuiOutlinedInput-root': {
                            color: '#fff',
                            '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                            '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                            '&.Mui-focused fieldset': { borderColor: '#fff' }
                        },
                        '& .MuiSelect-icon': { color: 'rgba(255,255,255,0.7)' }
                    }}>
                        <InputLabel>
                            <Box display="flex" alignItems="center" gap={0.5}>
                                Coordination Mechanism
                                <Box component="span" title={FIELD_METADATA.ARCHITECTURE.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                    <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                </Box>
                            </Box>
                        </InputLabel>
                        <Select
                            value={config.ARCHITECTURE}
                            label="Coordination Mechanism"
                            onChange={(e) => handleChange('ARCHITECTURE', e.target.value)}
                        >
                            {ARCHITECTURES.map(a => (
                                <MenuItem
                                    key={a}
                                    value={a}
                                >
                                    {a}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <TextField
                        label="Number of Agents"
                        type="number"
                        size="small"
                        value={config.N_ROBOTS}
                        onChange={(e) => handleChange('N_ROBOTS', parseInt(e.target.value))}
                        InputProps={{
                            endAdornment: (
                                <InputAdornment position="end">
                                    <Box component="span" title={FIELD_METADATA.N_ROBOTS.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                        <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                    </Box>
                                </InputAdornment>
                            )
                        }}
                        sx={{
                            '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                            '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                            '& .MuiOutlinedInput-root': {
                                color: '#fff',
                                '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                '&.Mui-focused fieldset': { borderColor: '#fff' }
                            }
                        }}
                    />

                    <TextField
                        label="Number of Malicious Agent"
                        type="number"
                        size="small"
                        value={config.N_MALICIOUS}
                        onChange={(e) => handleChange('N_MALICIOUS', parseInt(e.target.value))}
                        InputProps={{
                            endAdornment: (
                                <InputAdornment position="end">
                                    <Box component="span" title={FIELD_METADATA.N_MALICIOUS.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                        <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                    </Box>
                                </InputAdornment>
                            )
                        }}
                        sx={{
                            '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                            '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                            '& .MuiOutlinedInput-root': {
                                color: '#fff',
                                '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                '&.Mui-focused fieldset': { borderColor: '#fff' }
                            }
                        }}
                    />

                    <TextField
                        label="Simulation Window (s)"
                        type="number"
                        size="small"
                        value={config.SIM_TIME}
                        onChange={(e) => handleChange('SIM_TIME', parseFloat(e.target.value))}
                        InputProps={{
                            endAdornment: (
                                <InputAdornment position="end">
                                    <Box component="span" title={FIELD_METADATA.SIM_TIME.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                        <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                    </Box>
                                </InputAdornment>
                            )
                        }}
                        sx={{
                            '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                            '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                            '& .MuiOutlinedInput-root': {
                                color: '#fff',
                                '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                '&.Mui-focused fieldset': { borderColor: '#fff' }
                            }
                        }}
                    />

                    <TextField
                        label="Item Spawning Time"
                        type="number"
                        size="small"
                        value={config.ITEM_SPAWNING_TIME}
                        onChange={(e) => handleChange('ITEM_SPAWNING_TIME', parseFloat(e.target.value))}
                        InputProps={{
                            endAdornment: (
                                <InputAdornment position="end">
                                    <Box component="span" title={FIELD_METADATA.ITEM_SPAWNING_TIME.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                        <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                    </Box>
                                </InputAdornment>
                            )
                        }}
                        sx={{
                            '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                            '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                            '& .MuiOutlinedInput-root': {
                                color: '#fff',
                                '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                '&.Mui-focused fieldset': { borderColor: '#fff' }
                            }
                        }}
                    />

                    <FormControl fullWidth size="small" sx={{
                        '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                        '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                        '& .MuiOutlinedInput-root': {
                            color: '#fff',
                            '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                            '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                            '&.Mui-focused fieldset': { borderColor: '#fff' }
                        },
                        '& .MuiSelect-icon': { color: 'rgba(255,255,255,0.7)' }
                    }}>
                        <InputLabel>
                            <Box display="flex" alignItems="center" gap={0.5}>
                                Event Arrival Distribution
                                <Box component="span" title={FIELD_METADATA.ITEM_SPAWNING_DISTR.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                    <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                </Box>
                            </Box>
                        </InputLabel>
                        <Select
                            value={config.ITEM_SPAWNING_DISTR}
                            label="Event Arrival Distribution"
                            onChange={(e) => handleChange('ITEM_SPAWNING_DISTR', e.target.value)}
                        >
                            {DISTRIBUTION_OPTIONS.map((option) => (
                                <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                        </>
                    )}

                    {activeTab === 'runtime' && (
                        <>
                            <Box sx={{ color: 'rgba(255,255,255,0.75)', fontSize: '0.8rem', lineHeight: 1.5 }}>
                                Define optional runtime windows that change adverse-event parameters while the simulation is running.
                            </Box>

                            {config.PHASES.map((phase, index) => (
                                <Paper
                                    key={`phase-${index}`}
                                    elevation={0}
                                    sx={{
                                        p: 1.5,
                                        bgcolor: 'rgba(255,255,255,0.06)',
                                        border: '1px solid rgba(255,255,255,0.12)',
                                        display: 'flex',
                                        flexDirection: 'column',
                                        gap: 1.25
                                    }}
                                >
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                        <Typography sx={{ color: '#fff', fontSize: '0.85rem', fontWeight: 600 }}>
                                            Runtime Window {index + 1}
                                        </Typography>
                                        <IconButton size="small" onClick={() => removePhase(index)} sx={{ color: 'rgba(255,255,255,0.8)' }}>
                                            <DeleteOutline fontSize="small" />
                                        </IconButton>
                                    </Box>

                                    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
                                        <TextField
                                            label="Start (s)"
                                            type="number"
                                            size="small"
                                            value={phase.start}
                                            onChange={(e) => handlePhaseChange(index, 'start', parseFloat(e.target.value))}
                                            sx={{
                                                '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                                                '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                                                '& .MuiOutlinedInput-root': {
                                                    color: '#fff',
                                                    '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                                    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                                    '&.Mui-focused fieldset': { borderColor: '#fff' }
                                                }
                                            }}
                                        />
                                        <TextField
                                            label="End (s)"
                                            type="number"
                                            size="small"
                                            value={phase.end}
                                            onChange={(e) => handlePhaseChange(index, 'end', parseFloat(e.target.value))}
                                            sx={{
                                                '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                                                '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                                                '& .MuiOutlinedInput-root': {
                                                    color: '#fff',
                                                    '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                                    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                                    '&.Mui-focused fieldset': { borderColor: '#fff' }
                                                }
                                            }}
                                        />
                                    </Box>

                                    <TextField
                                        label="Failure Probability"
                                        type="number"
                                        size="small"
                                        inputProps={{ step: 0.01, min: 0, max: 1 }}
                                        value={phase.FAIL_PROB}
                                        onChange={(e) => handlePhaseChange(index, 'FAIL_PROB', parseFloat(e.target.value))}
                                        sx={{
                                            '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                                            '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                                            '& .MuiOutlinedInput-root': {
                                                color: '#fff',
                                                '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                                '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                                '&.Mui-focused fieldset': { borderColor: '#fff' }
                                            }
                                        }}
                                    />

                                    <TextField
                                        label="Communication Failure Probability"
                                        type="number"
                                        size="small"
                                        inputProps={{ step: 0.001, min: 0, max: 1 }}
                                        value={phase.COMM_FAIL_PROB}
                                        onChange={(e) => handlePhaseChange(index, 'COMM_FAIL_PROB', parseFloat(e.target.value))}
                                        sx={{
                                            '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                                            '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                                            '& .MuiOutlinedInput-root': {
                                                color: '#fff',
                                                '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                                '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                                '&.Mui-focused fieldset': { borderColor: '#fff' }
                                            }
                                        }}
                                    />

                                    <TextField
                                        label="Recovery Time"
                                        type="number"
                                        size="small"
                                        value={phase.RECOVERY_TIME}
                                        onChange={(e) => handlePhaseChange(index, 'RECOVERY_TIME', parseFloat(e.target.value))}
                                        sx={{
                                            '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                                            '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                                            '& .MuiOutlinedInput-root': {
                                                color: '#fff',
                                                '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                                '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                                '&.Mui-focused fieldset': { borderColor: '#fff' }
                                            }
                                        }}
                                    />
                                </Paper>
                            ))}

                            <Button
                                variant="outlined"
                                startIcon={<Add />}
                                onClick={addPhase}
                                sx={{
                                    color: '#fff',
                                    borderColor: 'rgba(255,255,255,0.25)',
                                    '&:hover': { borderColor: 'rgba(255,255,255,0.45)' }
                                }}
                            >
                                Add Runtime Window
                            </Button>
                        </>
                    )}

                    {activeTab === 'timing' && (
                        <>
                            <TextField
                                label="Failure Probability"
                                type="number"
                                size="small"
                                inputProps={{ step: 0.01, min: 0, max: 1 }}
                                value={config.FAIL_PROB}
                                onChange={(e) => handleChange('FAIL_PROB', parseFloat(e.target.value))}
                                InputProps={{
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <Box component="span" title={FIELD_METADATA.FAIL_PROB.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                                <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                            </Box>
                                        </InputAdornment>
                                    )
                                }}
                                sx={{
                                    '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                                    '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                                    '& .MuiOutlinedInput-root': {
                                        color: '#fff',
                                        '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                        '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                        '&.Mui-focused fieldset': { borderColor: '#fff' }
                                    }
                                }}
                            />

                            <TextField
                                label="Load Time"
                                type="number"
                                size="small"
                                value={config.LOAD_TIME}
                                onChange={(e) => handleChange('LOAD_TIME', parseFloat(e.target.value))}
                                InputProps={{
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <Box component="span" title={FIELD_METADATA.LOAD_TIME.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                                <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                            </Box>
                                        </InputAdornment>
                                    )
                                }}
                                sx={{
                                    '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                                    '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                                    '& .MuiOutlinedInput-root': {
                                        color: '#fff',
                                        '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                        '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                        '&.Mui-focused fieldset': { borderColor: '#fff' }
                                    }
                                }}
                            />
                            <TextField
                                label="Movement Time"
                                type="number"
                                size="small"
                                value={config.MOVEMENT_TIME}
                                onChange={(e) => handleChange('MOVEMENT_TIME', parseFloat(e.target.value))}
                                InputProps={{
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <Box component="span" title={FIELD_METADATA.MOVEMENT_TIME.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                                <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                            </Box>
                                        </InputAdornment>
                                    )
                                }}
                                sx={{
                                    '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                                    '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                                    '& .MuiOutlinedInput-root': {
                                        color: '#fff',
                                        '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                        '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                        '&.Mui-focused fieldset': { borderColor: '#fff' }
                                    }
                                }}
                            />
                            <TextField
                                label="Drop Time"
                                type="number"
                                size="small"
                                value={config.DROP_TIME}
                                onChange={(e) => handleChange('DROP_TIME', parseFloat(e.target.value))}
                                InputProps={{
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <Box component="span" title={FIELD_METADATA.DROP_TIME.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                                <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                            </Box>
                                        </InputAdornment>
                                    )
                                }}
                                sx={{
                                    '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                                    '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                                    '& .MuiOutlinedInput-root': {
                                        color: '#fff',
                                        '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                        '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                        '&.Mui-focused fieldset': { borderColor: '#fff' }
                                    }
                                }}
                            />
                            <TextField
                                label="Computation Time"
                                type="number"
                                size="small"
                                value={config.COMP_TIME}
                                onChange={(e) => handleChange('COMP_TIME', parseFloat(e.target.value))}
                                InputProps={{
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <Box component="span" title={FIELD_METADATA.COMP_TIME.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                                <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                            </Box>
                                        </InputAdornment>
                                    )
                                }}
                                sx={{
                                    '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                                    '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                                    '& .MuiOutlinedInput-root': {
                                        color: '#fff',
                                        '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                        '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                        '&.Mui-focused fieldset': { borderColor: '#fff' }
                                    }
                                }}
                            />
                            <TextField
                                label="Communication Time"
                                type="number"
                                size="small"
                                value={config.COMM_TIME}
                                onChange={(e) => handleChange('COMM_TIME', parseFloat(e.target.value))}
                                InputProps={{
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <Box component="span" title={FIELD_METADATA.COMM_TIME.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                                <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                            </Box>
                                        </InputAdornment>
                                    )
                                }}
                                sx={{
                                    '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                                    '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                                    '& .MuiOutlinedInput-root': {
                                        color: '#fff',
                                        '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                        '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                        '&.Mui-focused fieldset': { borderColor: '#fff' }
                                    }
                                }}
                            />
                            <TextField
                                label="Recovery Time"
                                type="number"
                                size="small"
                                value={config.RECOVERY_TIME}
                                onChange={(e) => handleChange('RECOVERY_TIME', parseFloat(e.target.value))}
                                InputProps={{
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <Box component="span" title={FIELD_METADATA.RECOVERY_TIME.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                                <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                            </Box>
                                        </InputAdornment>
                                    )
                                }}
                                sx={{
                                    '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                                    '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                                    '& .MuiOutlinedInput-root': {
                                        color: '#fff',
                                        '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                        '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                        '&.Mui-focused fieldset': { borderColor: '#fff' }
                                    }
                                }}
                            />
                        </>
                    )}

                    <Divider sx={{ borderColor: 'rgba(255,255,255,0.2)' }} />

                    <Box sx={{ display: 'flex', alignItems: 'stretch', gap: 1 }}>
                        <TextField
                            label="N° Repetitions"
                            type="number"
                            size="small"
                            value={config.N_REPETITIONS}
                            onChange={(e) => handleChange('N_REPETITIONS', Math.max(1, parseInt(e.target.value || '1', 10)))}
                            inputProps={{ min: 1, step: 1 }}
                            InputProps={{
                                endAdornment: (
                                    <InputAdornment position="end">
                                        <Box component="span" title={FIELD_METADATA.N_REPETITIONS.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                            <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                        </Box>
                                    </InputAdornment>
                                )
                            }}
                            sx={{
                                width: 132,
                                '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
                                '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                                '& .MuiOutlinedInput-root': {
                                    color: '#fff',
                                    '& fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                                    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                    '&.Mui-focused fieldset': { borderColor: '#fff' }
                                }
                            }}
                        />

                        <Button
                            variant="contained"
                            onClick={handleSubmit}
                            disabled={loading}
                            fullWidth
                            size="large"
                        >
                            {loading ? 'Running...' : (hasSimulation ? 'Run New Simulation' : 'Run Simulation')}
                        </Button>
                    </Box>
                </Box>
            </Collapse>

            {/* RTLola Editor Modal */}
            <RTLolaEditor
                open={rtlolaEditorOpen}
                onClose={handleRtlolaClose}
                onSave={handleRtlolaSave}
            />
        </Paper>
    );
}

export default ConfigForm;
