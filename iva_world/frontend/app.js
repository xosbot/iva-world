/**
 * IVA-World Frontend Application
 * WebSocket listener and 2D canvas rendering for agent visualization
 */

// Configuration
const CONFIG = {
    GRID_SIZE: 20,
    CELL_SIZE: 40, // 800px / 20 = 40px per cell
    WS_URL: `ws://${window.location.hostname}:8000/ws`,
    UPDATE_INTERVAL: 500, // 500ms = 0.5 seconds
};

// Agent definitions with colors and metadata
const AGENTS = {
    'IVA': { 
        color: '#FFB6C1', 
        role: 'Orchestrator', 
        avatar: 'White Persian',
        defaultX: 10,
        defaultY: 2
    },
    'LUNA': { 
        color: '#E8D5C4', 
        role: 'Market Research', 
        avatar: 'Siamese',
        defaultX: 3,
        defaultY: 10
    },
    'ARCHIE': { 
        color: '#D2B48C', 
        role: 'Software Engineering', 
        avatar: 'Tabby',
        defaultX: 17,
        defaultY: 10
    },
    'BYTE': { 
        color: '#2C2C2C', 
        role: 'Code Writer', 
        avatar: 'Black Cat',
        defaultX: 15,
        defaultY: 15
    },
    'PIXEL': { 
        color: '#FFA07A', 
        role: 'UI/UX Designer', 
        avatar: 'Calico',
        defaultX: 17,
        defaultY: 15
    },
    'GUARDIAN': { 
        color: '#DDA0DD', 
        role: 'Security & QA', 
        avatar: 'Sphynx',
        defaultX: 15,
        defaultY: 17
    }
};

// Zone definitions (special coordinates on the grid)
const ZONES = {
    'IVA_DESK': { x: 10, y: 2, label: "IVA's Desk", color: 'rgba(255, 182, 193, 0.3)' },
    'MEETING_RUG': { x: 10, y: 10, label: 'Meeting Rug', color: 'rgba(255, 215, 0, 0.3)' },
    'RESEARCH_LAB': { x: 3, y: 10, label: 'Research Lab', color: 'rgba(135, 206, 235, 0.3)' },
    'CODE_FORGE': { x: 17, y: 10, label: 'Code Forge', color: 'rgba(255, 160, 122, 0.3)' },
    'DESIGN_STUDIO': { x: 15, y: 15, label: 'Design Studio', color: 'rgba(255, 182, 193, 0.3)' },
    'QA_LAB': { x: 5, y: 15, label: 'QA Lab', color: 'rgba(221, 160, 221, 0.3)' },
    'BED_ROOM': { x: 10, y: 18, label: 'Bed Room', color: 'rgba(144, 238, 144, 0.3)' }
};

// Global state
let ws = null;
let agentStates = {};
let connectionStatus = 'disconnected';

// Canvas setup
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

/**
 * Initialize WebSocket connection
 */
function initWebSocket() {
    updateConnectionStatus('connecting');
    
    ws = new WebSocket(CONFIG.WS_URL);
    
    ws.onopen = () => {
        console.log('✅ Connected to IVA-World server');
        updateConnectionStatus('connected');
    };
    
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleAgentStateUpdate(data);
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    };
    
    ws.onclose = () => {
        console.log('❌ Disconnected from server');
        updateConnectionStatus('disconnected');
        // Attempt reconnection after 3 seconds
        setTimeout(initWebSocket, 3000);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateConnectionStatus('disconnected');
    };
}

/**
 * Handle incoming agent state updates
 */
function handleAgentStateUpdate(data) {
    if (data.states && Array.isArray(data.states)) {
        data.states.forEach(state => {
            const agentKey = getAgentKey(state.agent_type);
            if (agentKey) {
                agentStates[agentKey] = {
                    ...state,
                    targetX: state.grid_x,
                    targetY: state.grid_y,
                    currentX: agentStates[agentKey]?.currentX || state.grid_x,
                    currentY: agentStates[agentKey]?.currentY || state.grid_y
                };
            }
        });
        updateStatusPanel();
    }
}

/**
 * Convert agent type number to agent key
 */
function getAgentKey(agentType) {
    const mapping = {
        1: 'IVA',
        2: 'LUNA',
        3: 'ARCHIE',
        4: 'BYTE',
        5: 'PIXEL',
        6: 'GUARDIAN'
    };
    return mapping[agentType] || null;
}

/**
 * Update connection status UI
 */
function updateConnectionStatus(status) {
    connectionStatus = status;
    const statusEl = document.getElementById('connectionStatus');
    statusEl.className = `connection-status ${status}`;
    
    const messages = {
        'connected': '🟢 Connected to IVA-World',
        'disconnected': '🔴 Disconnected - Reconnecting...',
        'connecting': '🟡 Connecting...'
    };
    statusEl.textContent = messages[status];
}

/**
 * Update the status panel with current agent states
 */
function updateStatusPanel() {
    const container = document.getElementById('agentStatusList');
    container.innerHTML = '';
    
    Object.keys(AGENTS).forEach(agentKey => {
        const agent = AGENTS[agentKey];
        const state = agentStates[agentKey];
        
        const statusClass = getStateClass(state?.status || 1);
        const statusText = getStatusText(state?.status || 1);
        
        const div = document.createElement('div');
        div.className = 'agent-status';
        div.innerHTML = `
            <div class="agent-name">
                <span class="agent-avatar" style="background: ${agent.color}"></span>
                ${agentKey} (${agent.role})
            </div>
            <span class="agent-state ${statusClass}">${statusText}</span>
        `;
        container.appendChild(div);
    });
}

/**
 * Get CSS class for agent status
 */
function getStateClass(status) {
    const mapping = {
        1: 'state-idle',
        2: 'state-thinking',
        3: 'state-communicating',
        4: 'state-using-tool'
    };
    return mapping[status] || 'state-idle';
}

/**
 * Get human-readable status text
 */
function getStatusText(status) {
    const mapping = {
        1: 'Idle',
        2: 'Thinking',
        3: 'Communicating',
        4: 'Using Tool'
    };
    return mapping[status] || 'Unknown';
}

/**
 * Interpolate agent position for smooth animation
 */
function interpolatePosition(agent, deltaTime) {
    if (!agent) return;
    
    const speed = 0.1; // Animation speed
    
    if (Math.abs(agent.currentX - agent.targetX) > 0.1) {
        agent.currentX += (agent.targetX - agent.currentX) * speed;
    }
    if (Math.abs(agent.currentY - agent.targetY) > 0.1) {
        agent.currentY += (agent.targetY - agent.currentY) * speed;
    }
}

/**
 * Draw the grid background
 */
function drawGrid() {
    ctx.strokeStyle = '#ddd';
    ctx.lineWidth = 1;
    
    for (let i = 0; i <= CONFIG.GRID_SIZE; i++) {
        // Vertical lines
        ctx.beginPath();
        ctx.moveTo(i * CONFIG.CELL_SIZE, 0);
        ctx.lineTo(i * CONFIG.CELL_SIZE, CONFIG.GRID_SIZE * CONFIG.CELL_SIZE);
        ctx.stroke();
        
        // Horizontal lines
        ctx.beginPath();
        ctx.moveTo(0, i * CONFIG.CELL_SIZE);
        ctx.lineTo(CONFIG.GRID_SIZE * CONFIG.CELL_SIZE, i * CONFIG.CELL_SIZE);
        ctx.stroke();
    }
}

/**
 * Draw zone markers
 */
function drawZones() {
    Object.values(ZONES).forEach(zone => {
        const x = zone.x * CONFIG.CELL_SIZE;
        const y = zone.y * CONFIG.CELL_SIZE;
        
        // Draw zone background
        ctx.fillStyle = zone.color;
        ctx.fillRect(x, y, CONFIG.CELL_SIZE * 2, CONFIG.CELL_SIZE);
        
        // Draw zone label
        ctx.fillStyle = '#666';
        ctx.font = '10px Arial';
        ctx.textAlign = 'center';
        ctx.fillText(zone.label, x + CONFIG.CELL_SIZE, y + CONFIG.CELL_SIZE / 2 + 4);
    });
}

/**
 * Draw an agent on the canvas
 */
function drawAgent(agentKey, state) {
    const config = AGENTS[agentKey];
    const x = state.currentX * CONFIG.CELL_SIZE + CONFIG.CELL_SIZE / 2;
    const y = state.currentY * CONFIG.CELL_SIZE + CONFIG.CELL_SIZE / 2;
    const radius = CONFIG.CELL_SIZE / 2 - 4;
    
    // Draw agent body (circle)
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fillStyle = config.color;
    ctx.fill();
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 2;
    ctx.stroke();
    
    // Draw cat ears
    const earSize = radius * 0.4;
    const earOffset = radius * 0.6;
    
    // Left ear
    ctx.beginPath();
    ctx.moveTo(x - earOffset, y - radius + 4);
    ctx.lineTo(x - earOffset - earSize / 2, y - radius - earSize + 4);
    ctx.lineTo(x - earOffset + earSize / 2, y - radius + 4);
    ctx.fillStyle = config.color;
    ctx.fill();
    ctx.stroke();
    
    // Right ear
    ctx.beginPath();
    ctx.moveTo(x + earOffset, y - radius + 4);
    ctx.lineTo(x + earOffset - earSize / 2, y - radius - earSize + 4);
    ctx.lineTo(x + earOffset + earSize / 2, y - radius + 4);
    ctx.fillStyle = config.color;
    ctx.fill();
    ctx.stroke();
    
    // Draw eyes
    ctx.fillStyle = '#000';
    ctx.beginPath();
    ctx.arc(x - 6, y - 2, 3, 0, Math.PI * 2);
    ctx.arc(x + 6, y - 2, 3, 0, Math.PI * 2);
    ctx.fill();
    
    // Draw speech bubble if communicating
    if (state.status === 3 && state.speech_bubble) {
        drawSpeechBubble(x, y - radius - 10, state.speech_bubble);
    }
    
    // Draw thought bubble if thinking
    if (state.status === 2) {
        drawThoughtBubble(x, y - radius - 10);
    }
    
    // Draw Zzz if idle
    if (state.status === 1) {
        drawZzz(x + radius + 5, y - 10);
    }
    
    // Draw agent name below
    ctx.fillStyle = '#333';
    ctx.font = 'bold 10px Arial';
    ctx.textAlign = 'center';
    ctx.fillText(agentKey, x, y + radius + 12);
}

/**
 * Draw a speech bubble with text
 */
function drawSpeechBubble(x, y, text) {
    const padding = 8;
    ctx.font = '11px Arial';
    const textWidth = ctx.measureText(text).width;
    const bubbleWidth = textWidth + padding * 2;
    const bubbleHeight = 30;
    
    const bubbleX = x - bubbleWidth / 2;
    const bubbleY = y - bubbleHeight;
    
    // Draw bubble
    ctx.fillStyle = 'rgba(255, 255, 255, 0.95)';
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    
    ctx.beginPath();
    ctx.roundRect(bubbleX, bubbleY, bubbleWidth, bubbleHeight, 5);
    ctx.fill();
    ctx.stroke();
    
    // Draw tail
    ctx.beginPath();
    ctx.moveTo(x, bubbleY + bubbleHeight);
    ctx.lineTo(x - 5, bubbleY + bubbleHeight + 8);
    ctx.lineTo(x + 5, bubbleY + bubbleHeight);
    ctx.fill();
    ctx.stroke();
    
    // Draw text
    ctx.fillStyle = '#333';
    ctx.textAlign = 'center';
    ctx.fillText(text.substring(0, 20) + (text.length > 20 ? '...' : ''), x, bubbleY + 18);
}

/**
 * Draw a thought bubble
 */
function drawThoughtBubble(x, y) {
    ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
    ctx.strokeStyle = '#999';
    ctx.lineWidth = 1;
    
    // Draw small circles leading up
    for (let i = 0; i < 3; i++) {
        const size = 4 + i * 2;
        ctx.beginPath();
        ctx.arc(x - 10 + i * 8, y + 15 + i * 5, size, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
    }
    
    // Draw main bubble
    ctx.beginPath();
    ctx.arc(x, y, 15, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    
    // Draw question mark or dots
    ctx.fillStyle = '#666';
    ctx.font = '14px Arial';
    ctx.textAlign = 'center';
    ctx.fillText('?', x, y + 5);
}

/**
 * Draw Zzz animation for sleeping agents
 */
function drawZzz(x, y) {
    const time = Date.now() / 1000;
    const offset = Math.sin(time * 3) * 5;
    
    ctx.fillStyle = '#666';
    ctx.font = 'bold 14px Arial';
    ctx.textAlign = 'left';
    
    for (let i = 0; i < 3; i++) {
        const size = 14 - i * 3;
        ctx.font = `bold ${size}px Arial`;
        ctx.fillText('Z', x + i * 10, y - offset - i * 8);
    }
}

/**
 * Main render loop
 */
let lastTime = 0;
function render(timestamp) {
    const deltaTime = timestamp - lastTime;
    lastTime = timestamp;
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw background elements
    drawGrid();
    drawZones();
    
    // Update and draw all agents
    Object.keys(agentStates).forEach(agentKey => {
        const state = agentStates[agentKey];
        interpolatePosition(state, deltaTime);
        drawAgent(agentKey, state);
    });
    
    requestAnimationFrame(render);
}

/**
 * Initialize the application
 */
function init() {
    console.log('🚀 Initializing IVA-World Frontend...');
    
    // Initialize WebSocket connection
    initWebSocket();
    
    // Initialize default agent positions
    Object.keys(AGENTS).forEach(agentKey => {
        const agent = AGENTS[agentKey];
        agentStates[agentKey] = {
            agent_id: agentKey,
            agent_type: Object.keys(AGENTS).indexOf(agentKey) + 1,
            status: 1, // IDLE
            grid_x: agent.defaultX,
            grid_y: agent.defaultY,
            currentX: agent.defaultX,
            currentY: agent.defaultY,
            current_activity: 'Waiting for tasks',
            speech_bubble: ''
        };
    });
    
    // Start render loop
    requestAnimationFrame(render);
    
    console.log('✅ IVA-World Frontend initialized');
}

// Start the application when DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
