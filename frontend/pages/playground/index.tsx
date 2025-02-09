import React, { useState, useEffect, useRef } from 'react';
import {
    Box,
    Button,
    Typography,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogContentText,
    DialogActions,
    CircularProgress,
} from '@mui/material';
import { Autocomplete, TextField } from '@mui/material';
import { keyframes } from '@emotion/react';
import * as Tone from 'tone';

interface Note {
    id: number;
    pitch: number;
    x: number; // x position relative to the game area (excluding left margin)
    string: "E" | "A" | "D" | "G" | "B" | "e";
    velocity: number;
    timestamp: number;
    start: number;
    animationState?: 'idle' | 'hit' | 'miss';
    animationTime?: number;
}

interface GameState {
    isStarted: boolean;
    mode: 'menu' | 'upload' | 'waiting' | 'game' | 'problem' | 'finished';
    detectedNotes: Note[];
    currentNotes: Note[];
    problemNotes: Note[];
    userInput: Note[];
    score: number;
    combo: number;
    freezeNotes?: boolean;
    finalMetrics?: {
        final_score: number;
        final_combo: number;
        total_notes: number;
        time_played: number;
    };
}

interface Song {
    id: number;
    artist: string;
    title: string;
    formats: string[];
}

enum MessageType {
    CONNECT = 'connect',
    DISCONNECT = 'disconnect',
    AUDIO_CHUNK = 'audio_chunk',
    RIFF_MUTATION = 'riff_mutation',
    SCORE_UPDATE = 'score_update',
    PROBLEM_START = 'problem_start',
    PROBLEM_END = 'problem_end',
    PROBLEM_WARNING = "problem_warning",
    NOTE_HIT = 'note_hit',
    ERROR = 'error',
    SESSION_STATE = 'session_state',
    NOTE_MISS = 'note_miss',
    PAUSE_GAME = 'pause_game',
    RESUME_GAME = 'resume_game',
    SESSION_END = 'session_end',
    END_GAME = 'end_game'
}

// Explicitly type the key map so that its keys are one of the six strings.
const STRING_KEY_MAP: Record<"E" | "A" | "D" | "G" | "B" | "e", string> = {
    E: 'q',  // Low E
    A: 'w',
    D: 'e',
    G: 'r',
    B: 't',
    e: 'y'   // High E
};

// Mapping from backend-assigned string to sample key.
const STRING_TONE_MAP: Record<"E" | "A" | "D" | "G" | "B" | "e", string> = {
    E: 'E2',
    A: 'A2',
    D: 'D3',
    G: 'G3',
    B: 'B3',
    e: 'E4',
};

// Declare the strings order array with explicit types.
const stringsOrder: ("E" | "A" | "D" | "G" | "B" | "e")[] = ['E', 'A', 'D', 'G', 'B', 'e'];

// Debug logger
const debugLog = (component: string, action: string, data: any = null) => {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] ${component} - ${action}`, data ? data : '');
};

// Gradient animation for background
const gradientAnimation = keyframes`
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
`;

const gameAreaWidth = 768 - 20; // left margin is 10 on each side
const gameAreaHeight = 300;
const noteSpeed = 200;

let devMode = false;

const PlaygroundGame = () => {
    // State for game, debug info, and the instructions dialog.
    const [availableSongs, setAvailableSongs] = useState<Song[]>([]);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        const fetchSongs = async () => {
            try {
                const response = await fetch('http://localhost:8000/songs');
                const data = await response.json();
                if (data.status === 'success' && Array.isArray(data.songs)) {
                    setAvailableSongs(data.songs);
                }
            } catch (error) {
                console.error('Error fetching songs:', error);
            }
        };

        fetchSongs();
    }, []);

    const [gameState, setGameState] = useState<GameState>({
        isStarted: false,
        mode: 'menu',
        detectedNotes: [],
        currentNotes: [],
        problemNotes: [],
        userInput: [],
        score: 0,
        combo: 0,
    });
    const [debugInfo, setDebugInfo] = useState({
        wsStatus: 'disconnected',
        lastMessage: null as any,
        noteCount: 0,
        fps: 0,
        lastProcessedNote: null as Note | null,
    });
    const [instructionsOpen, setInstructionsOpen] = useState(false);
    const [problemWarning, setProblemWarning] = useState(false);
    const [isPaused, setIsPaused] = useState(false);

    // Refs for WebSocket, animation, etc.
    const wsRef = useRef<WebSocket | null>(null);
    const animationFrameRef = useRef<number>();
    const lastTimeRef = useRef<number>(0);
    const fpsCounterRef = useRef<number>(0);
    const lastFpsUpdateRef = useRef<number>(0);
    const endGameTimerRef = useRef<number | null>(null);

    // Ref for tracking keys pressed in problem mode.
    const pressedKeysRef = useRef<Set<"E" | "A" | "D" | "G" | "B" | "e">>(new Set());

    // Canvas dimensions and offsets
    const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
    const [gameAreaOffset, setGameAreaOffset] = useState({ x: 0, y: 0 });

    // Target line reference (used in normal mode for hit timing)
    const targetX = useRef(0);

    // Canvas ref
    const canvasRef = useRef<HTMLCanvasElement>(null);

    // Note positions (x coordinate relative to game area)
    const notePositionsRef = useRef<Note[]>([]);

    // Initialize the Sampler on mount.
    const acousticGuitarRef = useRef<Tone.Sampler | null>(null);
    useEffect(() => {
        acousticGuitarRef.current = new Tone.Sampler({
            urls: {
                E2: "E2.wav",
                A2: "A2.wav",
                D3: "D3.wav",
                G3: "G3.wav",
                B3: "B3.wav",
                E4: "E4.wav",
            },
            baseUrl: "/samples/guitar-acoustic/"
        }).toDestination();
    }, []);

    // Update dimensions on client side.
    useEffect(() => {
        if (typeof window !== 'undefined') {
            const updateDimensions = () => {
                debugLog('Dimensions', 'Updating window dimensions');
                const width = window.innerWidth;
                const height = window.innerHeight;
                setDimensions({ width, height });

                const xOffset = (width - gameAreaWidth) / 2;
                const yOffset = (height - gameAreaHeight) / 2 + 50;
                setGameAreaOffset({ x: xOffset, y: yOffset });

                // Target line at center (used in normal mode)
                targetX.current = xOffset + gameAreaWidth / 2;

                if (canvasRef.current) {
                    canvasRef.current.width = width;
                    canvasRef.current.height = height;
                }
            };

            updateDimensions();
            window.addEventListener('resize', updateDimensions);
            return () => window.removeEventListener('resize', updateDimensions);
        }
    }, []);

    // File upload handler.
    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        if (!event.target.files?.length) return;

        const file = event.target.files[0];
        debugLog('Upload', 'Starting file upload', { fileName: file.name, size: file.size });

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('http://localhost:8000/upload', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();
            debugLog('Upload', 'Response received', data);

            if (data.detected_notes) {
                debugLog(
                    'Notes',
                    `Received ${data.detected_notes.length} notes from upload`,
                    data.detected_notes.map((n: any) => ({ id: n.id, start: n.start }))
                );

                setGameState((prev) => ({
                    ...prev,
                    mode: 'waiting',
                    detectedNotes: data.detected_notes,
                }));

                await initializeWebSocket();

                if (wsRef.current?.readyState === WebSocket.OPEN) {
                    wsRef.current.send(
                        JSON.stringify({
                            type: MessageType.SESSION_STATE,
                            payload: {
                                current_notes: data.detected_notes,
                                is_active: false,
                                mode: 'waiting',
                                difficulty_level: 'medium',
                            },
                        })
                    );
                }
            }
        } catch (error) {
            debugLog('Upload', 'Upload error', error);
            console.error('Upload error:', error);
        }
    };

    // Handler when a preset is selected.
    const handleSongSelect = async (song: Song | null) => {
        if (!song) return;
        
        setIsLoading(true);
        debugLog('Song', 'Processing selected song', song);

        try {
            const response = await fetch(`http://localhost:8000/process-song/${song.id}`);
            const data = await response.json();
            
            if (data.status === 'success' && data.detected_notes) {
                debugLog(
                    'Notes',
                    `Received ${data.detected_notes.length} notes from selected song`,
                    data.detected_notes.map((n: any) => ({ id: n.id, start: n.start }))
                );

                setGameState((prev) => ({
                    ...prev,
                    mode: 'waiting',
                    detectedNotes: data.detected_notes,
                }));

                await initializeWebSocket();

                if (wsRef.current?.readyState === WebSocket.OPEN) {
                    wsRef.current.send(
                        JSON.stringify({
                            type: MessageType.SESSION_STATE,
                            payload: {
                                current_notes: data.detected_notes,
                                is_active: false,
                                mode: 'waiting',
                                difficulty_level: 'medium',
                            },
                        })
                    );
                }
            }
        } catch (error) {
            console.error('Error processing song:', error);
        } finally {
            setIsLoading(false);
        }
    };

    // WebSocket initialization.
    const initializeWebSocket = (): Promise<void> => {
        debugLog('WebSocket', 'Initializing connection');
        return new Promise((resolve, reject) => {
            try {
                const ws = new WebSocket('ws://localhost:8000/ws');
                wsRef.current = ws;

                ws.onopen = () => {
                    debugLog('WebSocket', 'Connection opened');
                    setDebugInfo((prev) => ({ ...prev, wsStatus: 'connected' }));
                    setGameState((prev) => ({ ...prev, mode: 'waiting' }));
                    resolve();
                };

                ws.onmessage = (event) => {
                    try {
                        debugLog('WebSocket', 'Raw message received', event.data);
                        const data = JSON.parse(event.data);
                        debugLog('WebSocket', 'Parsed message', {
                            type: data.type,
                            payload: data.payload,
                            timestamp: new Date().toISOString()
                        });
                        setDebugInfo((prev) => ({ ...prev, lastMessage: data }));
                        handleWebSocketMessage(data);
                    } catch (error) {
                        debugLog('WebSocket', 'Error handling message', {
                            error: error instanceof Error ? error.message : 'Unknown error',
                            rawData: event.data
                        });
                    }
                };

                ws.onerror = (error) => {
                    debugLog('WebSocket', 'Error occurred', error);
                    setDebugInfo((prev) => ({ ...prev, wsStatus: 'error' }));
                    reject(error);
                };

                ws.onclose = () => {
                    debugLog('WebSocket', 'Connection closed');
                    setDebugInfo((prev) => ({ ...prev, wsStatus: 'disconnected' }));
                };
            } catch (error) {
                debugLog('WebSocket', 'Initialization error', error);
                reject(error);
            }
        });
    };

    const handleWebSocketMessage = (data: any) => {
        debugLog('WebSocket', 'Processing message', {
            type: data.type,
            rawPayload: data.payload,
            timestamp: new Date().toISOString()
        });

        switch (data.type) {
            case MessageType.SESSION_STATE:
                debugLog('Session', 'Updating session state', {
                    mode: data.payload.mode,
                    noteCount: data.payload.current_notes?.length || 0,
                    score: data.payload.score,
                    combo: data.payload.combo
                });
                const notesWithPosition = (data.payload.current_notes || []).map((note: any) => ({
                    ...note,
                    x: gameAreaWidth + note.start * noteSpeed,
                    animationState: 'idle',
                    animationTime: 0
                }));
                setGameState((prev) => ({
                    ...prev,
                    mode: data.payload.mode,
                    currentNotes: notesWithPosition,
                    problemNotes: data.payload.problem_section?.notes || [],
                    score: data.payload.score,
                    combo: data.payload.combo,
                    isStarted: data.payload.is_active,
                }));
                break;

            case MessageType.RIFF_MUTATION:
                debugLog('Notes', 'Processing riff mutation', data.payload);
                processNewNotes(data.payload.notes);
                break;

            case MessageType.SCORE_UPDATE:
                debugLog('Score', 'Updating score', {
                    oldScore: gameState.score,
                    newScore: data.payload.total_score || data.payload.score,
                    oldCombo: gameState.combo,
                    newCombo: data.payload.combo,
                    rawPayload: data.payload
                });
                setGameState((prev) => {
                    const newState = {
                        ...prev,
                        score: Math.round(data.payload.total_score || data.payload.score || 0),
                        combo: Math.round(data.payload.combo || 0)
                    };
                    debugLog('Score', 'State updated', newState);
                    return newState;
                });
                break;

            case MessageType.PROBLEM_START:
                debugLog('Problem', 'Starting problem section', data.payload);
                // When a problem starts, update the state, display a warning, and (if provided) store the ideal notes.
                handleProblemSection(data.payload);
                setProblemWarning(true);
                setTimeout(() => setProblemWarning(false), 2000);
                break;

            case MessageType.PROBLEM_END:
                debugLog('Problem', 'Ending problem section', data.payload);
                setGameState((prev) => ({
                    ...prev,
                    mode: 'game',
                    freezeNotes: false,
                    problemNotes: [],
                    currentNotes: data.payload.current_notes || prev.currentNotes,
                }));
                break;
                
            
            case MessageType.SESSION_END:
                debugLog('Session', 'Received session end message', data.payload);
                // Update game state to finished and store final metrics.
                setGameState((prev) => ({
                    ...prev,
                    mode: 'finished',
                    finalMetrics: data.payload
                }));
                break;

            case MessageType.ERROR:
                debugLog('Error', 'Received error message', data.payload);
                console.error('WebSocket error:', data.payload);
                break;

            default:
                debugLog('WebSocket', 'Unknown message type', { type: data.type });
        }
    };

    const sendNoteHit = (note: Note, accuracy: number) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            const payload = {
                note_id: note.id,
                string: note.string,
                hit_time: Date.now() / 1000,
                accuracy: Math.max(-1, Math.min(1, accuracy)),
            };

            const message = {
                type: MessageType.NOTE_HIT,
                payload
            };

            debugLog('Game', 'Sending WebSocket message', {
                message,
                wsState: wsRef.current.readyState,
                noteDetails: {
                    id: note.id,
                    string: note.string,
                    x: note.x,
                    accuracy
                }
            });

            wsRef.current.send(JSON.stringify(message));
        } else {
            debugLog('Game', 'WebSocket not ready', {
                state: wsRef.current?.readyState,
                readyStateMap: {
                    0: 'CONNECTING',
                    1: 'OPEN',
                    2: 'CLOSING',
                    3: 'CLOSED'
                }
            });
        }
    };

    // Function to signal a missed note.
    const sendNoteMiss = (note: Note) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            const payload = {
                note_id: note.id,
                string: note.string,
                missed_time: Date.now() / 1000
            };

            const message = {
                type: MessageType.NOTE_MISS,
                payload
            };

            debugLog('Game', 'Sending WebSocket NOTE_MISS message', {
                message,
                noteDetails: {
                    id: note.id,
                    string: note.string,
                    x: note.x
                }
            });

            wsRef.current.send(JSON.stringify(message));
        }
    };

    // Process new notes from the backend.
    const processNewNotes = (notes: any[]) => {
        debugLog('Notes', `Processing ${notes.length} new notes`);
        const notesWithPosition = notes.map((note: any) => ({
            ...note,
            x: gameAreaWidth + note.start * noteSpeed,
            animationState: 'idle',
            animationTime: 0
        }));
        setGameState((prev) => ({
            ...prev,
            currentNotes: [...prev.currentNotes, ...notesWithPosition],
        }));
    };

    // Handle the problem section details.
    const handleProblemSection = (data: any) => {
        debugLog('Problem', 'Handling problem section', data);
        // Show the warning immediately
        setProblemWarning(true);
        
        // After 5 seconds, switch to problem mode and freeze the notes.
        setTimeout(() => {
            setProblemWarning(false);
            setGameState(prev => ({
                ...prev,
                mode: 'problem',
                freezeNotes: true,
                problemNotes: data.notes || [] 
            }));
        }, 5000);
    };

    // Effect to handle problem mode sounds and visuals
    useEffect(() => {
        if (gameState.mode === 'problem') {
            const handleProblemKeyPress = (event: KeyboardEvent) => {
                const pressedString = Object.entries(STRING_KEY_MAP).find(
                    ([, key]) => key === event.key
                )?.[0] as "E" | "A" | "D" | "G" | "B" | "e" | undefined;
                
                if (pressedString && acousticGuitarRef.current) {
                    const sampleKey = STRING_TONE_MAP[pressedString];
                    acousticGuitarRef.current.triggerAttackRelease(sampleKey, "8n");
                }
            };
            
            window.addEventListener('keydown', handleProblemKeyPress);
            return () => {
                window.removeEventListener('keydown', handleProblemKeyPress);
            };
        }
    }, [gameState.mode]);

    // Log currentNotes when they change.
    useEffect(() => {
        if (gameState.currentNotes.length > 0) {
            debugLog(
                'Notes Debug',
                'Current notes updated',
                gameState.currentNotes.map((note) => `ID: ${note.id}, start: ${note.start}`)
            );
            for (let i = 1; i < gameState.currentNotes.length; i++) {
                if (gameState.currentNotes[i].start < gameState.currentNotes[i - 1].start) {
                    debugLog('Warning', 'Notes are not in ascending order!', {
                        previous: gameState.currentNotes[i - 1],
                        current: gameState.currentNotes[i]
                    });
                }
            }
        }
    }, [gameState.currentNotes]);

    // Canvas animation loop.
    const animate = (timestamp: number) => {
        try {
            if (!lastTimeRef.current) {
                lastTimeRef.current = timestamp;
            }
            const deltaTime = timestamp - lastTimeRef.current;
            lastTimeRef.current = timestamp;
    
            fpsCounterRef.current++;
            if (timestamp - lastFpsUpdateRef.current >= 1000) {
                setDebugInfo(prev => ({ ...prev, fps: fpsCounterRef.current }));
                fpsCounterRef.current = 0;
                lastFpsUpdateRef.current = timestamp;
            }
    
            // Only update note positions if not frozen
            if (!gameState.freezeNotes) {
                notePositionsRef.current = notePositionsRef.current
                    .map((note) => {
                        const updatedNote = { ...note };
                        if (updatedNote.animationState === 'idle') {
                            updatedNote.x -= (noteSpeed * deltaTime) / 1000;
                        }
                        if (
                            updatedNote.animationState === 'idle' &&
                            updatedNote.x + gameAreaOffset.x < targetX.current - 15
                        ) {
                            updatedNote.animationState = 'miss';
                            updatedNote.animationTime = 0;
                            sendNoteMiss(updatedNote);
                        }
                        if (
                            updatedNote.animationState === 'hit' ||
                            updatedNote.animationState === 'miss'
                        ) {
                            updatedNote.animationTime = (updatedNote.animationTime || 0) + deltaTime;
                        }
                        return updatedNote;
                    })
                    .filter((note) => {
                        if (note.animationState === 'hit' && note.animationTime && note.animationTime > 200) {
                            return false;
                        }
                        if (note.animationState === 'miss' && note.animationTime && note.animationTime > 200) {
                            return false;
                        }
                        return note.x > -200 || note.animationState !== 'idle';
                    });
            }

            // DEV MODE: auto-simulate perfect hits.
            if (devMode) {
                const devThreshold = 10;
                for (let i = notePositionsRef.current.length - 1; i >= 0; i--) {
                    const note = notePositionsRef.current[i];
                    if (note.animationState === 'idle') {
                        const noteX = note.x + gameAreaOffset.x;
                        if (Math.abs(noteX - targetX.current) < devThreshold) {
                            debugLog("DevMode", "Simulating key press for note", {
                                id: note.id,
                                start: note.start,
                                noteX,
                                targetX: targetX.current
                            });
                            sendNoteHit(note, 0);
                            note.animationState = 'hit';
                            note.animationTime = 0;
                            if (acousticGuitarRef.current) {
                                const sampleKey = STRING_TONE_MAP[note.string];
                                acousticGuitarRef.current.triggerAttackRelease(sampleKey, "8n");
                            }
                        }
                    }
                }
            }

            // Drawing on the canvas.
            const canvas = canvasRef.current;
            if (canvas) {
                const ctx = canvas.getContext('2d');
                if (ctx) {
                    ctx.clearRect(0, 0, dimensions.width, dimensions.height);

                    if (gameState.mode === 'problem') {
                        // Golden background when in problem mode.
                        ctx.fillStyle = 'rgba(255,215,0,0.5)';
                        ctx.fillRect(
                            gameAreaOffset.x - 10,
                            gameAreaOffset.y,
                            gameAreaWidth + 10,
                            gameAreaHeight
                        );
                        // Highlight pressed keys by overlaying white on the corresponding row.
                        pressedKeysRef.current.forEach((str) => {
                            const rowIndex = stringsOrder.indexOf(str);
                            const rowHeightForNotes = gameAreaHeight / stringsOrder.length;
                            const y = gameAreaOffset.y + rowIndex * rowHeightForNotes;
                            ctx.fillStyle = 'rgba(255,255,255,0.3)';
                            ctx.fillRect(gameAreaOffset.x - 10, y, gameAreaWidth + 10, rowHeightForNotes);
                        });
                    } else {
                        // Normal background.
                        ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
                        ctx.fillRect(
                            gameAreaOffset.x - 10,
                            gameAreaOffset.y,
                            gameAreaWidth + 10,
                            gameAreaHeight
                        );
                    }

                    // Draw the target line (used in normal mode).
                    ctx.beginPath();
                    ctx.moveTo(targetX.current, gameAreaOffset.y);
                    ctx.lineTo(targetX.current, gameAreaOffset.y + gameAreaHeight);
                    ctx.strokeStyle = gameState.mode === 'problem' ? '#ffd700' : '#00ff88';
                    ctx.lineWidth = 2;
                    ctx.shadowColor = gameState.mode === 'problem' ? '#ffd700' : '#00ff88';
                    ctx.shadowBlur = 10;
                    ctx.stroke();

                    if (gameState.mode === 'problem' && gameState.problemNotes.length > 0) {
                        gameState.problemNotes.forEach((note) => {
                            const rowIndex = stringsOrder.indexOf(note.string);
                            const rowHeightForNotes = gameAreaHeight / stringsOrder.length;
                            const y = gameAreaOffset.y + rowIndex * rowHeightForNotes + rowHeightForNotes / 2;
                            ctx.beginPath();
                            ctx.arc(targetX.current, y, 8, 0, 2 * Math.PI);
                            ctx.fillStyle = '#ffd700';
                            ctx.fill();
                        });
                    }

                    // Draw the notes.
                    notePositionsRef.current.forEach((note) => {
                        const rowIndex = stringsOrder.indexOf(note.string);
                        const rowHeightForNotes = gameAreaHeight / stringsOrder.length;
                        const y = gameAreaOffset.y + rowIndex * rowHeightForNotes + rowHeightForNotes / 2;
                        const x = note.x + gameAreaOffset.x;
                        if (note.animationState === 'hit') {
                            const progress = (note.animationTime || 0) / 200;
                            const maxScale = 1.3;
                            const scale = 1 + (maxScale - 1) * (1 - progress);
                            ctx.save();
                            ctx.translate(x, y);
                            ctx.scale(scale, scale);
                            const alpha = 1 - progress;
                            ctx.beginPath();
                            ctx.arc(0, 0, 10, 0, Math.PI * 2);
                            ctx.fillStyle = `rgba(255, 215, 0, ${alpha})`;
                            ctx.shadowColor = 'rgba(255, 215, 0, 1)';
                            ctx.shadowBlur = 15;
                            ctx.fill();
                            ctx.restore();
                        } else if (note.animationState === 'miss') {
                            const progress = (note.animationTime || 0) / 200;
                            ctx.save();
                            ctx.translate(x, y);
                            const alpha = 1 - progress;
                            ctx.beginPath();
                            ctx.arc(0, 0, 10, 0, Math.PI * 2);
                            ctx.fillStyle = `rgba(255, 0, 0, ${alpha})`;
                            ctx.shadowColor = 'rgba(255, 0, 0, 1)';
                            ctx.shadowBlur = 15;
                            ctx.fill();
                            ctx.restore();
                        } else {
                            ctx.beginPath();
                            ctx.arc(x, y, 15, 0, Math.PI * 2);
                            ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
                            ctx.fill();
                            ctx.beginPath();
                            ctx.arc(x, y, 10, 0, Math.PI * 2);
                            ctx.fillStyle = '#00ff88';
                            ctx.shadowColor = '#00ff88';
                            ctx.shadowBlur = 15;
                            ctx.fill();
                        }
                    });

                    // Draw game area border.
                    ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
                    ctx.lineWidth = 2;
                    ctx.strokeRect(
                        gameAreaOffset.x - 10,
                        gameAreaOffset.y,
                        gameAreaWidth + 10,
                        gameAreaHeight
                    );
                }
            }

            // --- AUTO-END LOGIC ---
            // Only consider notes that are still idle (i.e. not hit or missed)
            const idleNotes = notePositionsRef.current.filter(note => note.animationState === "idle");
            if (gameState.isStarted && gameState.mode === 'game') {
                if (idleNotes.length === 0 && endGameTimerRef.current === null) {
                    endGameTimerRef.current = window.setTimeout(() => {
                        if (wsRef.current?.readyState === WebSocket.OPEN) {
                            wsRef.current.send(JSON.stringify({
                                type: MessageType.END_GAME,
                                payload: {}
                            }));
                        }
                    }, 3500); // 3.5 seconds delay after the last idle note
                } else if (idleNotes.length > 0 && endGameTimerRef.current !== null) {
                    clearTimeout(endGameTimerRef.current);
                    endGameTimerRef.current = null;
                }
            }
            // --- END AUTO-END LOGIC ---
            if (!isPaused) {
                animationFrameRef.current = requestAnimationFrame(animate);
            }
        } catch (error) {
            console.error("Animation loop error:", error);
            if (!isPaused) {
                animationFrameRef.current = requestAnimationFrame(animate);
            }
        }
    };

    // Pause and resume functions.
    const pauseGame = () => {
        setIsPaused(true);
        if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current);
        }
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                type: MessageType.PAUSE_GAME,
                payload: { pausedAt: Date.now() }
            }));
        }
    };

    const resumeGame = () => {
        if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current);
            animationFrameRef.current = undefined;
        }
        lastTimeRef.current = 0;
        setIsPaused(false);
        requestAnimationFrame((timestamp) => {
            lastTimeRef.current = timestamp;
            animate(timestamp);
        });
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                type: MessageType.RESUME_GAME,
                payload: { resumedAt: Date.now() }
            }));
        }
    };

    // Start game handler.
    const handleStartGame = () => {
        debugLog('Game', 'Starting game');
        const positionedNotes = gameState.detectedNotes.map((note) => ({
            ...note,
            x: gameAreaWidth + note.start * noteSpeed,
            animationState: 'idle',
            animationTime: 0
        }));
        notePositionsRef.current = positionedNotes;
        setGameState((prev) => ({
            ...prev,
            isStarted: true,
            mode: 'game',
            currentNotes: positionedNotes,
        }));
        lastTimeRef.current = performance.now();
        animationFrameRef.current = requestAnimationFrame(animate);
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                type: MessageType.SESSION_STATE,
                payload: {
                    is_active: true,
                    current_notes: gameState.detectedNotes,
                    mode: 'game',
                    current_score: 0,
                    riff_count: 0,
                    start_time: new Date().toISOString(),
                    difficulty_level: 'medium',
                },
            }));
        }
    };

    // Key press handler (keydown and keyup).
    useEffect(() => {
        const handleKeyPress = (event: KeyboardEvent) => {
            if (gameState.mode !== 'game' && gameState.mode !== 'problem') return;
            const pressedString = Object.entries(STRING_KEY_MAP).find(
                ([, key]) => key === event.key
            )?.[0] as "E" | "A" | "D" | "G" | "B" | "e" | undefined;
            if (!pressedString) return;
            debugLog('Input', 'Key pressed', { key: event.key, string: pressedString });
            if (gameState.mode === 'problem') {
                pressedKeysRef.current.add(pressedString);
            }
            const hitThreshold = 50;
            const noteIndex = notePositionsRef.current.findIndex(
                (note) =>
                    note.animationState === 'idle' &&
                    note.string === pressedString &&
                    Math.abs(note.x + gameAreaOffset.x - targetX.current) < hitThreshold
            );
            if (noteIndex !== -1) {
                const hitNote = notePositionsRef.current[noteIndex];
                const accuracy = (hitNote.x + gameAreaOffset.x - targetX.current) / hitThreshold;
                sendNoteHit(hitNote, accuracy);
                hitNote.animationState = 'hit';
                hitNote.animationTime = 0;
                if (acousticGuitarRef.current) {
                    const sampleKey = STRING_TONE_MAP[hitNote.string];
                    acousticGuitarRef.current.triggerAttackRelease(sampleKey, "8n");
                }
                setDebugInfo((prev) => ({ ...prev, lastProcessedNote: hitNote }));
                setGameState((prev) => ({ ...prev }));
            }
        };

        const handleKeyUp = (event: KeyboardEvent) => {
            const releasedString = Object.entries(STRING_KEY_MAP).find(
                ([, key]) => key === event.key
            )?.[0] as "E" | "A" | "D" | "G" | "B" | "e" | undefined;
            if (releasedString && gameState.mode === 'problem') {
                pressedKeysRef.current.delete(releasedString);
            }
        };

        window.addEventListener('keydown', handleKeyPress);
        window.addEventListener('keyup', handleKeyUp);
        return () => {
            window.removeEventListener('keydown', handleKeyPress);
            window.removeEventListener('keyup', handleKeyUp);
        };
    }, [gameState.mode, gameAreaOffset.x]);

    // Cleanup on unmount.
    useEffect(() => {
        return () => {
            if (animationFrameRef.current) {
                cancelAnimationFrame(animationFrameRef.current);
            }
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, []);

    useEffect(() => {
        debugLog('State', 'Score/Combo updated', {
            score: gameState.score,
            combo: gameState.combo
        });
    }, [gameState.score, gameState.combo]);

    useEffect(() => {
        debugLog('WebSocket', 'Status changed', {
            status: debugInfo.wsStatus,
            timestamp: new Date().toISOString()
        });
    }, [debugInfo.wsStatus]);

    useEffect(() => {
        debugLog('Message', 'Last message updated', {
            message: debugInfo.lastMessage,
            timestamp: new Date().toISOString()
        });
    }, [debugInfo.lastMessage]);

    return (
        <Box
            sx={{
                width: '100vw',
                height: '100vh',
                margin: '0 auto',
                padding: 0,
                position: 'relative',
                overflow: 'hidden',
                background: 'linear-gradient(-45deg, #1a1a2e, #16213e, #0f3460)',
                animation: `${gradientAnimation} 15s ease infinite`,
                backgroundSize: '400% 400%',
                maxHeight: '95vh',
                maxWidth: '100vw',
                '&::before': {
                    content: '""',
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: 'radial-gradient(circle, transparent 60%, rgba(0,0,0,0.7))',
                    zIndex: 0,
                },
            }}
        >
            {/* Final Session Metrics Overlay */}
            {gameState.mode === 'finished' && gameState.finalMetrics && (
                <Box
                    sx={{
                        position: 'absolute',
                        top: '50%',
                        left: '50%',
                        transform: 'translate(-50%, -50%)',
                        background: 'rgba(0,0,0,0.8)',
                        color: '#ffd700',
                        padding: '20px 40px',
                        borderRadius: '8px',
                        zIndex: 2000,
                        textAlign: 'center',
                    }}
                >
                    <Typography variant="h3">Game Over!</Typography>
                    <Typography variant="h4">
                        Final Score: {gameState.finalMetrics.final_score}
                    </Typography>
                    <Typography variant="h5">
                        Final Combo: {gameState.finalMetrics.final_combo}x
                    </Typography>
                    <Typography variant="body1">
                        Total Notes: {gameState.finalMetrics.total_notes}
                    </Typography>
                    <Typography variant="body1">
                        Time Played: {Math.round(gameState.finalMetrics.time_played)} seconds
                    </Typography>
                    <Button
                        variant="contained"
                        onClick={() => {
                        }}
                        sx={{
                            marginTop: '16px',
                            background: 'linear-gradient(45deg, #00b4ff, #00ff88)',
                            '&:hover': { transform: 'scale(1.05)' },
                        }}
                    >
                        Play Again
                    </Button>
                </Box>
            )}

            {/* Problem Warning Overlay */}
            {problemWarning && (
                <Box
                    sx={{
                        position: 'absolute',
                        top: '40%',
                        left: '50%',
                        transform: 'translate(-50%, -50%)',
                        background: 'rgba(0,0,0,0.8)',
                        color: '#ffd700',
                        padding: '20px 40px',
                        borderRadius: '8px',
                        zIndex: 2000,
                        fontSize: '2rem',
                        fontFamily: '"Audiowide", cursive',
                        boxShadow: '0 0 20px rgba(255,215,0,0.8)',
                    }}
                >
                    Problem Incoming!
                </Box>
            )}

            {/* Debug Overlay */}
            <Box
                sx={{
                    position: 'absolute',
                    top: 16,
                    right: 16,
                    bgcolor: 'rgba(0,0,0,0.7)',
                    color: '#00ff88',
                    p: 2,
                    borderRadius: '8px',
                    zIndex: 1000,
                    fontFamily: '"JetBrains Mono", monospace',
                    fontSize: '0.8rem',
                    backdropFilter: 'blur(4px)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                }}
            >
                <Typography variant="body2" sx={{ color: '#7df2ff' }}>
                    STATUS: {debugInfo.wsStatus.toUpperCase()}
                </Typography>
                <Typography variant="body2">MODE: {gameState.mode}</Typography>
                <Typography variant="body2">NOTES: {notePositionsRef.current.length}</Typography>
                <Typography variant="body2" sx={{ color: '#ffd700' }}>
                    SCORE: {Math.round(gameState.score)}
                </Typography>
                <Typography variant="body2" sx={{ color: '#ff7d7d' }}>
                    COMBO: {Math.round(gameState.combo)}x
                </Typography>
                <Typography variant="body2">FPS: {debugInfo.fps}</Typography>
            </Box>

            {/* Menu Mode */}
            {gameState.mode === 'menu' && (
                <Box
                    sx={{
                        position: 'absolute',
                        width: '100vw',
                        height: '100vh',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 4,
                        zIndex: 1,
                    }}
                >
                    <Typography
                        variant="h1"
                        sx={{
                            fontFamily: '"Audiowide", cursive',
                            fontSize: '4rem',
                            background: 'linear-gradient(45deg, #00ff88, #00b4ff)',
                            WebkitBackgroundClip: 'text',
                            WebkitTextFillColor: 'transparent',
                            textShadow: '0 0 20px rgba(0,255,136,0.5)',
                            mb: 4,
                        }}
                    >
                        RIFF ROULETTE
                    </Typography>
                    <Button
                        variant="contained"
                        onClick={() =>
                            setGameState((prev) => ({ ...prev, mode: 'upload' }))
                        }
                        sx={{
                            background: 'linear-gradient(45deg, #00b4ff, #00ff88)',
                            fontSize: '1.2rem',
                            px: 6,
                            py: 1.5,
                            borderRadius: '12px',
                            boxShadow: '0 4px 15px rgba(0,180,255,0.4)',
                            transition: 'all 0.3s ease',
                            '&:hover': {
                                transform: 'scale(1.05)',
                                boxShadow: '0 6px 20px rgba(0,180,255,0.6)',
                            },
                        }}
                    >
                        START GAME
                    </Button>
                    <Button
                        variant="outlined"
                        onClick={() => setInstructionsOpen(true)}
                        sx={{
                            color: '#00ff88',
                            borderColor: '#00ff88',
                            '&:hover': {
                                backgroundColor: 'rgba(0,255,136,0.1)',
                                borderColor: '#00ff88',
                            },
                        }}
                    >
                        HOW TO PLAY
                    </Button>
                </Box>
            )}

            {/* Upload Mode */}
            {gameState.mode === 'upload' && (
                <Box
                    sx={{
                        width: '100vw',
                        height: '100vh',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 4,
                        zIndex: 1,
                    }}
                >
                    <Typography
                        variant="h4"
                        sx={{
                            fontFamily: '"Audiowide", cursive',
                            color: '#00ff88',
                            textShadow: '0 0 12px rgba(0,255,136,0.4)',
                        }}
                    >
                        UPLOAD YOUR RIFF OR CHOOSE A PRESET
                    </Typography>
                    <Button
                        variant="contained"
                        component="label"
                        sx={{
                            background: 'linear-gradient(45deg, #ff00ff, #00b4ff)',
                            fontSize: '1.1rem',
                            px: 6,
                            py: 1.5,
                            borderRadius: '8px',
                            boxShadow: '0 4px 15px rgba(255,0,255,0.3)',
                            transition: 'all 0.3s ease',
                            '&:hover': {
                                transform: 'scale(1.05)',
                                boxShadow: '0 6px 20px rgba(255,0,255,0.5)',
                            },
                        }}
                    >
                        CHOOSE FILE
                        <input type="file" hidden onChange={handleFileUpload} accept="audio/*" />
                    </Button>
                    <Box sx={{ width: '300px' }}>
                        <Autocomplete
                            options={availableSongs}
                            getOptionLabel={(option) => `${option.title} by ${option.artist}`}
                            onChange={(event, newValue) => handleSongSelect(newValue)}
                            loading={isLoading}
                            renderInput={(params) => (
                                <TextField
                                    {...params}
                                    variant="outlined"
                                    label="Select a song"
                                    sx={{
                                        label: { color: '#00ff88' },
                                        '& .MuiOutlinedInput-root': {
                                            color: '#fff',
                                            backgroundColor: 'rgba(255,255,255,0.1)',
                                            borderRadius: '8px',
                                            '& fieldset': {
                                                borderColor: 'rgba(255,255,255,0.3)',
                                            },
                                            '&:hover fieldset': {
                                                borderColor: '#00ff88',
                                            },
                                        },
                                        '& .MuiSvgIcon-root': {
                                            color: '#00ff88',
                                        },
                                    }}
                                    InputProps={{
                                        ...params.InputProps,
                                        endAdornment: (
                                            <>
                                                {isLoading ? (
                                                    <CircularProgress color="inherit" size={20} />
                                                ) : null}
                                                {params.InputProps.endAdornment}
                                            </>
                                        ),
                                    }}
                                />
                            )}
                        />
                    </Box>
                    {isLoading && (
                        <Typography
                            sx={{
                                color: '#00ff88',
                                mt: 2,
                                textAlign: 'center',
                            }}
                        >
                            Processing song...
                        </Typography>
                    )}
                </Box>
            )}

            {/* Waiting Mode */}
            {gameState.mode === 'waiting' && (
                <Box
                    sx={{
                        width: '100vw',
                        height: '100vh',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 4,
                        zIndex: 1,
                    }}
                >
                    <Typography
                        variant="h3"
                        sx={{
                            fontFamily: '"Audiowide", cursive',
                            color: '#00ff88',
                            textShadow: '0 0 12px rgba(0,255,136,0.4)',
                        }}
                    >
                        READY TO ROCK?
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 4 }}>
                        <Button
                            variant="contained"
                            onClick={() => {
                                devMode = false;
                                handleStartGame();
                            }}
                            sx={{
                                background: 'linear-gradient(45deg, #ff00ff, #00b4ff)',
                                fontSize: '1rem',
                                px: 6,
                                py: 1.5,
                                borderRadius: '12px',
                                boxShadow: '0 4px 20px rgba(255,0,255,0.4)',
                                transition: 'all 0.3s ease',
                                '&:hover': {
                                    transform: 'scale(1.05)',
                                    boxShadow: '0 6px 25px rgba(255,0,255,0.6)',
                                },
                            }}
                        >
                            START NORMAL
                        </Button>
                        <Button
                            variant="contained"
                            onClick={() => {
                                devMode = true;
                                handleStartGame();
                            }}
                            sx={{
                                background: 'linear-gradient(45deg, #ff00ff, #00b4ff)',
                                fontSize: '1rem',
                                px: 6,
                                py: 1.5,
                                borderRadius: '12px',
                                boxShadow: '0 4px 20px rgba(255,0,255,0.4)',
                                transition: 'all 0.3s ease',
                                '&:hover': {
                                    transform: 'scale(1.05)',
                                    boxShadow: '0 6px 25px rgba(255,0,255,0.6)',
                                },
                            }}
                        >
                            PLAY PERFECT SIMULATION
                        </Button>
                    </Box>
                </Box>
            )}

            {/* Game/Problem Mode */}
            {(gameState.mode === 'game' || gameState.mode === 'problem') && (
                <>
                    {/* Score and Pause/Resume Controls */}
                    <Box
                        sx={{
                            position: 'absolute',
                            top: 16,
                            left: 16,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 1,
                            zIndex: 1,
                        }}
                    >
                        <Typography
                            variant="h4"
                            sx={{
                                fontFamily: '"Audiowide", cursive',
                                color: '#ffd700',
                                textShadow: '0 0 12px rgba(255,215,0,0.4)',
                            }}
                        >
                            SCORE: {Math.round(gameState.score)}
                        </Typography>
                        <Typography
                            variant="h5"
                            sx={{
                                fontFamily: '"Audiowide", cursive',
                                color: '#ff7d7d',
                                textShadow: '0 0 12px rgba(255,125,125,0.4)',
                            }}
                        >
                            COMBO: {gameState.combo}x
                        </Typography>
                        <Button
                            variant="outlined"
                            onClick={isPaused ? resumeGame : pauseGame}
                            sx={{
                                color: '#00ff88',
                                borderColor: '#00ff88',
                                '&:hover': {
                                    backgroundColor: 'rgba(0,255,136,0.1)',
                                    borderColor: '#00ff88',
                                },
                            }}
                        >
                            {isPaused ? '▶ RESUME' : '⏸ PAUSE'}
                        </Button>
                    </Box>
                    {/* Canvas Game Area */}
                    <Box
                        sx={{
                            position: 'absolute',
                            width: gameAreaWidth,
                            height: gameAreaHeight,
                            zIndex: 0,
                        }}
                    >
                        <canvas
                            ref={canvasRef}
                            width={dimensions.width}
                            height={dimensions.height}
                            style={{ display: 'block' }}
                        />
                    </Box>
                </>
            )}

            {/* Instructions Dialog */}
            <Dialog
                open={instructionsOpen}
                onClose={() => setInstructionsOpen(false)}
                PaperProps={{
                    sx: {
                        background: 'linear-gradient(45deg, #1a1a2e, #16213e)',
                        borderRadius: '16px',
                        border: '1px solid rgba(255,255,255,0.1)',
                        boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
                    },
                }}
            >
                <DialogTitle
                    sx={{
                        fontFamily: '"Audiowide", cursive',
                        color: '#00ff88',
                        borderBottom: '1px solid rgba(255,255,255,0.1)',
                    }}
                >
                    HOW TO PLAY
                </DialogTitle>
                <DialogContent>
                    <DialogContentText
                        sx={{
                            color: '#a0a0a0',
                            lineHeight: 1.8,
                            '& strong': {
                                color: '#00b4ff',
                            },
                        }}
                    >
                        <strong>1. Upload</strong> your audio file or choose a preset to start<br />
                        <strong>2. Notes</strong> move from right to left<br />
                        <strong>3. Press keys</strong> when notes reach the glowing line:<br />
                        &nbsp;&nbsp;🎸 <strong>Q:</strong> Low E&nbsp;&nbsp;| 🎸 <strong>W:</strong> A<br />
                        &nbsp;&nbsp;🎸 <strong>E:</strong> D&nbsp;&nbsp;| 🎸 <strong>R:</strong> G<br />
                        &nbsp;&nbsp;🎸 <strong>T:</strong> B&nbsp;&nbsp;| 🎸 <strong>Y:</strong> High E<br />
                        <strong>4. Combos</strong> boost your score multiplier<br />
                        <strong>5. Pause</strong> anytime with the Pause button<br />
                        <strong>6. Perfect Simulation</strong> mode will auto-play perfectly
                    </DialogContentText>
                </DialogContent>
                <DialogActions
                    sx={{
                        borderTop: '1px solid rgba(255,255,255,0.1)',
                        padding: '16px',
                    }}
                >
                    <Button
                        onClick={() => setInstructionsOpen(false)}
                        sx={{
                            color: '#00ff88',
                            '&:hover': {
                                backgroundColor: 'rgba(0,255,136,0.1)',
                            },
                        }}
                    >
                        GOT IT!
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};
export default PlaygroundGame;
