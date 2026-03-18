import React, { useState, useEffect } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    Typography,
    Box,
    Alert,
    IconButton,
    Tooltip
} from '@mui/material';
import { Close, RestartAlt, Info } from '@mui/icons-material';

/**
 * RTLola Specification Editor Modal
 * Allows users to view and edit RTLola specifications before running dynamic adaptation simulations
 */
function RTLolaEditor({ open, onClose, onSave }) {
    const [specContent, setSpecContent] = useState('');
    const [originalContent, setOriginalContent] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [hasChanges, setHasChanges] = useState(false);

    // Fetch RTLola spec when modal opens
    useEffect(() => {
        if (open) {
            fetchSpec();
        }
    }, [open]);

    // Track changes
    useEffect(() => {
        setHasChanges(specContent !== originalContent);
    }, [specContent, originalContent]);

    const fetchSpec = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch('/api/rtlola/spec');
            if (!response.ok) {
                throw new Error('Failed to fetch RTLola specification');
            }
            const data = await response.json();
            setSpecContent(data.content);
            setOriginalContent(data.content);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleReset = () => {
        setSpecContent(originalContent);
    };

    const handleSave = async () => {
        setLoading(true);
        setError(null);
        try {
            // Save the spec to backend
            const response = await fetch('/api/rtlola/spec', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ content: specContent }),
            });

            if (!response.ok) {
                throw new Error('Failed to save RTLola specification');
            }

            const data = await response.json();

            // Call parent's onSave with the spec file path
            onSave(data.specFile);
        } catch (err) {
            setError(err.message);
            setLoading(false);
        }
    };

    const handleClose = () => {
        if (hasChanges) {
            if (window.confirm('You have unsaved changes. Are you sure you want to close?')) {
                onClose();
            }
        } else {
            onClose();
        }
    };

    return (
        <Dialog
            open={open}
            onClose={handleClose}
            maxWidth="lg"
            fullWidth
            PaperProps={{
                sx: {
                    height: '90vh',
                    maxHeight: '90vh'
                }
            }}
        >
            <DialogTitle sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                borderBottom: '1px solid rgba(0, 0, 0, 0.12)',
                pb: 2
            }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="h5" component="span" sx={{ fontWeight: 'bold' }}>
                        RTLola Requirement Setup
                    </Typography>
                    <Tooltip title="Define performance indicators and thresholds. Lower values indicate better performance.">
                        <IconButton size="small">
                            <Info fontSize="small" />
                        </IconButton>
                    </Tooltip>
                </Box>
                <IconButton onClick={handleClose} size="small">
                    <Close />
                </IconButton>
            </DialogTitle>

            <DialogContent sx={{ p: 3 }}>
                <Box sx={{ mb: 2 }}>
                    <Alert severity="info" sx={{ mb: 2 }}>
                        <Typography variant="body2">
                            <strong>Performance Indicator:</strong> The RTLola specification encodes performance metrics as output streams.
                            By convention, <strong>lower values correspond to better performance</strong>.
                            You can modify the threshold that separates acceptable performance (below threshold) from poor performance (above threshold).
                        </Typography>
                    </Alert>

                    {error && (
                        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                            {error}
                        </Alert>
                    )}

                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        Editing: <code>spec2.rtlola</code>
                        {hasChanges && <span style={{ color: '#ff9800', marginLeft: 8 }}>● Modified</span>}
                    </Typography>
                </Box>

                <TextField
                    multiline
                    fullWidth
                    value={specContent}
                    onChange={(e) => setSpecContent(e.target.value)}
                    disabled={loading}
                    placeholder="Loading RTLola specification..."
                    sx={{
                        '& .MuiInputBase-root': {
                            fontFamily: 'monospace',
                            fontSize: '0.875rem',
                            lineHeight: 1.6,
                            height: 'calc(90vh - 300px)',
                            alignItems: 'flex-start'
                        },
                        '& textarea': {
                            height: '100% !important',
                            overflow: 'auto !important'
                        }
                    }}
                />
            </DialogContent>

            <DialogActions sx={{
                borderTop: '1px solid rgba(0, 0, 0, 0.12)',
                p: 2,
                gap: 1
            }}>
                <Button
                    onClick={handleReset}
                    disabled={!hasChanges || loading}
                    startIcon={<RestartAlt />}
                    variant="outlined"
                >
                    Reset to Default
                </Button>
                <Box sx={{ flex: 1 }} />
                <Button onClick={handleClose} disabled={loading}>
                    Cancel
                </Button>
                <Button
                    onClick={handleSave}
                    variant="contained"
                    disabled={loading || !specContent.trim()}
                    color="primary"
                >
                    {loading ? 'Saving...' : 'Save & Run Simulation'}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

export default RTLolaEditor;
