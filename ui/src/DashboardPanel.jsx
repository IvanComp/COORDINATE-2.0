import React from 'react';
import { Box, Chip, Paper, Stack, Typography } from '@mui/material';

function StatCard({ label, value, accent }) {
    return (
        <Paper
            sx={{
                p: 1.4,
                minWidth: 110,
                bgcolor: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: 'white',
            }}
        >
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.62)' }}>
                {label}
            </Typography>
            <Typography variant="h6" sx={{ mt: 0.35, color: accent || 'white', fontWeight: 700 }}>
                {value}
            </Typography>
        </Paper>
    );
}

function DashboardPanel({ title, subtitle, badges = [], stats = [] }) {
    return (
        <Paper
            sx={{
                width: 'min(860px, calc(100vw - 32px))',
                p: 1.8,
                bgcolor: 'rgba(0,0,0,0.58)',
                backdropFilter: 'blur(12px)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: 'white',
            }}
        >
            <Stack spacing={1.3}>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.2} justifyContent="space-between" alignItems={{ xs: 'flex-start', md: 'center' }}>
                    <Box>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                            {title}
                        </Typography>
                        {subtitle && (
                            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.65)' }}>
                                {subtitle}
                            </Typography>
                        )}
                    </Box>
                    {badges.length > 0 && (
                        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                            {badges.map((badge) => (
                                <Chip
                                    key={badge.label}
                                    label={badge.label}
                                    size="small"
                                    sx={{
                                        bgcolor: badge.bg || 'rgba(255,255,255,0.08)',
                                        color: badge.color || 'white',
                                        border: '1px solid rgba(255,255,255,0.08)',
                                    }}
                                />
                            ))}
                        </Stack>
                    )}
                </Stack>

                <Box
                    sx={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
                        gap: 1,
                    }}
                >
                    {stats.map((stat) => (
                        <StatCard key={stat.label} label={stat.label} value={stat.value} accent={stat.accent} />
                    ))}
                </Box>
            </Stack>
        </Paper>
    );
}

export default DashboardPanel;
