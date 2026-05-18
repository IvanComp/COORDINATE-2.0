import React, { useEffect, useMemo, useState } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    Button,
    Box,
    Typography,
    Paper,
    IconButton,
    Select,
    MenuItem,
    Checkbox,
    FormControlLabel
} from '@mui/material';
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import TableChartRoundedIcon from '@mui/icons-material/TableChartRounded';
import {
    ResponsiveContainer,
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    BarChart,
    Bar,
    PieChart,
    Pie,
    Cell,
    AreaChart,
    Area
} from 'recharts';
import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';
import { calculateRoomPositions } from './layoutUtils';

function pastelFromString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i += 1) hash = str.charCodeAt(i) + ((hash << 5) - hash);
    const hue = Math.abs(hash) % 360;
    return `hsl(${hue}, 65%, 78%)`;
}

function normalizeNum(v, fallback = 0) {
    if (typeof v === 'number') return v;
    const n = Number(v);
    return Number.isFinite(n) ? n : fallback;
}

function FailedXDot(props) {
    const { cx, cy, stroke = '#ff3b30' } = props;
    if (cx == null || cy == null) return null;
    const s = 4;
    return (
        <g>
            <line x1={cx - s} y1={cy - s} x2={cx + s} y2={cy + s} stroke={stroke} strokeWidth={1.8} />
            <line x1={cx - s} y1={cy + s} x2={cx + s} y2={cy - s} stroke={stroke} strokeWidth={1.8} />
        </g>
    );
}

function PackageIcon({ x, y, width, height, color }) {
    const bodyH = height * 0.72;
    const lidH = height * 0.28;
    const stroke = 'rgba(81, 65, 32, 0.35)';
    return (
        <g>
            <rect x={x} y={y + lidH} width={width} height={bodyH} rx={1.5} fill={color} stroke={stroke} strokeWidth={0.6} />
            <rect x={x} y={y} width={width} height={lidH + 1} rx={1.5} fill="rgba(255,255,255,0.26)" stroke={stroke} strokeWidth={0.6} />
            <line x1={x + width * 0.5} y1={y + 1} x2={x + width * 0.5} y2={y + height - 1} stroke={stroke} strokeWidth={0.55} />
        </g>
    );
}

function PackageStackShape(props) {
    const { x, y, width, height, fill, payload, dataKey } = props;
    const value = Number(payload?.[dataKey] || 0);
    if (!value || width <= 0 || height <= 0) return null;

    const iconW = Math.max(12, Math.min(22, width * 0.42));
    const iconH = Math.max(10, Math.min(16, height / Math.max(value, 1)));
    const gap = 1.5;
    const maxIcons = Math.max(1, Math.floor((height + gap) / (iconH + gap)));
    const visibleIcons = Math.min(value, maxIcons);
    const startX = x + (width - iconW) / 2;
    const baseY = y + height - iconH;

    return (
        <g>
            {Array.from({ length: visibleIcons }).map((_, idx) => (
                <PackageIcon
                    key={`${dataKey}-${idx}`}
                    x={startX}
                    y={baseY - idx * (iconH + gap)}
                    width={iconW}
                    height={iconH}
                    color={fill}
                />
            ))}
        </g>
    );
}

const EVENTS_TIMELINE_COLORS = {
    created: '#A5D6A7',
    delivered: '#A7C7FF',
    failed: '#ff3b30'
};

const EVENT_DISTRIBUTION_COLORS = {
    create: '#A5D6A7',
    deliver: '#A7C7FF',
    fail: '#ff3b30',
    recover: pastelFromString('failures'),
    recovery: pastelFromString('failures'),
    expire: pastelFromString('backlog')
};

const LATENCY_HISTOGRAM_COLOR = '#B8E0D2';
const AGENT_ACTIVITY_COLORS = [
    '#B8E0D2',
    '#AFCBFF',
    '#FFF2B2',
    '#CDECCF',
    '#D6C5F0',
    '#C7E9F1',
    '#F9D8A7',
    '#C4E7D0',
    '#D4E4FF',
    '#F7EDB2',
    '#BFE3E0',
    '#D8D0F5'
];

function ChartCard({
    title,
    chartId,
    children,
    onDownload,
    onDownloadData,
    leftControls = null,
    dataRows = [],
    dataFilename = ''
}) {
    return (
        <Paper sx={{ p: 1.5, minWidth: 0, bgcolor: '#fff', border: '1px solid #e5e7eb', borderRadius: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1, gap: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="subtitle2" sx={{ pr: 0.5, fontWeight: 700 }}>{title}</Typography>
                    {leftControls}
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Button
                        size="small"
                        variant="contained"
                        onClick={() => onDownloadData(dataRows, dataFilename || chartId)}
                        sx={{
                            minWidth: 34,
                            width: 34,
                            height: 34,
                            p: 0,
                            textTransform: 'none',
                            fontWeight: 600,
                            borderRadius: 1.5,
                            bgcolor: '#334155',
                            color: '#f9fafb',
                            boxShadow: 'none',
                            '&:hover': {
                                bgcolor: '#1f2937',
                                boxShadow: 'none'
                            }
                        }}
                        aria-label="Download chart data CSV"
                    >
                        <TableChartRoundedIcon fontSize="small" />
                    </Button>
                    <Button
                        size="small"
                        variant="contained"
                        onClick={() => onDownload(chartId)}
                        sx={{
                            minWidth: 34,
                            width: 34,
                            height: 34,
                            p: 0,
                            textTransform: 'none',
                            fontWeight: 600,
                            borderRadius: 1.5,
                            bgcolor: '#1f2937',
                            color: '#f9fafb',
                            boxShadow: 'none',
                            '&:hover': {
                                bgcolor: '#111827',
                                boxShadow: 'none'
                            }
                        }}
                        aria-label="Download chart PDF"
                    >
                        <DownloadRoundedIcon fontSize="small" />
                    </Button>
                </Box>
            </Box>
            <Box id={chartId} sx={{ height: { xs: 300, sm: 320, md: 360 } }}>
                {children}
            </Box>
        </Paper>
    );
}

const CHART_IDS = [
    'chart-events-timeline',
    'chart-cumulative',
    'chart-event-pie',
    'chart-importance',
    'chart-latency-hist',
    'chart-agent-activity',
    'chart-fail-recover',
    'chart-heatmap',
    'chart-success-rate',
    'chart-backlog',
    'chart-latency-by-importance',
    'chart-deliveries-by-agent'
];

const HEATMAP_BASE_WIDTH = 760;
const HEATMAP_BASE_HEIGHT = 460;

function AnalyticsModal({ open, onClose, logs = [], topology = null, topologyName = 'mesh25', nAgents = null }) {
    const [selectedAgent, setSelectedAgent] = useState('average');
    const [excludeWaiting, setExcludeWaiting] = useState(false);
    const [excludeFail, setExcludeFail] = useState(false);
    const [chartRenderKey, setChartRenderKey] = useState(0);

    useEffect(() => {
        if (!open || typeof window === 'undefined') return undefined;
        const timeout = window.setTimeout(() => {
            setChartRenderKey((k) => k + 1);
            window.dispatchEvent(new Event('resize'));
        }, 80);
        return () => window.clearTimeout(timeout);
    }, [open, logs.length, topologyName]);

    const parsedLogs = useMemo(() => {
        return (logs || []).map((row) => ({
            simTime: normalizeNum(row.simTime),
            robotId: normalizeNum(row.robotId, -1),
            itemId: normalizeNum(row.itemId, -1),
            itemImportance: normalizeNum(row.itemImportance, -1),
            position: normalizeNum(row.position, -1),
            destination: normalizeNum(row.destination, -1),
            event: row.event || ''
        }));
    }, [logs]);

    const availableAgents = useMemo(() => {
        if (Number.isInteger(nAgents) && nAgents > 0) {
            return Array.from({ length: nAgents }, (_, i) => i + 1);
        }
        const ids = [...new Set(parsedLogs.filter((r) => r.robotId >= 0).map((r) => r.robotId + 1))];
        return ids.sort((a, b) => a - b);
    }, [parsedLogs, nAgents]);

    const maxSimTime = useMemo(() => {
        if (parsedLogs.length === 0) return 1;
        return Math.max(...parsedLogs.map((r) => r.simTime), 1);
    }, [parsedLogs]);

    const bins = useMemo(() => {
        const nBins = 20;
        const w = maxSimTime / nBins;
        const arr = Array.from({ length: nBins }).map((_, i) => ({
            bin: i,
            t: Math.round(i * w),
            created: 0,
            delivered: 0,
            expired: 0,
            failed: 0,
            recovered: 0
        }));
        parsedLogs.forEach((r) => {
            const idx = Math.min(nBins - 1, Math.max(0, Math.floor(r.simTime / w)));
            if (r.event === 'create') arr[idx].created += 1;
            if (r.event === 'deliver') arr[idx].delivered += 1;
            if (r.event === 'expire') arr[idx].expired += 1;
            if (r.event === 'fail') arr[idx].failed += 1;
            if (r.event === 'recover' || r.event === 'recovery') arr[idx].recovered += 1;
        });
        return arr;
    }, [parsedLogs, maxSimTime]);

    const cumulative = useMemo(() => {
        let cCreate = 0;
        let cDeliver = 0;
        return bins.map((b) => {
            cCreate += b.created;
            cDeliver += b.delivered;
            return { t: b.t, created: cCreate, delivered: cDeliver };
        });
    }, [bins]);

    const eventDistribution = useMemo(() => {
        const counts = {};
        parsedLogs.forEach((r) => { counts[r.event] = (counts[r.event] || 0) + 1; });
        return Object.entries(counts)
            .map(([name, value]) => ({ name, value }))
            .sort((a, b) => b.value - a.value)
            .slice(0, 10);
    }, [parsedLogs]);

    const eventDistributionColor = (name) => EVENT_DISTRIBUTION_COLORS[name] || pastelFromString(name);

    const importanceDist = useMemo(() => {
        const dist = { Low: 0, Medium: 0, High: 0 };
        parsedLogs.forEach((r) => {
            if (r.event !== 'create') return;
            if (r.itemImportance === 0) dist.Low += 1;
            else if (r.itemImportance === 1) dist.Medium += 1;
            else if (r.itemImportance === 2) dist.High += 1;
        });
        return Object.entries(dist).map(([k, v]) => ({ level: k, value: v }));
    }, [parsedLogs]);

    const itemImportanceColor = (level) => {
        if (level === 'Low') return '#A5D6A7';
        if (level === 'Medium') return '#FFF59D';
        if (level === 'High') return '#EF9A9A';
        return '#9E9E9E';
    };

    const latencyHistogram = useMemo(() => {
        const createTimes = new Map();
        const latencies = [];
        parsedLogs.forEach((r) => {
            if (r.event === 'create') createTimes.set(r.itemId, r.simTime);
            if (r.event === 'deliver' && createTimes.has(r.itemId)) {
                latencies.push(r.simTime - createTimes.get(r.itemId));
            }
        });
        if (latencies.length === 0) return [];
        const maxLat = Math.max(...latencies, 1);
        const nBins = 10;
        const w = maxLat / nBins;
        const binsOut = Array.from({ length: nBins }).map((_, i) => ({ range: `${Math.round(i * w)}-${Math.round((i + 1) * w)}`, count: 0 }));
        latencies.forEach((v) => {
            const idx = Math.min(nBins - 1, Math.floor(v / w));
            binsOut[idx].count += 1;
        });
        return binsOut;
    }, [parsedLogs]);

    const agentActivity = useMemo(() => {
        const counts = {};
        parsedLogs.forEach((r) => {
            if (r.robotId === -1) return;
            const key = `A${r.robotId + 1}`;
            counts[key] = (counts[key] || 0) + 1;
        });
        return Object.entries(counts)
            .map(([agent, actions]) => ({ agent, actions }))
            .sort((a, b) => b.actions - a.actions)
            .slice(0, 12);
    }, [parsedLogs]);

    const failRecoverTrend = useMemo(() => bins.map((b) => ({ t: b.t, failures: b.failed, recoveries: b.recovered })), [bins]);

    const successRateTrend = useMemo(() => {
        let createdCum = 0;
        let deliveredCum = 0;
        return bins.map((b) => {
            createdCum += b.created;
            deliveredCum += b.delivered;
            return {
                t: b.t,
                successRate: createdCum > 0 ? (deliveredCum / createdCum) * 100 : 0
            };
        });
    }, [bins]);

    const backlogTrend = useMemo(() => {
        let backlog = 0;
        return bins.map((b) => {
            backlog += b.created - b.delivered - b.expired;
            return { t: b.t, backlog: Math.max(0, backlog) };
        });
    }, [bins]);

    const backlogByPriorityTrend = useMemo(() => {
        if (!bins.length) return [];
        const sortedLogs = [...parsedLogs].sort((a, b) => a.simTime - b.simTime);
        const pending = new Map();
        let logIdx = 0;

        return bins.map((bin) => {
            while (logIdx < sortedLogs.length && sortedLogs[logIdx].simTime <= bin.t) {
                const event = sortedLogs[logIdx];
                if (event.itemId >= 0) {
                    if (event.event === 'create') {
                        pending.set(event.itemId, event.itemImportance);
                    } else if (event.event === 'deliver' || event.event === 'expire') {
                        pending.delete(event.itemId);
                    }
                }
                logIdx += 1;
            }

            let low = 0;
            let medium = 0;
            let high = 0;
            pending.forEach((importance) => {
                if (importance === 0) low += 1;
                else if (importance === 1) medium += 1;
                else if (importance === 2) high += 1;
            });

            return {
                t: bin.t,
                low,
                medium,
                high,
                backlog: low + medium + high
            };
        });
    }, [bins, parsedLogs]);

    const latencyByImportance = useMemo(() => {
        const createInfo = new Map();
        const samples = { Low: [], Medium: [], High: [] };
        parsedLogs.forEach((r) => {
            if (r.event === 'create') {
                createInfo.set(r.itemId, { t: r.simTime, imp: r.itemImportance });
            } else if (r.event === 'deliver' && createInfo.has(r.itemId)) {
                const info = createInfo.get(r.itemId);
                const lat = r.simTime - info.t;
                if (info.imp === 0) samples.Low.push(lat);
                else if (info.imp === 1) samples.Medium.push(lat);
                else if (info.imp === 2) samples.High.push(lat);
            }
        });
        const avg = (arr) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0);
        return [
            { level: 'Low', avgLatency: avg(samples.Low), deliveries: samples.Low.length },
            { level: 'Medium', avgLatency: avg(samples.Medium), deliveries: samples.Medium.length },
            { level: 'High', avgLatency: avg(samples.High), deliveries: samples.High.length }
        ];
    }, [parsedLogs]);

    const deliveriesByAgent = useMemo(() => {
        const counts = {};
        parsedLogs.forEach((r) => {
            if (r.event === 'deliver' && r.robotId !== -1) {
                const key = `A${r.robotId + 1}`;
                counts[key] = (counts[key] || 0) + 1;
            }
        });
        return Object.entries(counts)
            .map(([agent, delivered]) => ({ agent, delivered }))
            .sort((a, b) => b.delivered - a.delivered)
            .slice(0, 12);
    }, [parsedLogs]);

    const heatmapData = useMemo(() => {
        if (!topology || !topology.nodes) return [];
        const visits = {};
        parsedLogs.forEach((r) => {
            if (r.robotId === -1 || r.position < 0) return;
            if (selectedAgent !== 'average' && String(r.robotId + 1) !== selectedAgent) return;
            // "Waiting" in the visualization corresponds to agents without an assigned item.
            if (excludeWaiting && r.itemId === -1) return;
            if (excludeFail && r.event === 'fail') return;
            visits[r.position] = (visits[r.position] || 0) + 1;
        });
        const positions = calculateRoomPositions(topology, topologyName);
        const nodes = topology.nodes.map((n) => ({
            id: n.id,
            visits: visits[n.id] || 0,
            x: positions[n.id]?.x ?? 0,
            z: positions[n.id]?.z ?? 0
        }));
        const minX = Math.min(...nodes.map((n) => n.x));
        const maxX = Math.max(...nodes.map((n) => n.x));
        const minZ = Math.min(...nodes.map((n) => n.z));
        const maxZ = Math.max(...nodes.map((n) => n.z));
        const rangeX = Math.max(maxX - minX, 1);
        const rangeZ = Math.max(maxZ - minZ, 1);
        // Keep topology aspect ratio to avoid visual stretching.
        const scale = 92 / Math.max(rangeX, rangeZ);
        const width = rangeX * scale;
        const height = rangeZ * scale;
        const offsetX = (100 - width) / 2;
        const offsetZ = (100 - height) / 2;
        const maxV = Math.max(...nodes.map((n) => n.visits), 1);
        return nodes.map((n) => ({
            ...n,
            nx: (n.x - minX) * scale + offsetX,
            nz: (n.z - minZ) * scale + offsetZ,
            intensity: n.visits / maxV
        }));
    }, [parsedLogs, topology, topologyName, selectedAgent, excludeWaiting, excludeFail]);

    const lerp = (a, b, t) => a + (b - a) * t;
    const lerpColor = (c1, c2, t) => ([
        Math.round(lerp(c1[0], c2[0], t)),
        Math.round(lerp(c1[1], c2[1], t)),
        Math.round(lerp(c1[2], c2[2], t))
    ]);
    const colorFromScale = (t) => {
        // palette tuned to match the reference look:
        // lavender/cool edge -> cyan -> green -> yellow -> orange -> red
        const stops = [
            { p: 0.00, c: [220, 220, 242] },
            { p: 0.14, c: [160, 170, 236] },
            { p: 0.30, c: [106, 236, 255] },
            { p: 0.48, c: [108, 246, 140] },
            { p: 0.66, c: [250, 242, 110] },
            { p: 0.84, c: [255, 164, 84] },
            { p: 1.00, c: [255, 58, 58] }
        ];
        if (t <= 0) return stops[0].c;
        for (let i = 0; i < stops.length - 1; i += 1) {
            if (t <= stops[i + 1].p) {
                const lt = (t - stops[i].p) / (stops[i + 1].p - stops[i].p);
                return lerpColor(stops[i].c, stops[i + 1].c, lt);
            }
        }
        return stops[stops.length - 1].c;
    };

    const heatmapImageUrl = useMemo(() => {
        if (typeof document === 'undefined') return null;
        const visited = heatmapData.filter((n) => n.visits > 0);
        const w = HEATMAP_BASE_WIDTH;
        const h = HEATMAP_BASE_HEIGHT;
        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        if (!ctx) return null;

        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, w, h);
        if (visited.length === 0) return canvas.toDataURL('image/png');

        const points = visited.map((n) => ({
            x: (n.nx / 100) * w,
            y: (n.nz / 100) * h,
            v: Math.max(0.05, n.intensity)
        }));

        // Large sigma makes the heat "communicating" and continuous.
        const sigma = Math.min(w, h) * 0.12;
        const denom = 2 * sigma * sigma;
        const field = new Float32Array(w * h);
        let maxVal = 0;

        for (let y = 0; y < h; y += 1) {
            for (let x = 0; x < w; x += 1) {
                let value = 0;
                const wx = x + (Math.sin(y * 0.035) * 9) + (Math.sin((x + y) * 0.02) * 6);
                const wy = y + (Math.sin(x * 0.03) * 8) + (Math.sin((x - y) * 0.018) * 5);
                for (const p of points) {
                    const dx = wx - p.x;
                    const dy = wy - p.y;
                    value += p.v * Math.exp(-(dx * dx + dy * dy) / denom);
                }
                const idx = y * w + x;
                field[idx] = value;
                if (value > maxVal) maxVal = value;
            }
        }

        const image = ctx.createImageData(w, h);
        const out = image.data;
        const norm = maxVal > 0 ? maxVal : 1;

        for (let i = 0; i < field.length; i += 1) {
            const t = Math.min(1, field[i] / norm);
            const x = i % w;
            const y = Math.floor(i / w);
            const n = (
                Math.sin(x * 0.09) * 0.5 +
                Math.sin(y * 0.11) * 0.35 +
                Math.sin((x + y) * 0.05) * 0.25
            ) * 0.03;
            const mapped = Math.min(1, Math.max(0, Math.pow(t, 0.74) + n));
            let [r, g, b] = colorFromScale(mapped);

            // Cool vignette toward corners to mimic the reference.
            const nx = (x - w / 2) / (w / 2);
            const ny = (y - h / 2) / (h / 2);
            const edge = Math.min(1, Math.sqrt(nx * nx + ny * ny));
            const cool = Math.max(0, (edge - 0.62) / 0.38);
            if (cool > 0) {
                const coolColor = [120, 132, 214];
                r = Math.round(lerp(r, coolColor[0], cool * 0.55));
                g = Math.round(lerp(g, coolColor[1], cool * 0.55));
                b = Math.round(lerp(b, coolColor[2], cool * 0.55));
            }
            const o = i * 4;
            out[o] = r;
            out[o + 1] = g;
            out[o + 2] = b;
            out[o + 3] = 255;
        }

        ctx.putImageData(image, 0, 0);
        return canvas.toDataURL('image/png');
    }, [heatmapData]);

    const downloadChartPdf = async (chartId) => {
        const el = document.getElementById(chartId);
        if (!el) return;
        const exportScale = chartId === CHART_IDS[7] ? 5 : 3;
        const canvas = await html2canvas(el, { scale: exportScale, backgroundColor: '#ffffff', useCORS: true });
        const imgData = canvas.toDataURL('image/png');
        const pdf = new jsPDF('landscape', 'pt', [canvas.width, canvas.height]);
        pdf.addImage(imgData, 'PNG', 0, 0, canvas.width, canvas.height);
        pdf.save(`${chartId}.pdf`);
    };

    const toCsv = (rows) => {
        if (!rows || rows.length === 0) return '';
        const headers = Object.keys(rows[0]);
        const esc = (v) => {
            if (v == null) return '';
            const s = String(v);
            return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
        };
        return [
            headers.join(','),
            ...rows.map((r) => headers.map((h) => esc(r[h])).join(','))
        ].join('\n');
    };

    const downloadChartDataCsv = (rows, basename) => {
        const csv = toCsv(rows);
        if (!csv) return;
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${basename}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    };

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth="xl"
            fullWidth
            BackdropProps={{ sx: { backgroundColor: 'rgba(0,0,0,0.82)' } }}
            PaperProps={{
                sx: {
                    bgcolor: '#0b0b0f',
                    color: '#f3f4f6',
                    border: '1px solid #1f2937'
                }
            }}
        >
            <DialogTitle sx={{ borderBottom: '1px solid #1f2937', pr: 6, position: 'relative' }}>
                <IconButton
                    onClick={onClose}
                    size="small"
                    sx={{
                        position: 'absolute',
                        top: 10,
                        right: 10,
                        color: '#d1d5db',
                        border: '1px solid #374151',
                        bgcolor: '#111827',
                        '&:hover': { bgcolor: '#1f2937' }
                    }}
                    aria-label="Close dashboard"
                >
                    <CloseRoundedIcon fontSize="small" />
                </IconButton>
                Dashboard
            </DialogTitle>
            <DialogContent dividers sx={{ borderColor: '#1f2937', p: { xs: 1.5, md: 2 } }}>
                <Box
                    key={`charts-${chartRenderKey}`}
                    sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, minmax(0, 1fr))' }, gap: 2, alignItems: 'start' }}
                >
                    <Box sx={{ minWidth: 0 }}>
                        <ChartCard title="Events Timeline" chartId={CHART_IDS[0]} onDownload={downloadChartPdf} onDownloadData={downloadChartDataCsv} dataRows={bins} dataFilename="events_timeline">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={bins} margin={{ top: 12, right: 24, left: 10, bottom: 52 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="t" tickMargin={10} height={46} label={{ value: 'Time (s)', position: 'bottom', offset: 8 }} />
                                    <YAxis label={{ value: 'Events (#)', angle: -90, position: 'insideLeft' }} />
                                    <Tooltip />
                                    <Line type="monotone" dataKey="created" stroke={EVENTS_TIMELINE_COLORS.created} strokeWidth={2} />
                                    <Line type="monotone" dataKey="delivered" stroke={EVENTS_TIMELINE_COLORS.delivered} strokeWidth={2} />
                                    <Line
                                        type="monotone"
                                        dataKey="failed"
                                        stroke={EVENTS_TIMELINE_COLORS.failed}
                                        strokeWidth={2}
                                        dot={<FailedXDot />}
                                        activeDot={<FailedXDot />}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        </ChartCard>
                    </Box>

                    <Box sx={{ minWidth: 0 }}>
                        <ChartCard title="Cumulative Item Throughput" chartId={CHART_IDS[1]} onDownload={downloadChartPdf} onDownloadData={downloadChartDataCsv} dataRows={cumulative} dataFilename="cumulative_item_throughput">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={cumulative} margin={{ top: 12, right: 24, left: 10, bottom: 52 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="t" tickMargin={10} height={46} label={{ value: 'Time (s)', position: 'bottom', offset: 8 }} />
                                    <YAxis label={{ value: 'Cumulative items (#)', angle: -90, position: 'insideLeft', dy: 45 }} />
                                    <Tooltip />
                                    <Line type="monotone" dataKey="created" stroke={EVENTS_TIMELINE_COLORS.created} strokeWidth={2} />
                                    <Line type="monotone" dataKey="delivered" stroke={EVENTS_TIMELINE_COLORS.delivered} strokeWidth={2} />
                                </LineChart>
                            </ResponsiveContainer>
                        </ChartCard>
                    </Box>

                    <Box sx={{ minWidth: 0 }}>
                        <ChartCard title="Event Distribution" chartId={CHART_IDS[2]} onDownload={downloadChartPdf} onDownloadData={downloadChartDataCsv} dataRows={eventDistribution} dataFilename="event_distribution">
                            <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie data={eventDistribution} dataKey="value" nameKey="name" outerRadius={90} label>
                                        {eventDistribution.map((e) => <Cell key={e.name} fill={eventDistributionColor(e.name)} />)}
                                    </Pie>
                                    <Tooltip />
                                    <Legend verticalAlign="bottom" height={24} wrapperStyle={{ paddingTop: 4, marginBottom: 0 }} />
                                </PieChart>
                            </ResponsiveContainer>
                        </ChartCard>
                    </Box>

                    <Box sx={{ minWidth: 0 }}>
                        <ChartCard title="Created Items by Importance" chartId={CHART_IDS[3]} onDownload={downloadChartPdf} onDownloadData={downloadChartDataCsv} dataRows={importanceDist} dataFilename="created_items_by_importance">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={importanceDist} margin={{ top: 12, right: 24, left: 10, bottom: 52 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="level" tickMargin={10} height={46} label={{ value: 'Importance level', position: 'bottom', offset: 8 }} />
                                    <YAxis label={{ value: 'Created items (#)', angle: -90, position: 'insideLeft', dy: 45 }} />
                                    <Tooltip />
                                    <Bar dataKey="value">
                                        {importanceDist.map((d) => <Cell key={d.level} fill={itemImportanceColor(d.level)} />)}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </ChartCard>
                    </Box>

                    <Box sx={{ minWidth: 0 }}>
                        <ChartCard title="Delivery Latency Histogram" chartId={CHART_IDS[4]} onDownload={downloadChartPdf} onDownloadData={downloadChartDataCsv} dataRows={latencyHistogram} dataFilename="delivery_latency_histogram">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={latencyHistogram} margin={{ top: 12, right: 24, left: 10, bottom: 52 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="range" tickMargin={10} height={46} label={{ value: 'Latency range (s)', position: 'bottom', offset: 8 }} />
                                    <YAxis label={{ value: 'Delivered items (#)', angle: -90, position: 'insideLeft', dy: 45 }} />
                                    <Tooltip />
                                    <Bar dataKey="count" fill={LATENCY_HISTOGRAM_COLOR} />
                                </BarChart>
                            </ResponsiveContainer>
                        </ChartCard>
                    </Box>

                    <Box sx={{ minWidth: 0 }}>
                        <ChartCard title="Agent Activity (Top)" chartId={CHART_IDS[5]} onDownload={downloadChartPdf} onDownloadData={downloadChartDataCsv} dataRows={agentActivity} dataFilename="agent_activity_top">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={agentActivity} margin={{ top: 12, right: 24, left: 10, bottom: 52 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="agent" tickMargin={10} height={46} label={{ value: 'Agent ID', position: 'bottom', offset: 8 }} />
                                    <YAxis label={{ value: 'Actions (#)', angle: -90, position: 'insideLeft' }} />
                                    <Tooltip />
                                    <Bar dataKey="actions">
                                        {agentActivity.map((d, idx) => <Cell key={d.agent} fill={AGENT_ACTIVITY_COLORS[idx % AGENT_ACTIVITY_COLORS.length]} />)}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </ChartCard>
                    </Box>

                    <Box sx={{ minWidth: 0 }}>
                        <ChartCard title="Failures vs Recoveries" chartId={CHART_IDS[6]} onDownload={downloadChartPdf} onDownloadData={downloadChartDataCsv} dataRows={failRecoverTrend} dataFilename="failures_vs_recoveries">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={failRecoverTrend} margin={{ top: 12, right: 24, left: 10, bottom: 52 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="t" tickMargin={10} height={46} label={{ value: 'Time (s)', position: 'bottom', offset: 8 }} />
                                    <YAxis label={{ value: 'Events (#)', angle: -90, position: 'insideLeft' }} />
                                    <Tooltip />
                                    <Area type="monotone" dataKey="failures" stroke={pastelFromString('recoveries')} fill={pastelFromString('recoveries')} />
                                    <Area type="monotone" dataKey="recoveries" stroke={pastelFromString('failures')} fill={pastelFromString('failures')} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </ChartCard>
                    </Box>

                    <Box sx={{ minWidth: 0 }}>
                        <ChartCard
                            title="Agent Room Visit Frequency"
                            chartId={CHART_IDS[7]}
                            onDownload={downloadChartPdf}
                            onDownloadData={downloadChartDataCsv}
                            dataRows={heatmapData.map((n) => ({ roomId: n.id, visits: n.visits, normalizedIntensity: Number(n.intensity.toFixed(4)) }))}
                            dataFilename="agent_room_visit_frequency"
                            leftControls={(
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Select
                                        size="small"
                                        value={selectedAgent}
                                        onChange={(e) => setSelectedAgent(e.target.value)}
                                        sx={{ minWidth: 120, height: 34, fontSize: '0.8rem' }}
                                    >
                                        <MenuItem value="average">Average</MenuItem>
                                        {availableAgents.map((id) => (
                                            <MenuItem key={id} value={String(id)}>
                                                {`Agent ${id}`}
                                            </MenuItem>
                                        ))}
                                    </Select>
                                    <FormControlLabel
                                        control={
                                            <Checkbox
                                                size="small"
                                                checked={excludeWaiting}
                                                onChange={(e) => setExcludeWaiting(e.target.checked)}
                                            />
                                        }
                                        label="Exclude Waiting"
                                        sx={{ m: 0, '& .MuiFormControlLabel-label': { fontSize: '0.75rem', whiteSpace: 'nowrap' } }}
                                    />
                                    <FormControlLabel
                                        control={
                                            <Checkbox
                                                size="small"
                                                checked={excludeFail}
                                                onChange={(e) => setExcludeFail(e.target.checked)}
                                            />
                                        }
                                        label="Exclude Fail"
                                        sx={{ m: 0, '& .MuiFormControlLabel-label': { fontSize: '0.75rem', whiteSpace: 'nowrap' } }}
                                    />
                                </Box>
                            )}
                        >
                            <Box sx={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                <Box
                                    sx={{
                                        position: 'relative',
                                        width: '100%',
                                        aspectRatio: `${HEATMAP_BASE_WIDTH} / ${HEATMAP_BASE_HEIGHT}`,
                                        maxHeight: '100%',
                                        bgcolor: '#d9dbf2',
                                        border: '1px solid #c7cbe5',
                                        borderRadius: 1.5,
                                        overflow: 'hidden'
                                    }}
                                >
                                    {heatmapImageUrl && (
                                        <Box
                                            component="img"
                                            src={heatmapImageUrl}
                                            alt="Heatmap"
                                            sx={{
                                                position: 'absolute',
                                                inset: 0,
                                                width: '100%',
                                                height: '100%',
                                                objectFit: 'fill'
                                            }}
                                        />
                                    )}
                                    <svg
                                        viewBox={`0 0 ${HEATMAP_BASE_WIDTH} ${HEATMAP_BASE_HEIGHT}`}
                                        preserveAspectRatio="none"
                                        width="100%"
                                        height="100%"
                                        style={{ position: 'absolute', inset: 0, shapeRendering: 'geometricPrecision' }}
                                    >
                                    {topology?.edges?.map((e, idx) => {
                                        // Backend topology edges are exposed as { source, target }.
                                        const from = heatmapData.find((n) => n.id === e.source);
                                        const to = heatmapData.find((n) => n.id === e.target);
                                        if (!from || !to) return null;
                                        return (
                                            <line
                                                key={`${e.source}-${e.target}-${idx}`}
                                                x1={(from.nx / 100) * HEATMAP_BASE_WIDTH}
                                                y1={(from.nz / 100) * HEATMAP_BASE_HEIGHT}
                                                x2={(to.nx / 100) * HEATMAP_BASE_WIDTH}
                                                y2={(to.nz / 100) * HEATMAP_BASE_HEIGHT}
                                                stroke="rgba(0,0,0,0.24)"
                                                strokeWidth="0.62"
                                                strokeLinecap="round"
                                                vectorEffect="non-scaling-stroke"
                                            />
                                        );
                                    })}
                                    {heatmapData.map((n) => (
                                        <g key={`node-${n.id}`}>
                                            <circle
                                                cx={(n.nx / 100) * HEATMAP_BASE_WIDTH}
                                                cy={(n.nz / 100) * HEATMAP_BASE_HEIGHT}
                                                r="3"
                                                fill="rgba(139, 209, 124, 0.16)"
                                                stroke="rgba(15, 23, 42, 0.18)"
                                                strokeWidth="0.5"
                                                vectorEffect="non-scaling-stroke"
                                            />
                                            <circle
                                                cx={(n.nx / 100) * HEATMAP_BASE_WIDTH}
                                                cy={(n.nz / 100) * HEATMAP_BASE_HEIGHT}
                                                r="1.85"
                                                fill="rgba(166, 221, 143, 0.62)"
                                                stroke="rgba(15, 23, 42, 0.34)"
                                                strokeWidth="0.34"
                                                vectorEffect="non-scaling-stroke"
                                            >
                                                <title>{`Room ${n.id} · visits ${n.visits}`}</title>
                                            </circle>
                                        </g>
                                    ))}
                                    </svg>
                                </Box>
                            </Box>
                        </ChartCard>
                    </Box>

                    <Box sx={{ minWidth: 0 }}>
                        <ChartCard title="Delivery Success Rate Over Time" chartId={CHART_IDS[8]} onDownload={downloadChartPdf} onDownloadData={downloadChartDataCsv} dataRows={successRateTrend} dataFilename="delivery_success_rate_over_time">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={successRateTrend} margin={{ top: 12, right: 24, left: 10, bottom: 52 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="t" tickMargin={10} height={46} label={{ value: 'Time (s)', position: 'bottom', offset: 8 }} />
                                    <YAxis domain={[0, 100]} label={{ value: 'Success Rate (%)', angle: -90, position: 'insideLeft', dy: 45 }} />
                                    <Tooltip formatter={(v) => `${Number(v).toFixed(1)}%`} />
                                    <Line type="monotone" dataKey="successRate" stroke="#A5D6A7" strokeWidth={2.5} dot={false} />
                                </LineChart>
                            </ResponsiveContainer>
                        </ChartCard>
                    </Box>

                    <Box sx={{ minWidth: 0 }}>
                        <ChartCard title="Pending Items by Priority Over Time" chartId={CHART_IDS[9]} onDownload={downloadChartPdf} onDownloadData={downloadChartDataCsv} dataRows={backlogByPriorityTrend} dataFilename="backlog_formula_over_time">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={backlogByPriorityTrend} margin={{ top: 12, right: 24, left: 10, bottom: 52 }} barGap={2}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="t" tickMargin={10} height={46} label={{ value: 'Time (s)', position: 'bottom', offset: 8 }} />
                                    <YAxis label={{ value: 'Pending Items (#)', angle: -90, position: 'insideLeft', dy: 45 }} />
                                    <Tooltip />
                                    <Bar dataKey="low" stackId="backlog" fill={itemImportanceColor('Low')} shape={<PackageStackShape />} />
                                    <Bar dataKey="medium" stackId="backlog" fill={itemImportanceColor('Medium')} shape={<PackageStackShape />} />
                                    <Bar dataKey="high" stackId="backlog" fill={itemImportanceColor('High')} shape={<PackageStackShape />} />
                                </BarChart>
                            </ResponsiveContainer>
                        </ChartCard>
                    </Box>

                    <Box sx={{ minWidth: 0 }}>
                        <ChartCard title="Average Delivery Latency by Importance" chartId={CHART_IDS[10]} onDownload={downloadChartPdf} onDownloadData={downloadChartDataCsv} dataRows={latencyByImportance} dataFilename="avg_delivery_latency_by_importance">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={latencyByImportance} margin={{ top: 12, right: 24, left: 10, bottom: 52 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="level" tickMargin={10} height={46} label={{ value: 'Importance Level', position: 'bottom', offset: 8 }} />
                                    <YAxis label={{ value: 'Latency (s)', angle: -90, position: 'insideLeft' }} />
                                    <Tooltip />
                                    <Bar dataKey="avgLatency" name="Average Latency (s)">
                                        {latencyByImportance.map((d) => <Cell key={d.level} fill={itemImportanceColor(d.level)} />)}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </ChartCard>
                    </Box>

                    <Box sx={{ minWidth: 0 }}>
                        <ChartCard title="Deliveries by Agent" chartId={CHART_IDS[11]} onDownload={downloadChartPdf} onDownloadData={downloadChartDataCsv} dataRows={deliveriesByAgent} dataFilename="deliveries_by_agent">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={deliveriesByAgent} margin={{ top: 12, right: 24, left: 10, bottom: 52 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="agent" tickMargin={10} height={46} label={{ value: 'Agent ID', position: 'bottom', offset: 8 }} />
                                    <YAxis label={{ value: 'Delivered Items (#)', angle: -90, position: 'insideLeft', dy: 45 }} />
                                    <Tooltip />
                                    <Bar dataKey="delivered" name="Delivered Items">
                                        {deliveriesByAgent.map((d, idx) => <Cell key={d.agent} fill={AGENT_ACTIVITY_COLORS[idx % AGENT_ACTIVITY_COLORS.length]} />)}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </ChartCard>
                    </Box>
                </Box>
            </DialogContent>
        </Dialog>
    );
}

export default AnalyticsModal;
