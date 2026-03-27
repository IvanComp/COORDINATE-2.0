import React, { useEffect, useState } from 'react';
import {
    Box,
    Button,
    Collapse,
    FormControl,
    InputLabel,
    MenuItem,
    Paper,
    Select,
    Stack,
    TextField,
    Typography,
} from '@mui/material';
import { Settings } from '@mui/icons-material';
import axios from 'axios';

const API_BASE = '/api';

const DEFAULTS = {
    RESULTS_DIR: 'results',
    SIM_TIME: 180,
    TOPOLOGY_NAME: 'mesh9',
    N_ROOMS: 9,
    N_ANTS: 12,
    INITIAL_MALES: 4,
    COLONY_STRATEGY: 'balanced',
    RESOURCE_SPAWNING_TIME: 20,
    MEAL_RESTORE: 38,
    DRINK_RESTORE: 42,
    MICRO_NAPS_PER_DAY: 120,
    MICRO_NAP_DURATION: 1,
    MATING_PROBABILITY: 0.05,
    BROOD_MIN: 1,
    BROOD_MAX: 2,
    N_REPETITIONS: 1,
    FAIL_PROB: 0.0005,
    MOVEMENT_TIME: 1,
};

const STRATEGIES = [
    'balanced',
    'brood-focus',
    'forager',
    'hydration-first',
    'rest-guarded',
    'expansion',
    'adaptive-colony',
];

const TOPOLOGY_MAP = {
    4: ['mesh4', 'ring4', 'tree4'],
    9: ['mesh9', 'ring9', 'tree9'],
    16: ['mesh16', 'ring16', 'tree16'],
    25: ['mesh25', 'ring25', 'tree25'],
    36: ['mesh36', 'ring36', 'tree36'],
    49: ['mesh49', 'ring49', 'tree49'],
};

function ConfigForm({ onRun, loading, hasSimulation }) {
    const [config, setConfig] = useState(DEFAULTS);
    const [expanded, setExpanded] = useState(true);
    const [topologies, setTopologies] = useState([]);

    useEffect(() => {
        axios.get(`${API_BASE}/topologies`)
            .then((res) => setTopologies(res.data))
            .catch((err) => console.error(err));
    }, []);

    useEffect(() => {
        setExpanded(!hasSimulation);
    }, [hasSimulation]);

    const validTopologies = topologies.filter((topology) => (TOPOLOGY_MAP[config.N_ROOMS] || []).includes(topology));

    const handleChange = (field, value) => {
        const next = { ...config, [field]: value };
        if (field === 'N_ROOMS') {
            next.TOPOLOGY_NAME = TOPOLOGY_MAP[value]?.[0] || next.TOPOLOGY_NAME;
        }
        setConfig(next);
    };

    const numericFields = [
        ['SIM_TIME', 'Simulation length (min)'],
        ['N_ANTS', 'Starting ants'],
        ['INITIAL_MALES', 'Starting males'],
        ['RESOURCE_SPAWNING_TIME', 'Resource pulse (min)'],
        ['MICRO_NAPS_PER_DAY', 'Micro-naps per day'],
        ['MICRO_NAP_DURATION', 'Nap duration (min)'],
        ['MATING_PROBABILITY', 'Mating probability'],
        ['BROOD_MIN', 'Minimum brood'],
        ['BROOD_MAX', 'Maximum brood'],
        ['MEAL_RESTORE', 'Food recovery'],
        ['DRINK_RESTORE', 'Water recovery'],
        ['FAIL_PROB', 'Environmental stress'],
        ['N_REPETITIONS', 'Repetitions'],
    ];

    return (
        <Paper
            sx={{
                position: 'absolute',
                top: 16,
                left: 16,
                width: 'min(360px, calc(100vw - 32px))',
                maxHeight: 'calc(100vh - 32px)',
                zIndex: 7,
                bgcolor: 'rgba(0,0,0,0.62)',
                backdropFilter: 'blur(12px)',
                border: '1px solid rgba(255,255,255,0.12)',
                color: 'white',
                overflow: 'hidden',
            }}
        >
            <Box
                sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
                onClick={() => setExpanded((value) => !value)}
            >
                <Stack direction="row" spacing={1} alignItems="center">
                    <Settings fontSize="small" />
                    <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                        Anthill Control
                    </Typography>
                </Stack>
                <Typography variant="caption">{expanded ? '▲' : '▼'}</Typography>
            </Box>

            <Collapse in={expanded} sx={{ overflow: 'auto', maxHeight: 'calc(100vh - 96px)' }}>
                <Stack spacing={1.5} sx={{ px: 2, pb: 2 }}>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.72)' }}>
                        Configure geography, population, and the colony's vital rhythm to observe how the anthill evolves.
                    </Typography>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.58)' }}>
                        The starting values are tuned for a simple run: a small colony, a short duration, and a compact topology.
                    </Typography>

                    <FormControl fullWidth size="small">
                        <InputLabel sx={{ color: 'rgba(255,255,255,0.75)' }}>Colony strategy</InputLabel>
                        <Select
                            value={config.COLONY_STRATEGY}
                            label="Colony strategy"
                            onChange={(e) => handleChange('COLONY_STRATEGY', e.target.value)}
                            sx={{ color: 'white' }}
                        >
                            {STRATEGIES.map((strategy) => (
                                <MenuItem key={strategy} value={strategy}>{strategy}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <Stack direction="row" spacing={1}>
                        <TextField
                            fullWidth
                            size="small"
                            type="number"
                            label="Rooms"
                            value={config.N_ROOMS}
                            onChange={(e) => handleChange('N_ROOMS', Number(e.target.value))}
                            slotProps={{ inputLabel: { sx: { color: 'rgba(255,255,255,0.75)' } }, input: { sx: { color: 'white' } } }}
                        />
                        <FormControl fullWidth size="small">
                            <InputLabel sx={{ color: 'rgba(255,255,255,0.75)' }}>Topology</InputLabel>
                            <Select
                                value={config.TOPOLOGY_NAME}
                                label="Topology"
                                onChange={(e) => handleChange('TOPOLOGY_NAME', e.target.value)}
                                sx={{ color: 'white' }}
                            >
                                {(validTopologies.length ? validTopologies : TOPOLOGY_MAP[config.N_ROOMS] || []).map((topology) => (
                                    <MenuItem key={topology} value={topology}>{topology}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Stack>

                    {numericFields.map(([field, label]) => (
                        <TextField
                            key={field}
                            fullWidth
                            size="small"
                            type="number"
                            label={label}
                            value={config[field]}
                            onChange={(e) => handleChange(field, Number(e.target.value))}
                            slotProps={{ inputLabel: { sx: { color: 'rgba(255,255,255,0.75)' } }, input: { sx: { color: 'white' } } }}
                        />
                    ))}

                    <Button variant="contained" onClick={() => onRun(config)} disabled={loading} sx={{ position: 'sticky', bottom: 0 }}>
                        {loading ? 'Simulation running...' : 'Start simulation'}
                    </Button>
                </Stack>
            </Collapse>
        </Paper>
    );
}

export default ConfigForm;
