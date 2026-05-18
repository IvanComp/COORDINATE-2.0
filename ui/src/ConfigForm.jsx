import React, { useState, useEffect, useMemo } from 'react';
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
    Tab,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Alert
} from '@mui/material';
import { Settings, ExpandMore, ExpandLess, HelpOutline, Add, DeleteOutline, Inventory2, AccountTree, Bolt } from '@mui/icons-material';
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
    INITIAL_ARCHITECTURE: "semi-decentralized",
    ADAPTATION_CHECK_INTERVAL: 300.0,
    LATENCY_THRESHOLD_LOW: 10.0,
    LATENCY_THRESHOLD_HIGH: 40.0,
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
    INITIAL_ARCHITECTURE: { label: "Initial Architecture", description: "Coordination mechanism used at the beginning of a dynamic-adaptation run." },
    ADAPTATION_CHECK_INTERVAL: { label: "Adaptation Check Interval", description: "Simulation-time interval, in seconds, between two dynamic-adaptation checks." },
    LATENCY_THRESHOLD_LOW: { label: "Low Latency Threshold", description: "Below this latency, dynamic adaptation prefers centralized-impprox." },
    LATENCY_THRESHOLD_HIGH: { label: "High Latency Threshold", description: "Above this latency, dynamic adaptation prefers decentralized coordination." },
    N_ROBOTS: { label: "Number of Agents", description: "Total number of agents in the fleet." },
    N_MALICIOUS: { label: "Number of Malicious Agent", description: "Number of agents that may fail or act maliciously." },
    SIM_TIME: { label: "Simulation Window (s)", description: "Duration of the simulation in seconds." },
    N_REPETITIONS: { label: "N° Repetitions", description: "Number of independent simulation runs used to compute the final average CSV." },
    FAIL_PROB: { label: "Failure Probability", description: "Probability of an agent failing during operation (0-1)." },
    ITEM_SPAWNING_TIME: { label: "Item Spawning Time", description: "Average time (in seconds) between new item requests." },
    IMPORTANCE_PROBABILITIES: { label: "Item Importance Probabilities", description: "Spawn probability, as a percentage, for Low, Medium, and High priority items." },
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

const ITEM_IMPORTANCE_LEVELS = [
    { label: 'Low', color: '#4CAF50' },
    { label: 'Medium', color: '#FFC107' },
    { label: 'High', color: '#FF5722' },
];

const CUSTOM_ROOM_VALUE = 'custom';
const DEFAULT_CUSTOM_ROOM_TEXT = '0-1, 1-2, 2-3, 3-0';
const DEFAULT_CUSTOM_COORDS_TEXT = '0:0,0\n1:8,0\n2:8,8\n3:0,8';

// Map N_ROOMS to appropriate topology
const TOPOLOGY_MAP = {
    4: ['mesh4', 'ring4', 'tree4', 'line4', 'star4', 'fully_connected4', 'bus4'],
    9: ['mesh9', 'ring9', 'tree9', 'line9', 'star9', 'fully_connected9', 'bus9'],
    16: ['mesh16', 'ring16', 'tree16', 'line16', 'star16', 'fully_connected16', 'bus16'],
    25: ['mesh25', 'ring25', 'tree25', 'line25', 'star25', 'fully_connected25', 'bus25'],
    36: ['mesh36', 'ring36', 'tree36', 'line36', 'star36', 'fully_connected36', 'bus36'],
    49: ['mesh49', 'ring49', 'tree49', 'line49', 'star49', 'fully_connected49', 'bus49'],
    73: ['GUH73']
};

function AgentTabIcon() {
    return (
        <svg width="16" height="16" viewBox="0 0 16 16" style={{ display: 'block' }} aria-hidden="true">
            <rect x="5" y="6" width="6" height="7" fill="currentColor" rx="1" />
            <circle cx="8" cy="4" r="2.5" fill="currentColor" />
            <circle cx="7" cy="4" r="0.5" fill="rgba(0,0,0,0.75)" />
            <circle cx="9" cy="4" r="0.5" fill="rgba(0,0,0,0.75)" />
        </svg>
    );
}

function topologyLabel(topologyName) {
    if (topologyName === CUSTOM_ROOM_VALUE) return 'custom';
    if (topologyName.startsWith('mesh')) return 'mesh';
    if (topologyName.startsWith('ring')) return 'ring';
    if (topologyName.startsWith('tree')) return 'tree';
    if (topologyName.startsWith('line')) return 'line';
    if (topologyName.startsWith('star')) return 'star';
    if (topologyName.startsWith('fully_connected')) return 'fully connected';
    if (topologyName.startsWith('bus')) return 'bus';
    return topologyName;
}

function parseCustomEdges(rawEdges, roomCount) {
    const edges = rawEdges
        .split(/[\n,;]+/)
        .map(part => part.trim())
        .filter(Boolean)
        .map(part => {
            const match = part.match(/^(\d+)\s*(?:-|->|:)\s*(\d+)$/);
            if (!match) {
                throw new Error(`Invalid corridor "${part}". Use pairs like 0-1.`);
            }
            const source = Number(match[1]);
            const target = Number(match[2]);
            if (source === target) {
                throw new Error(`Room ${source} cannot connect to itself.`);
            }
            if (source < 0 || target < 0 || source >= roomCount || target >= roomCount) {
                throw new Error(`Corridor ${source}-${target} is outside the 0-${roomCount - 1} range.`);
            }
            return { source, target };
        });

    const seen = new Set();
    return edges.filter(edge => {
        const key = [edge.source, edge.target].sort((a, b) => a - b).join('-');
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
    });
}

function parseCustomCoordinates(rawCoordinates, roomCount) {
    const coordinates = new Map();
    rawCoordinates
        .split(/\n+/)
        .map(line => line.trim())
        .filter(Boolean)
        .forEach(line => {
            const match = line.match(/^(\d+)\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$/);
            if (!match) {
                throw new Error(`Invalid coordinate "${line}". Use id:x,z, for example 0:0,0.`);
            }
            const id = Number(match[1]);
            if (id < 0 || id >= roomCount) {
                throw new Error(`Coordinate room ${id} is outside the 0-${roomCount - 1} range.`);
            }
            coordinates.set(id, { x: Number(match[2]), z: Number(match[3]) });
        });
    return coordinates;
}

function assertConnected(roomCount, edges) {
    if (roomCount <= 1) return;
    const adjacency = Array.from({ length: roomCount }, () => []);
    edges.forEach(({ source, target }) => {
        adjacency[source].push(target);
        adjacency[target].push(source);
    });

    const visited = new Set([0]);
    const queue = [0];
    while (queue.length > 0) {
        const room = queue.shift();
        adjacency[room].forEach(next => {
            if (!visited.has(next)) {
                visited.add(next);
                queue.push(next);
            }
        });
    }

    if (visited.size !== roomCount) {
        throw new Error(`The custom room graph must be connected. ${roomCount - visited.size} room(s) are isolated.`);
    }
}

function ConfigForm({ onRun, loading, hasSimulation = false }) {
    const [config, setConfig] = useState(DEFAULTS);
    const [topologies, setTopologies] = useState([]);
    const [expanded, setExpanded] = useState(true);
    const [rtlolaEditorOpen, setRtlolaEditorOpen] = useState(false);
    const [activeTab, setActiveTab] = useState('task');
    const [customBuilderOpen, setCustomBuilderOpen] = useState(false);
    const [customRoomCount, setCustomRoomCount] = useState(4);
    const [customEdgesText, setCustomEdgesText] = useState(DEFAULT_CUSTOM_ROOM_TEXT);
    const [customCoordinatesText, setCustomCoordinatesText] = useState(DEFAULT_CUSTOM_COORDS_TEXT);
    const [customBuilderError, setCustomBuilderError] = useState('');
    const [customLayoutPreset, setCustomLayoutPreset] = useState('');

    useEffect(() => {
        axios.get(`${API_BASE}/topologies`)
            .then(res => setTopologies(res.data))
            .catch(err => console.error(err));
    }, []);

    useEffect(() => {
        setExpanded(!hasSimulation);
    }, [hasSimulation]);

    const handleChange = (field, value) => {
        if (field === 'N_ROOMS' && value === CUSTOM_ROOM_VALUE) {
            setCustomBuilderOpen(true);
            return;
        }

        const newConfig = { ...config, [field]: value };

        // Auto-update topology when N_ROOMS changes
        if (field === 'N_ROOMS') {
            const validTopologies = TOPOLOGY_MAP[value];
            if (validTopologies && validTopologies.length > 0) {
                // Pick the first mesh topology if available
                const meshTopo = validTopologies.find(t => t.startsWith('mesh'));
                newConfig.TOPOLOGY_NAME = meshTopo || validTopologies[0];
                delete newConfig.CUSTOM_TOPOLOGY;
                delete newConfig.CUSTOM_TOPOLOGY_NAME;
            }
        }

        setConfig(newConfig);
    };

    const saveCustomTopology = () => {
        try {
            const roomCount = Number(customRoomCount);
            if (!Number.isInteger(roomCount) || roomCount < 2) {
                throw new Error('Use at least 2 rooms for a custom topology.');
            }

            const edges = parseCustomEdges(customEdgesText, roomCount);
            if (edges.length === 0) {
                throw new Error('Add at least one corridor.');
            }
            assertConnected(roomCount, edges);

            const coordinates = customLayoutPreset ? new Map() : parseCustomCoordinates(customCoordinatesText, roomCount);
            const nodes = Array.from({ length: roomCount }, (_, id) => {
                const coordinate = coordinates.get(id);
                return coordinate
                    ? { id, label: `Room ${id}`, x: coordinate.x, z: coordinate.z }
                    : { id, label: `Room ${id}` };
            });

            setConfig(prev => ({
                ...prev,
                N_ROOMS: roomCount,
                TOPOLOGY_NAME: CUSTOM_ROOM_VALUE,
                CUSTOM_TOPOLOGY_NAME: customLayoutPreset === 'GUH73' ? 'Custom Ghent' : `Custom ${roomCount}`,
                CUSTOM_TOPOLOGY: {
                    nodes,
                    edges,
                    layoutPreset: customLayoutPreset || undefined,
                },
            }));
            setCustomBuilderOpen(false);
            setCustomBuilderError('');
        } catch (err) {
            setCustomBuilderError(err.message);
        }
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

    const sanitizeImportanceProbabilities = (probabilities) => {
        const values = (probabilities || DEFAULTS.IMPORTANCE_PROBABILITIES)
            .slice(0, 3)
            .map(value => {
                const numeric = Number(value);
                return Number.isFinite(numeric) && numeric > 0 ? numeric : 0;
            });
        while (values.length < 3) values.push(0);

        const total = values.reduce((sum, value) => sum + value, 0);
        if (total <= 0) {
            return DEFAULTS.IMPORTANCE_PROBABILITIES;
        }

        return values.map(value => value / total);
    };

    const handleImportanceProbabilityChange = (index, percentValue) => {
        const percent = Number(percentValue);
        const probability = Number.isFinite(percent) ? Math.max(0, percent) / 100 : 0;
        setConfig(prev => {
            const next = [...(prev.IMPORTANCE_PROBABILITIES || DEFAULTS.IMPORTANCE_PROBABILITIES)];
            while (next.length < 3) next.push(0);
            next[index] = probability;
            return { ...prev, IMPORTANCE_PROBABILITIES: next };
        });
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
            IMPORTANCE_PROBABILITIES: sanitizeImportanceProbabilities(config.IMPORTANCE_PROBABILITIES),
        };
        if (configToRun.TOPOLOGY_NAME === CUSTOM_ROOM_VALUE && !configToRun.CUSTOM_TOPOLOGY) {
            setCustomBuilderOpen(true);
            setCustomBuilderError('Create the custom topology before running the simulation.');
            return;
        }
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
            IMPORTANCE_PROBABILITIES: sanitizeImportanceProbabilities(config.IMPORTANCE_PROBABILITIES),
            RTLOLA_SPEC_FILE: specFile
        };
        onRun(configWithSpec);
    };

    const handleRtlolaClose = () => {
        setRtlolaEditorOpen(false);
    };

    // Get valid topologies for current N_ROOMS
    const validTopologies = useMemo(() => TOPOLOGY_MAP[config.N_ROOMS] || [], [config.N_ROOMS]);
    const availableTopologies = useMemo(() => (
        config.TOPOLOGY_NAME === CUSTOM_ROOM_VALUE
            ? [CUSTOM_ROOM_VALUE]
            : topologies.length > 0
            ? topologies.filter(t => validTopologies.includes(t))
            : validTopologies
    ), [config.TOPOLOGY_NAME, topologies, validTopologies]);

    useEffect(() => {
        if (config.TOPOLOGY_NAME !== CUSTOM_ROOM_VALUE && availableTopologies.length > 0 && !availableTopologies.includes(config.TOPOLOGY_NAME)) {
            setConfig(prev => ({ ...prev, TOPOLOGY_NAME: availableTopologies[0] }));
        }
    }, [availableTopologies, config.TOPOLOGY_NAME]);

    const importancePercentages = (config.IMPORTANCE_PROBABILITIES || DEFAULTS.IMPORTANCE_PROBABILITIES)
        .slice(0, 3)
        .map(value => Number(((Number(value) || 0) * 100).toFixed(2)));
    while (importancePercentages.length < 3) importancePercentages.push(0);
    const importanceTotal = importancePercentages.reduce((sum, value) => sum + value, 0);

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
                                fontSize: '0.72rem',
                                minWidth: 0,
                                px: 0.35,
                                py: 0.25
                            },
                            '& .MuiTab-root.Mui-selected': { color: '#fff' },
                            '& .MuiTabs-indicator': { backgroundColor: '#fff' }
                        }}
                    >
                        <Tab label="Task" value="task" icon={<Inventory2 fontSize="small" />} iconPosition="start" />
                        <Tab label="Topology" value="topology" icon={<AccountTree fontSize="small" />} iconPosition="start" />
                        <Tab label="Agent" value="agent" icon={<AgentTabIcon />} iconPosition="start" />
                        <Tab label="Runtime" value="runtime" icon={<Bolt fontSize="small" />} iconPosition="start" />
                    </Tabs>

                    {activeTab === 'topology' && (
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
                            value={config.TOPOLOGY_NAME === CUSTOM_ROOM_VALUE ? CUSTOM_ROOM_VALUE : config.N_ROOMS}
                            label="Number of Rooms"
                            onChange={(e) => {
                                const value = e.target.value;
                                handleChange('N_ROOMS', value === CUSTOM_ROOM_VALUE ? value : parseInt(value, 10));
                            }}
                        >
                            {Object.keys(TOPOLOGY_MAP).map(n => (
                                <MenuItem key={n} value={parseInt(n)}>{n} rooms</MenuItem>
                            ))}
                            <MenuItem value={CUSTOM_ROOM_VALUE}>
                                Custom...
                            </MenuItem>
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
                                <MenuItem key={t} value={t}>
                                    {t === CUSTOM_ROOM_VALUE
                                        ? (config.CUSTOM_TOPOLOGY_NAME || `Custom (${config.N_ROOMS} rooms)`)
                                        : topologyLabel(t)}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    {config.TOPOLOGY_NAME === CUSTOM_ROOM_VALUE && (
                        <Button
                            variant="outlined"
                            size="small"
                            onClick={() => setCustomBuilderOpen(true)}
                            sx={{
                                color: '#fff',
                                borderColor: 'rgba(255,255,255,0.25)',
                                '&:hover': { borderColor: 'rgba(255,255,255,0.45)' }
                            }}
                        >
                            Edit Custom Rooms
                        </Button>
                    )}
                        </>
                    )}

                    {activeTab === 'runtime' && (
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

                    {config.ARCHITECTURE === 'dynamic-adaptation' && (
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
                                        Initial Architecture
                                        <Box component="span" title={FIELD_METADATA.INITIAL_ARCHITECTURE.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                            <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                        </Box>
                                    </Box>
                                </InputLabel>
                                <Select
                                    value={config.INITIAL_ARCHITECTURE}
                                    label="Initial Architecture"
                                    onChange={(e) => handleChange('INITIAL_ARCHITECTURE', e.target.value)}
                                >
                                    {ARCHITECTURES.filter(a => a !== 'dynamic-adaptation').map(a => (
                                        <MenuItem key={a} value={a}>{a}</MenuItem>
                                    ))}
                                </Select>
                            </FormControl>

                            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 1 }}>
                                <TextField
                                    label="Adapt Check (s)"
                                    type="number"
                                    size="small"
                                    value={config.ADAPTATION_CHECK_INTERVAL}
                                    onChange={(e) => handleChange('ADAPTATION_CHECK_INTERVAL', parseFloat(e.target.value))}
                                    InputProps={{
                                        endAdornment: (
                                            <InputAdornment position="end">
                                                <Box component="span" title={FIELD_METADATA.ADAPTATION_CHECK_INTERVAL.description} sx={{ display: 'flex', alignItems: 'center' }}>
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
                                    label="Low Latency"
                                    type="number"
                                    size="small"
                                    value={config.LATENCY_THRESHOLD_LOW}
                                    onChange={(e) => handleChange('LATENCY_THRESHOLD_LOW', parseFloat(e.target.value))}
                                    InputProps={{
                                        endAdornment: (
                                            <InputAdornment position="end">
                                                <Box component="span" title={FIELD_METADATA.LATENCY_THRESHOLD_LOW.description} sx={{ display: 'flex', alignItems: 'center' }}>
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
                                    label="High Latency"
                                    type="number"
                                    size="small"
                                    value={config.LATENCY_THRESHOLD_HIGH}
                                    onChange={(e) => handleChange('LATENCY_THRESHOLD_HIGH', parseFloat(e.target.value))}
                                    InputProps={{
                                        endAdornment: (
                                            <InputAdornment position="end">
                                                <Box component="span" title={FIELD_METADATA.LATENCY_THRESHOLD_HIGH.description} sx={{ display: 'flex', alignItems: 'center' }}>
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
                            </Box>
                        </>
                    )}
                        </>
                    )}

                    {activeTab === 'agent' && (
                        <>

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
                        </>
                    )}

                    {activeTab === 'runtime' && (
                        <>

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
                        </>
                    )}

                    {activeTab === 'task' && (
                        <>

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

                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'rgba(255,255,255,0.75)', fontSize: '0.78rem' }}>
                                Item importance %
                                <Box component="span" title={FIELD_METADATA.IMPORTANCE_PROBABILITIES.description} sx={{ display: 'flex', alignItems: 'center' }}>
                                    <HelpOutline sx={{ fontSize: 16, color: 'rgba(255,255,255,0.5)', cursor: 'help' }} />
                                </Box>
                            </Box>
                            <Typography
                                variant="caption"
                                sx={{
                                    color: Math.abs(importanceTotal - 100) < 0.01 ? 'rgba(255,255,255,0.7)' : '#FFC107',
                                    fontSize: '0.72rem'
                                }}
                            >
                                Total: {importanceTotal.toFixed(2)}%
                            </Typography>
                        </Box>

                        <Box sx={{ display: 'grid', gap: 0.75 }}>
                            {ITEM_IMPORTANCE_LEVELS.map((level, index) => (
                                <Box
                                    key={level.label}
                                    sx={{
                                        display: 'grid',
                                        gridTemplateColumns: 'minmax(0, 1fr) 128px',
                                        alignItems: 'center',
                                        gap: 1,
                                        p: 0.75,
                                        border: '1px solid rgba(255,255,255,0.12)',
                                        borderRadius: 1.5,
                                        background: 'rgba(255,255,255,0.04)'
                                    }}
                                >
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
                                        <Box sx={{ width: 9, height: 9, borderRadius: '50%', bgcolor: level.color, flex: '0 0 auto' }} />
                                        <Typography variant="body2" sx={{ color: '#fff', fontSize: '0.82rem', fontWeight: 600 }}>
                                            {level.label}
                                        </Typography>
                                    </Box>
                                    <TextField
                                        type="number"
                                        size="small"
                                        value={importancePercentages[index]}
                                        onChange={(e) => handleImportanceProbabilityChange(index, e.target.value)}
                                        InputProps={{
                                            endAdornment: <InputAdornment position="end">%</InputAdornment>
                                        }}
                                        inputProps={{ min: 0, step: 1, 'aria-label': `${level.label} importance percentage` }}
                                        sx={{
                                            '& .MuiOutlinedInput-input': {
                                                py: 0.75,
                                                textAlign: 'right',
                                                fontSize: '0.92rem',
                                                fontWeight: 700
                                            },
                                            '& .MuiOutlinedInput-root': {
                                                color: '#fff',
                                                '& fieldset': { borderColor: 'rgba(255,255,255,0.28)' },
                                                '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.5)' },
                                                '&.Mui-focused fieldset': { borderColor: '#fff' }
                                            },
                                            '& .MuiInputAdornment-root': { color: 'rgba(255,255,255,0.65)' }
                                        }}
                                    />
                                </Box>
                            ))}
                        </Box>
                    </Box>

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

                    {activeTab === 'agent' && (
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
                        {activeTab === 'runtime' && (
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
                        )}

                        <Button
                            variant="contained"
                            onClick={handleSubmit}
                            disabled={loading}
                            fullWidth
                            size="large"
                        >
                            {loading ? 'Running...' : 'Run Simulation'}
                        </Button>
                    </Box>
                </Box>
            </Collapse>

            <Dialog
                open={customBuilderOpen}
                onClose={() => setCustomBuilderOpen(false)}
                fullWidth
                maxWidth="md"
            >
                <DialogTitle>Create Custom Room Topology</DialogTitle>
                <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                        Define rooms as a connected graph. Corridors use room pairs such as 0-1, 1-2. Optional coordinates control the visual shape.
                    </Typography>

                    {customBuilderError && (
                        <Alert severity="error">{customBuilderError}</Alert>
                    )}

                    <TextField
                        label="Rooms"
                        type="number"
                        size="small"
                        value={customRoomCount}
                        onChange={(e) => {
                            setCustomRoomCount(parseInt(e.target.value || '0', 10));
                            setCustomLayoutPreset('');
                        }}
                        inputProps={{ min: 2, step: 1 }}
                    />

                    <TextField
                        label="Corridors"
                        value={customEdgesText}
                        onChange={(e) => {
                            setCustomEdgesText(e.target.value);
                            setCustomLayoutPreset('');
                        }}
                        multiline
                        minRows={4}
                        helperText="Accepted separators: comma, semicolon, or new line. Example: 0-1, 1-2, 2-3."
                    />

                    <TextField
                        label="Visual coordinates (optional)"
                        value={customCoordinatesText}
                        onChange={(e) => {
                            setCustomCoordinatesText(e.target.value);
                            setCustomLayoutPreset('');
                        }}
                        multiline
                        minRows={4}
                        disabled={customLayoutPreset === 'GUH73'}
                        helperText={customLayoutPreset === 'GUH73'
                            ? 'The Ghent template uses the existing GUH73 visual layout.'
                            : 'One room per line as id:x,z. Rooms without coordinates fall back to automatic placement.'}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setCustomBuilderOpen(false)}>Cancel</Button>
                    <Button variant="contained" onClick={saveCustomTopology}>Use Custom Rooms</Button>
                </DialogActions>
            </Dialog>

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
