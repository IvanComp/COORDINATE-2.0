import React, { useMemo } from 'react';
import {
    Box,
    Dialog,
    DialogContent,
    DialogTitle,
    IconButton,
    Paper,
    Stack,
    Typography,
} from '@mui/material';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import {
    Area,
    AreaChart,
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    Legend,
    Line,
    LineChart,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';

const PIE_COLORS = ['#9ac46e', '#a7b4cf', '#f08b7f'];

function binEvents(logs) {
    if (!logs.length) return [];
    const maxTime = Math.max(...logs.map((log) => Number(log.simTime) || 0), 1);
    const bins = 12;
    const width = Math.max(maxTime / bins, 1);
    const rows = Array.from({ length: bins }).map((_, index) => ({
        time: Math.round(index * width),
        births: 0,
        deaths: 0,
        matings: 0,
        meals: 0,
        drinks: 0,
        naps: 0,
    }));
    logs.forEach((log) => {
        const idx = Math.min(bins - 1, Math.floor((Number(log.simTime) || 0) / width));
        if (log.event === 'birth') rows[idx].births += 1;
        if (log.event === 'death') rows[idx].deaths += 1;
        if (log.event === 'mate') rows[idx].matings += 1;
        if (log.event === 'eat') rows[idx].meals += 1;
        if (log.event === 'drink') rows[idx].drinks += 1;
        if (log.event === 'nap_start') rows[idx].naps += 1;
    });
    return rows;
}

function populationTrend(logs) {
    let living = 0;
    return logs
        .slice()
        .sort((a, b) => Number(a.simTime) - Number(b.simTime))
        .map((log) => {
            if (log.event === 'birth') living += 1;
            if (log.event === 'death') living = Math.max(0, living - 1);
            return {
                time: Number(log.simTime) || 0,
                living,
            };
        })
        .filter((_, index, arr) => index === 0 || arr[index].time !== arr[index - 1].time || index === arr.length - 1);
}

function actionTotals(logs) {
    const totals = {
        Births: 0,
        Deaths: 0,
        Matings: 0,
        Meals: 0,
        Drinks: 0,
        Naps: 0,
        Moves: 0,
    };
    logs.forEach((log) => {
        if (log.event === 'birth') totals.Births += 1;
        if (log.event === 'death') totals.Deaths += 1;
        if (log.event === 'mate') totals.Matings += 1;
        if (log.event === 'eat') totals.Meals += 1;
        if (log.event === 'drink') totals.Drinks += 1;
        if (log.event === 'nap_start') totals.Naps += 1;
        if (log.event === 'move') totals.Moves += 1;
    });
    return Object.entries(totals).map(([name, value]) => ({ name, value }));
}

function ChartCard({ title, children }) {
    return (
        <Paper sx={{ p: 1.5, bgcolor: '#fff', borderRadius: 2, border: '1px solid #e5e7eb', minWidth: 0 }}>
            <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
                {title}
            </Typography>
            <Box sx={{ height: 260 }}>
                {children}
            </Box>
        </Paper>
    );
}

function AnalyticsModal({ open, onClose, logs = [], summary = null, title = 'Analytics Dashboard', subtitle = '' }) {
    const normalizedLogs = useMemo(
        () =>
            (logs || []).map((log) => ({
                ...log,
                simTime: Number(log.simTime) || 0,
            })),
        [logs]
    );

    const timeline = useMemo(() => binEvents(normalizedLogs), [normalizedLogs]);
    const population = useMemo(() => populationTrend(normalizedLogs), [normalizedLogs]);
    const totals = useMemo(() => actionTotals(normalizedLogs), [normalizedLogs]);
    const stateBreakdown = useMemo(() => {
        const living = summary?.living || 0;
        const sleeping = summary?.sleeping || 0;
        return [
            { name: 'Active', value: Math.max(0, living - sleeping) },
            { name: 'Sleeping', value: sleeping },
            { name: 'Dead', value: summary?.deaths || 0 },
        ];
    }, [summary]);

    return (
        <Dialog open={open} onClose={onClose} maxWidth="xl" fullWidth>
            <DialogTitle sx={{ pr: 7 }}>
                <Typography variant="h6" sx={{ fontWeight: 800 }}>
                    {title}
                </Typography>
                {subtitle && (
                    <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.4 }}>
                        {subtitle}
                    </Typography>
                )}
                <IconButton onClick={onClose} sx={{ position: 'absolute', right: 12, top: 12 }}>
                    <CloseRoundedIcon />
                </IconButton>
            </DialogTitle>
            <DialogContent dividers sx={{ bgcolor: '#f7f8fb' }}>
                <Stack spacing={2}>
                    <Box
                        sx={{
                            display: 'grid',
                            gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, minmax(0, 1fr))' },
                            gap: 2,
                        }}
                    >
                        <ChartCard title="Population Trend">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={population}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                    <XAxis dataKey="time" stroke="#64748b" />
                                    <YAxis stroke="#64748b" />
                                    <Tooltip />
                                    <Area type="monotone" dataKey="living" stroke="#9ac46e" fill="#d8f0c8" strokeWidth={2} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </ChartCard>

                        <ChartCard title="Event Timeline">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={timeline}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                    <XAxis dataKey="time" stroke="#64748b" />
                                    <YAxis stroke="#64748b" />
                                    <Tooltip />
                                    <Legend />
                                    <Line type="monotone" dataKey="births" stroke="#d8a95f" strokeWidth={2} dot={false} />
                                    <Line type="monotone" dataKey="deaths" stroke="#f08b7f" strokeWidth={2} dot={false} />
                                    <Line type="monotone" dataKey="matings" stroke="#cf95e8" strokeWidth={2} dot={false} />
                                    <Line type="monotone" dataKey="naps" stroke="#a7b4cf" strokeWidth={2} dot={false} />
                                </LineChart>
                            </ResponsiveContainer>
                        </ChartCard>

                        <ChartCard title="Action Totals">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={totals}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                    <XAxis dataKey="name" stroke="#64748b" angle={-18} textAnchor="end" height={56} />
                                    <YAxis stroke="#64748b" />
                                    <Tooltip />
                                    <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                                        {totals.map((entry) => (
                                            <Cell
                                                key={entry.name}
                                                fill={
                                                    entry.name === 'Births'
                                                        ? '#d8a95f'
                                                        : entry.name === 'Deaths'
                                                            ? '#f08b7f'
                                                            : entry.name === 'Matings'
                                                                ? '#cf95e8'
                                                                : entry.name === 'Meals'
                                                                    ? '#8fcf65'
                                                                    : entry.name === 'Drinks'
                                                                        ? '#6ab3e7'
                                                                        : entry.name === 'Naps'
                                                                            ? '#a7b4cf'
                                                                            : '#9ac46e'
                                                }
                                            />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </ChartCard>

                        <ChartCard title="Current Colony State">
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie data={stateBreakdown} dataKey="value" nameKey="name" outerRadius={86} innerRadius={44}>
                                        {stateBreakdown.map((entry, index) => (
                                            <Cell key={entry.name} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                                        ))}
                                    </Pie>
                                    <Tooltip />
                                    <Legend />
                                </PieChart>
                            </ResponsiveContainer>
                        </ChartCard>
                    </Box>
                </Stack>
            </DialogContent>
        </Dialog>
    );
}

export default AnalyticsModal;
