import React, { useState } from 'react';
import { Alert, Box, Button, Paper, Stack, TextField, Typography } from '@mui/material';
import axios from 'axios';

const API_BASE = '/api';

function DetailRow({ label, value }) {
    return (
        <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>{label}</Typography>
            <Typography variant="caption" sx={{ color: 'white', textAlign: 'right' }}>{value}</Typography>
        </Box>
    );
}

function AntSearchPanel({ lineageFile, liveMode = false, liveAvailable = false }) {
    const [query, setQuery] = useState('');
    const [profile, setProfile] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);
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
        } catch (err) {
            setProfile(null);
            setError(err.response?.data?.error || err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <Paper
            elevation={8}
            sx={{
                bgcolor: 'rgba(0, 0, 0, 0.6)',
                backdropFilter: 'blur(10px)',
                border: '1px solid rgba(255,255,255,0.1)',
                p: 2,
                width: 320,
                color: 'white'
            }}
        >
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
                {liveMode ? 'Live Ant Search' : 'Ant Search'}
            </Typography>
            <Stack direction="row" spacing={1} sx={{ mb: 1.5 }}>
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
                        input: { sx: { color: 'white' } }
                    }}
                />
                <Button variant="contained" onClick={handleSearch} disabled={!isAvailable || loading}>
                    Search
                </Button>
            </Stack>

            {!isAvailable && (
                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                    {liveMode
                        ? 'Start the live colony first to inspect active ants and their current life history.'
                        : 'Run a simulation first to inspect genealogy and life history.'}
                </Typography>
            )}

            {error && <Alert severity="warning" sx={{ mb: 1.5 }}>{error}</Alert>}

            {profile && (
                <Stack spacing={0.8}>
                    <DetailRow label="Sex" value={profile.sex} />
                    <DetailRow label="Generation" value={profile.generation} />
                    <DetailRow label="Birth" value={`${profile.birthTime} min`} />
                    <DetailRow label="Mother" value={profile.motherId ?? 'N/A'} />
                    <DetailRow label="Father" value={profile.fatherId ?? 'N/A'} />
                    <DetailRow label="Children" value={profile.children.length} />
                    <DetailRow label="Matings" value={profile.mates.length} />
                    <DetailRow label="Micro-naps" value={profile.microNaps} />
                    <DetailRow label="Meals" value={profile.meals} />
                    <DetailRow label="Drinks" value={profile.drinks} />
                    <DetailRow label="Visited chambers" value={profile.visitedChambers.join(', ')} />
                    <DetailRow label="Status" value={profile.alive ? 'Alive' : `Dead (${profile.deathCause})`} />
                    <DetailRow label="Death" value={profile.deathTime ?? 'Still alive'} />
                </Stack>
            )}
        </Paper>
    );
}

export default AntSearchPanel;
