import React, { useMemo, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import {
    Alert,
    Box,
    Button,
    Dialog,
    DialogContent,
    DialogTitle,
    LinearProgress,
    Paper,
    Stack,
    TextField,
    Typography,
} from '@mui/material';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import IconButton from '@mui/material/IconButton';
import axios from 'axios';

const API_BASE = '/api';

const FEMALE_NAMES = ['Amber', 'Willow', 'Poppy', 'Hazel', 'Maple', 'Clover', 'Ivy', 'Juniper', 'Nectar', 'Ember', 'Daisy', 'Mira'];
const MALE_NAMES = ['Ash', 'Rowan', 'Flint', 'Moss', 'Cedar', 'Bramble', 'Orion', 'Atlas', 'Acorn', 'Rusty', 'Silas', 'Pico'];
const TITLE_PARTS = ['Swift', 'Bold', 'Quiet', 'Golden', 'Dusky', 'Tiny', 'Clever', 'Sturdy', 'Lively', 'Gentle', 'Watchful', 'Wild'];
const TRAIT_BANK = {
    build: ['slender frame', 'compact body', 'broad thorax', 'nimble stance', 'lean runner', 'steady posture'],
    pattern: ['amber stripe', 'dark shell', 'bright crest', 'soft sheen', 'dusty markings', 'glossy armor'],
    vibe: ['curious explorer', 'restless scout', 'careful worker', 'calm forager', 'fierce defender', 'patient wanderer'],
    quirk: ['quick antennae', 'heavy sleeper', 'sharp turner', 'long-route walker', 'food hoarder', 'water seeker'],
};

function mixHex(colorA, colorB, ratio = 0.5) {
    const a = colorA.replace('#', '');
    const b = colorB.replace('#', '');
    const clamp = Math.max(0, Math.min(1, ratio));
    const mix = [0, 2, 4].map((index) => {
        const av = Number.parseInt(a.slice(index, index + 2), 16);
        const bv = Number.parseInt(b.slice(index, index + 2), 16);
        return Math.round((av * (1 - clamp)) + (bv * clamp)).toString(16).padStart(2, '0');
    });
    return `#${mix.join('')}`;
}

function antTint(profile) {
    if (!profile?.alive) return '#7b5954';
    if (profile?.state === 'sleeping') return '#9a8bc9';
    if (profile?.state === 'mating') return '#cf95e8';
    return profile?.sex === 'F' ? '#f28bb3' : '#7ca6ff';
}

function seededNoise(seed) {
    const value = Math.sin(seed * 91.173) * 43758.5453123;
    return value - Math.floor(value);
}

function pickFrom(list, seed) {
    return list[Math.floor(seededNoise(seed) * list.length) % list.length];
}

function buildIdentity(profile) {
    const base = Number(profile?.id || 0) + (Number(profile?.generation || 0) * 13);
    const first = pickFrom(profile?.sex === 'F' ? FEMALE_NAMES : MALE_NAMES, base + 1);
    const title = pickFrom(TITLE_PARTS, base + 2);
    return {
        name: `${first} the ${title}`,
        appearance: {
            shellMix: 0.64 + (seededNoise(base + 1) * 0.18),
            accentMix: 0.12 + (seededNoise(base + 2) * 0.28),
            stripeScale: 0.6 + (seededNoise(base + 3) * 0.35),
            antennaTilt: 0.32 + (seededNoise(base + 4) * 0.4),
            eyeScale: 0.85 + (seededNoise(base + 5) * 0.4),
        },
    };
}

function AntModel({ profile }) {
    const color = antTint(profile);
    const identity = buildIdentity(profile);
    const shellColor = !profile?.alive ? '#503631' : mixHex(color, '#2a1f19', identity.appearance.shellMix);
    const limbColor = profile?.state === 'sleeping' ? '#ddd4f4' : mixHex(shellColor, '#eadfc7', 0.18);
    const accentColor = !profile?.alive ? '#7b5954' : mixHex(color, '#ffffff', identity.appearance.accentMix);
    const eyeColor = profile?.state === 'sleeping' ? '#efe9ff' : '#0f0b09';
    const stripeColor = !profile?.alive ? '#6b4f49' : color;

    return (
        <group rotation={[0.2, -0.55, 0]}>
            <mesh castShadow receiveShadow position={[-0.66, 0.06, 0]} scale={profile?.sex === 'F' ? [1.3, 1.04, 0.98] : [1.16, 0.98, 0.9]}>
                <sphereGeometry args={[0.58, 24, 24]} />
                <meshStandardMaterial color={shellColor} roughness={0.58} metalness={0.08} emissive={shellColor} emissiveIntensity={0.04} />
            </mesh>
            <mesh castShadow position={[-0.7, 0.18, 0]} scale={[0.46 + (identity.appearance.stripeScale * 0.3), 0.2, 0.38 + (identity.appearance.stripeScale * 0.2)]}>
                <sphereGeometry args={[0.4, 20, 20]} />
                <meshStandardMaterial color={stripeColor} roughness={0.7} emissive={stripeColor} emissiveIntensity={0.08} />
            </mesh>
            <mesh castShadow position={[0.0, 0.08, 0]} scale={[1.26, 1.04, 1.08]}>
                <sphereGeometry args={[0.4, 20, 20]} />
                <meshStandardMaterial color={shellColor} roughness={0.52} metalness={0.07} />
            </mesh>
            <mesh castShadow position={[0.64, 0.16, 0]} scale={[1.02, 0.94, 0.98]}>
                <sphereGeometry args={[0.3, 18, 18]} />
                <meshStandardMaterial color={shellColor} roughness={0.46} metalness={0.06} />
            </mesh>
            <mesh castShadow position={[0.86, 0.1, 0]} scale={[0.44, 0.32, 0.58]}>
                <sphereGeometry args={[0.24, 16, 16]} />
                <meshStandardMaterial color={accentColor} roughness={0.76} emissive={accentColor} emissiveIntensity={0.06} />
            </mesh>
            {[-0.34, 0, 0.34].map((offset, index) => (
                <group key={offset} position={[-0.08, -0.06, offset]}>
                    <mesh rotation={[0, 0, Math.PI / (3.2 + (index * 0.24))]}>
                        <cylinderGeometry args={[0.028, 0.032, 1.25, 8]} />
                        <meshStandardMaterial color={limbColor} />
                    </mesh>
                    <mesh rotation={[0, 0, -Math.PI / (3.2 + (index * 0.24))]}>
                        <cylinderGeometry args={[0.028, 0.032, 1.25, 8]} />
                        <meshStandardMaterial color={limbColor} />
                    </mesh>
                </group>
            ))}
            <group position={[0.8, 0.34, 0]}>
                <mesh rotation={[identity.appearance.antennaTilt, 0.12, Math.PI / 4.2]}>
                    <cylinderGeometry args={[0.018, 0.02, 0.95, 8]} />
                    <meshStandardMaterial color={limbColor} />
                </mesh>
                <mesh rotation={[-identity.appearance.antennaTilt, -0.12, -Math.PI / 4.2]}>
                    <cylinderGeometry args={[0.018, 0.02, 0.95, 8]} />
                    <meshStandardMaterial color={limbColor} />
                </mesh>
            </group>
            <mesh position={[0.77, 0.22, 0.14]}>
                <sphereGeometry args={[0.04 + (0.02 * identity.appearance.eyeScale), 10, 10]} />
                <meshStandardMaterial color={eyeColor} emissive={eyeColor} emissiveIntensity={0.18} />
            </mesh>
            <mesh position={[0.77, 0.22, -0.14]}>
                <sphereGeometry args={[0.04 + (0.02 * identity.appearance.eyeScale), 10, 10]} />
                <meshStandardMaterial color={eyeColor} emissive={eyeColor} emissiveIntensity={0.18} />
            </mesh>
        </group>
    );
}

function AntPreview({ profile }) {
    return (
        <Box
            sx={{
                height: { xs: 260, md: 360 },
                borderRadius: 3,
                overflow: 'hidden',
                border: '1px solid rgba(255,255,255,0.08)',
                background: 'radial-gradient(circle at top left, rgba(255,244,200,0.35), transparent 28%), linear-gradient(180deg, #abd5f0 0%, #89be63 42%, #59402a 100%)',
            }}
        >
            <Canvas camera={{ position: [0, 1.7, 5.8], fov: 34 }} shadows>
                <ambientLight intensity={1.2} />
                <directionalLight position={[6, 8, 5]} intensity={1.45} castShadow />
                <pointLight position={[-4, 4, -3]} intensity={0.55} color="#ffefc9" />
                <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow position={[0, -0.72, 0]}>
                    <circleGeometry args={[4, 36]} />
                    <meshStandardMaterial color="#b07a49" roughness={1} />
                </mesh>
                <AntModel profile={profile} />
                <OrbitControls enablePan={false} minDistance={4.5} maxDistance={7} />
            </Canvas>
        </Box>
    );
}

function DetailRow({ label, value }) {
    return (
        <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
            <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.68)' }}>{label}</Typography>
            <Typography variant="body2" sx={{ color: 'white', textAlign: 'right' }}>{value}</Typography>
        </Box>
    );
}

function StatBlock({ profile }) {
    const visited = useMemo(() => (profile?.visitedChambers || []).slice(-12), [profile]);
    const identity = useMemo(() => buildIdentity(profile), [profile]);
    const sexLabel = profile.sex === 'F' ? '♀ Female' : '♂ Male';

    return (
        <Stack spacing={1.2}>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                <Typography variant="h6" sx={{ color: 'white', fontWeight: 800 }}>
                    {identity.name}
                </Typography>
                <Typography variant="body2" sx={{ color: antTint(profile), alignSelf: 'center' }}>
                    {sexLabel}
                </Typography>
                <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.68)', alignSelf: 'center' }}>
                    {profile.alive ? profile.state : `Dead${profile.deathCause ? ` • ${profile.deathCause}` : ''}`}
                </Typography>
            </Stack>
            <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.78)' }}>
                Ant #{profile.id}
            </Typography>

            <DetailRow label="Generation" value={profile.generation} />
            <DetailRow label="Birth time" value={`${profile.birthTime} min`} />
            <DetailRow label="Current chamber" value={profile.position} />
            <DetailRow label="Destination" value={profile.destination} />
            <DetailRow label="Hunger" value={profile.hunger} />
            <DetailRow label="Thirst" value={profile.thirst} />
            <DetailRow label="Energy" value={profile.energy} />
            <DetailRow label="Children" value={profile.children.length} />
            <DetailRow label="Matings" value={profile.mates.length} />
            <DetailRow label="Meals" value={profile.meals} />
            <DetailRow label="Drinks" value={profile.drinks} />
            <DetailRow label="Micro-naps" value={profile.microNaps} />
            <DetailRow label="Moves" value={profile.moves} />
            <DetailRow label="Mother" value={profile.motherId ?? 'N/A'} />
            <DetailRow label="Father" value={profile.fatherId ?? 'N/A'} />
            <DetailRow label="Death time" value={profile.deathTime ?? 'Still alive'} />

            <Box sx={{ mt: 1 }}>
                <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.68)', mb: 0.7 }}>
                    Recently visited chambers
                </Typography>
                <Typography variant="body2" sx={{ color: 'white', lineHeight: 1.6 }}>
                    {visited.length ? visited.join(', ') : 'No chamber history yet'}
                </Typography>
            </Box>
        </Stack>
    );
}

function AntSearchPanel({ lineageFile, liveMode = false, liveAvailable = false, width = 320 }) {
    const [query, setQuery] = useState('');
    const [profile, setProfile] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);
    const [open, setOpen] = useState(false);
    const isAvailable = liveMode ? liveAvailable : Boolean(lineageFile);

    const handleSearch = async () => {
        if (!isAvailable || query === '') return;
        setLoading(true);
        setError(null);
        try {
            const endpoint = liveMode
                ? `${API_BASE}/live/ant/${Number(query)}`
                : `${API_BASE}/ant/${lineageFile}/${Number(query)}`;
            const res = await axios.get(endpoint);
            setProfile(res.data.profile);
            setOpen(true);
        } catch (err) {
            setProfile(null);
            setOpen(false);
            setError(err.response?.data?.error || err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            <Paper
                elevation={8}
                sx={{
                    bgcolor: 'rgba(0, 0, 0, 0.6)',
                    backdropFilter: 'blur(10px)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    p: 2,
                    width,
                    color: 'white',
                }}
            >
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
                    {liveMode ? 'Live Ant Search' : 'Batch Ant Search'}
                </Typography>
                <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
                    <TextField
                        size="small"
                        fullWidth
                        type="number"
                        label="Ant ID"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        disabled={!isAvailable}
                        slotProps={{
                            inputLabel: { sx: { color: 'rgba(255,255,255,0.75)' } },
                            input: { sx: { color: 'white' } },
                        }}
                    />
                    <Button variant="contained" onClick={handleSearch} disabled={!isAvailable || loading}>
                        Search
                    </Button>
                </Stack>

                {loading && <LinearProgress sx={{ mb: 1.2, borderRadius: 999, bgcolor: 'rgba(255,255,255,0.08)' }} />}

                {!isAvailable && (
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                        {liveMode
                            ? 'Start the live colony first to inspect active ants and their current life history.'
                            : 'Run a simulation first to inspect genealogy and life history.'}
                    </Typography>
                )}

                {error && <Alert severity="warning" sx={{ mt: 1 }}>{error}</Alert>}
            </Paper>

            <Dialog open={open && Boolean(profile)} onClose={() => setOpen(false)} maxWidth="lg" fullWidth>
                <DialogTitle sx={{ pr: 7 }}>
                    Ant Profile
                    <IconButton onClick={() => setOpen(false)} sx={{ position: 'absolute', right: 12, top: 12 }}>
                        <CloseRoundedIcon />
                    </IconButton>
                </DialogTitle>
                <DialogContent sx={{ bgcolor: '#0f1318' }}>
                    {profile && (
                        <Box
                            sx={{
                                display: 'grid',
                                gridTemplateColumns: { xs: '1fr', md: 'minmax(320px, 0.95fr) minmax(320px, 1.05fr)' },
                                gap: 2.5,
                                alignItems: 'start',
                            }}
                        >
                            <AntPreview profile={profile} />
                            <Paper
                                sx={{
                                    p: 2.2,
                                    bgcolor: 'rgba(255,255,255,0.04)',
                                    border: '1px solid rgba(255,255,255,0.08)',
                                    color: 'white',
                                    borderRadius: 3,
                                }}
                            >
                                <StatBlock profile={profile} />
                            </Paper>
                        </Box>
                    )}
                </DialogContent>
            </Dialog>
        </>
    );
}

export default AntSearchPanel;
