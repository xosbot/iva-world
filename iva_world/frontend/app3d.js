// IVA-World 3D Visualization Engine using Three.js

class IVAWorld3D {
    constructor() {
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.agents = {};
        this.agentMeshes = {};
        this.zones = {};
        this.zoneMeshes = {};
        this.ws = null;
        this.autoRotate = false;
        this.wireframe = false;
        this.clock = new THREE.Clock();
        
        // Agent colors matching the legend
        this.agentColors = {
            'IVA': 0xffffff,      // White Persian
            'Luna': 0xf0e6d2,     // Siamese (cream)
            'Archie': 0xd4a574,   // Tabby (brown)
            'Byte': 0x2c2c2c,     // Black
            'Pixel': 0xff9500,    // Calico (orange)
            'Guardian': 0xffb6c1  // Sphynx (pink)
        };
        
        // Zone definitions for 20x20 grid mapped to 3D space
        this.zoneDefinitions = {
            'IVA_DESK': { x: 0, z: 0, label: "IVA's Desk", color: 0x667eea },
            'RESEARCH_LAB': { x: 8, z: -5, label: "Research Lab", color: 0x4ade80 },
            'CODE_FORGE': { x: -8, z: -5, label: "Code Forge", color: 0xf97316 },
            'DESIGN_STUDIO': { x: 5, z: 8, label: "Design Studio", color: 0xec4899 },
            'QA_CENTER': { x: -5, z: 8, label: "QA Center", color: 0x8b5cf6 },
            'MEETING_RUG': { x: 0, z: 5, label: "Meeting Rug", color: 0x06b6d4 },
            'LIBRARY': { x: -10, z: 0, label: "Library", color: 0x84cc16 },
            'COMPUTER_DESK': { x: 10, z: 0, label: "Computer Desk", color: 0x3b82f6 },
            'BED_ZONE': { x: 0, z: -10, label: "Rest Area", color: 0xa855f7 },
            'DEPLOYMENT_BAY': { x: 8, z: 10, label: "Deployment Bay", color: 0xef4444 }
        };
        
        this.init();
        this.connectWebSocket();
        this.animate();
    }
    
    init() {
        // Scene setup
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x1a1a2e);
        this.scene.fog = new THREE.FogExp2(0x1a1a2e, 0.02);
        
        // Camera setup
        this.camera = new THREE.PerspectiveCamera(
            75, 
            window.innerWidth / window.innerHeight, 
            0.1, 
            1000
        );
        this.camera.position.set(0, 25, 30);
        this.camera.lookAt(0, 0, 0);
        
        // Renderer setup
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        
        document.getElementById('canvas-container').appendChild(this.renderer.domElement);
        
        // Controls
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.maxPolarAngle = Math.PI / 2.2;
        
        // Lighting
        this.setupLighting();
        
        // Create world
        this.createGrid();
        this.createZones();
        this.createAgents();
        
        // Handle resize
        window.addEventListener('resize', () => this.onWindowResize(), false);
    }
    
    setupLighting() {
        // Ambient light
        const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
        this.scene.add(ambientLight);
        
        // Directional light (sun)
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(10, 20, 10);
        directionalLight.castShadow = true;
        directionalLight.shadow.mapSize.width = 2048;
        directionalLight.shadow.mapSize.height = 2048;
        this.scene.add(directionalLight);
        
        // Point lights for ambiance
        const pointLight1 = new THREE.PointLight(0x667eea, 0.5, 50);
        pointLight1.position.set(-10, 5, -10);
        this.scene.add(pointLight1);
        
        const pointLight2 = new THREE.PointLight(0xf97316, 0.5, 50);
        pointLight2.position.set(10, 5, 10);
        this.scene.add(pointLight2);
    }
    
    createGrid() {
        // Create a glowing grid floor
        const gridHelper = new THREE.GridHelper(40, 40, 0x444444, 0x222222);
        gridHelper.position.y = -0.5;
        this.scene.add(gridHelper);
        
        // Add a reflective plane below the grid
        const planeGeometry = new THREE.PlaneGeometry(40, 40);
        const planeMaterial = new THREE.MeshStandardMaterial({ 
            color: 0x0f0f1a,
            roughness: 0.1,
            metalness: 0.8
        });
        const plane = new THREE.Mesh(planeGeometry, planeMaterial);
        plane.rotation.x = -Math.PI / 2;
        plane.position.y = -0.6;
        plane.receiveShadow = true;
        this.scene.add(plane);
    }
    
    createZones() {
        Object.entries(this.zoneDefinitions).forEach(([key, zone]) => {
            // Create zone platform
            const geometry = new THREE.BoxGeometry(6, 0.5, 6);
            const material = new THREE.MeshStandardMaterial({ 
                color: zone.color,
                transparent: true,
                opacity: 0.3,
                emissive: zone.color,
                emissiveIntensity: 0.2
            });
            
            const zoneMesh = new THREE.Mesh(geometry, material);
            zoneMesh.position.set(zone.x * 1.5, -0.25, zone.z * 1.5);
            zoneMesh.castShadow = true;
            zoneMesh.receiveShadow = true;
            
            this.scene.add(zoneMesh);
            this.zoneMeshes[key] = zoneMesh;
            
            // Add zone label (using sprite)
            const label = this.createTextSprite(zone.label, { fontSize: 24, fillColor: 'white' });
            label.position.set(zone.x * 1.5, 2, zone.z * 1.5);
            this.scene.add(label);
        });
    }
    
    createAgents() {
        const agentTypes = ['IVA', 'Luna', 'Archie', 'Byte', 'Pixel', 'Guardian'];
        
        agentTypes.forEach((type, index) => {
            // Create cat-like mesh (simplified as capsule with ears)
            const agentGroup = new THREE.Group();
            
            // Body (capsule-like)
            const bodyGeometry = new THREE.CapsuleGeometry(0.8, 1.5, 4, 8);
            const bodyMaterial = new THREE.MeshStandardMaterial({ 
                color: this.agentColors[type],
                roughness: 0.3,
                metalness: 0.2
            });
            const body = new THREE.Mesh(bodyGeometry, bodyMaterial);
            body.castShadow = true;
            agentGroup.add(body);
            
            // Head
            const headGeometry = new THREE.SphereGeometry(0.6, 16, 16);
            const head = new THREE.Mesh(headGeometry, bodyMaterial);
            head.position.y = 1.2;
            head.castShadow = true;
            agentGroup.add(head);
            
            // Ears
            const earGeometry = new THREE.ConeGeometry(0.2, 0.4, 8);
            const ear1 = new THREE.Mesh(earGeometry, bodyMaterial);
            ear1.position.set(-0.3, 1.7, 0);
            ear1.rotation.z = 0.3;
            agentGroup.add(ear1);
            
            const ear2 = new THREE.Mesh(earGeometry, bodyMaterial);
            ear2.position.set(0.3, 1.7, 0);
            ear2.rotation.z = -0.3;
            agentGroup.add(ear2);
            
            // Tail
            const tailGeometry = new THREE.CylinderGeometry(0.1, 0.15, 1, 8);
            const tail = new THREE.Mesh(tailGeometry, bodyMaterial);
            tail.position.set(0, 0.5, -0.8);
            tail.rotation.x = -0.5;
            agentGroup.add(tail);
            
            // Initial position
            const startPositions = [
                { x: 0, z: 0 },      // IVA
                { x: 8, z: -5 },     // Luna
                { x: -8, z: -5 },    // Archie
                { x: 10, z: 0 },     // Byte
                { x: 5, z: 8 },      // Pixel
                { x: -5, z: 8 }      // Guardian
            ];
            
            agentGroup.position.set(
                startPositions[index].x * 1.5,
                0,
                startPositions[index].z * 1.5
            );
            
            // Add name label
            const nameLabel = this.createTextSprite(type, { fontSize: 32, fillColor: 'white', fontWeight: 'bold' });
            nameLabel.position.set(0, 2.5, 0);
            agentGroup.add(nameLabel);
            
            this.scene.add(agentGroup);
            this.agentMeshes[type] = {
                mesh: agentGroup,
                targetPosition: agentGroup.position.clone(),
                currentState: 'IDLE',
                thoughtBubble: null,
                speechBubble: null
            };
            
            this.agents[type] = {
                status: 'IDLE',
                position: { x: startPositions[index].x, y: startPositions[index].z },
                current_task: null
            };
        });
        
        this.updateAgentListUI();
    }
    
    createTextSprite(message, parameters) {
        const font = parameters.font || "Arial";
        const fontSize = parameters.fontSize || 24;
        const fillColor = parameters.fillColor || "black";
        const fontWeight = parameters.fontWeight || "normal";
        
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.width = 512;
        canvas.height = 128;
        
        context.font = `${fontWeight} ${fontSize}px ${font}`;
        context.fillStyle = fillColor;
        context.textAlign = 'center';
        context.fillText(message, 256, 64);
        
        const texture = new THREE.CanvasTexture(canvas);
        const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
        const sprite = new THREE.Sprite(material);
        sprite.scale.set(4, 1, 1);
        
        return sprite;
    }
    
    connectWebSocket() {
        const wsUrl = `ws://${window.location.host}/ws`;
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('Connected to IVA-World server');
            document.getElementById('connection-status').className = 'connected';
            document.getElementById('connection-status').textContent = 'Connected';
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleServerMessage(data);
        };
        
        this.ws.onclose = () => {
            console.log('Disconnected from server');
            document.getElementById('connection-status').className = 'disconnected';
            document.getElementById('connection-status').textContent = 'Disconnected';
            
            // Auto-reconnect after 3 seconds
            setTimeout(() => this.connectWebSocket(), 3000);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }
    
    handleServerMessage(data) {
        if (data.type === 'agent_state') {
            this.updateAgentState(data.agent_id, data.state);
        } else if (data.type === 'agent_position') {
            this.updateAgentPosition(data.agent_id, data.x, data.y);
        } else if (data.type === 'agent_communication') {
            this.showSpeechBubble(data.from_agent, data.message);
        } else if (data.type === 'full_state') {
            this.syncFullState(data.agents);
        }
    }
    
    updateAgentState(agentId, state) {
        if (!this.agentMeshes[agentId]) return;
        
        const agentData = this.agentMeshes[agentId];
        agentData.currentState = state.status;
        
        // Update UI
        this.updateAgentListUI();
        
        // Visual feedback based on state
        switch(state.status) {
            case 'THINKING':
                this.createThoughtEffect(agentId);
                break;
            case 'USING_TOOL':
                this.highlightZoneForAgent(agentId, state.tool_location);
                break;
            case 'COMMUNICATING':
                // Will be handled by communication event
                break;
            case 'IDLE':
                this.removeEffects(agentId);
                break;
        }
        
        if (state.current_task) {
            this.showThoughtBubble(agentId, state.current_task.substring(0, 50) + '...');
        }
    }
    
    updateAgentPosition(agentId, x, y) {
        if (!this.agentMeshes[agentId]) return;
        
        const agentData = this.agentMeshes[agentId];
        agentData.targetPosition.set(x * 1.5, 0, y * 1.5);
        
        this.agents[agentId].position = { x, y };
    }
    
    syncFullState(agents) {
        Object.entries(agents).forEach(([agentId, agentData]) => {
            if (this.agentMeshes[agentId]) {
                const pos = agentData.position || { x: 0, y: 0 };
                this.updateAgentPosition(agentId, pos.x, pos.y);
                if (agentData.status) {
                    this.updateAgentState(agentId, agentData);
                }
            }
        });
    }
    
    createThoughtEffect(agentId) {
        const agentData = this.agentMeshes[agentId];
        if (!agentData) return;
        
        // Create floating particles above agent
        const particleCount = 10;
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(particleCount * 3);
        
        for (let i = 0; i < particleCount; i++) {
            positions[i * 3] = (Math.random() - 0.5) * 2;
            positions[i * 3 + 1] = 3 + Math.random() * 2;
            positions[i * 3 + 2] = (Math.random() - 0.5) * 2;
        }
        
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        
        const material = new THREE.PointsMaterial({
            color: 0xffff00,
            size: 0.2,
            transparent: true,
            opacity: 0.8
        });
        
        const particles = new THREE.Points(geometry, material);
        particles.position.copy(agentData.mesh.position);
        particles.userData.isThoughtEffect = true;
        particles.userData.createdAt = Date.now();
        
        this.scene.add(particles);
        agentData.thoughtEffect = particles;
    }
    
    highlightZoneForAgent(agentId, zoneName) {
        const zoneKey = Object.keys(this.zoneDefinitions).find(
            key => key.toLowerCase().includes(zoneName.toLowerCase())
        );
        
        if (zoneKey && this.zoneMeshes[zoneKey]) {
            const zoneMesh = this.zoneMeshes[zoneKey];
            zoneMesh.material.emissiveIntensity = 0.8;
            
            // Reset after 2 seconds
            setTimeout(() => {
                zoneMesh.material.emissiveIntensity = 0.2;
            }, 2000);
        }
    }
    
    showSpeechBubble(agentId, message) {
        const bubble = document.getElementById('speech-bubble');
        if (!this.agentMeshes[agentId]) return;
        
        bubble.textContent = message;
        bubble.style.display = 'block';
        
        // Position bubble above agent in screen coordinates
        this.updateBubblePosition(agentId, bubble);
        
        // Hide after 3 seconds
        setTimeout(() => {
            bubble.style.display = 'none';
        }, 3000);
    }
    
    showThoughtBubble(agentId, message) {
        // Similar to speech bubble but with different styling
        const bubble = document.getElementById('speech-bubble');
        if (!this.agentMeshes[agentId]) return;
        
        bubble.textContent = '💭 ' + message;
        bubble.style.display = 'block';
        bubble.style.background = '#f0f0f0';
        
        this.updateBubblePosition(agentId, bubble);
        
        setTimeout(() => {
            bubble.style.display = 'none';
            bubble.style.background = 'white';
        }, 2000);
    }
    
    updateBubblePosition(agentId, bubble) {
        const agentData = this.agentMeshes[agentId];
        if (!agentData) return;
        
        const vector = agentData.mesh.position.clone();
        vector.y += 3; // Above the agent
        
        vector.project(this.camera);
        
        const x = (vector.x * .5 + .5) * window.innerWidth;
        const y = (-(vector.y * .5) + .5) * window.innerHeight;
        
        bubble.style.left = `${x - 100}px`;
        bubble.style.top = `${y - 30}px`;
    }
    
    removeEffects(agentId) {
        const agentData = this.agentMeshes[agentId];
        if (!agentData) return;
        
        if (agentData.thoughtEffect) {
            this.scene.remove(agentData.thoughtEffect);
            agentData.thoughtEffect = null;
        }
    }
    
    updateAgentListUI() {
        const agentList = document.getElementById('agent-list');
        agentList.innerHTML = '';
        
        Object.entries(this.agents).forEach(([agentId, agentData]) => {
            const statusDiv = document.createElement('div');
            statusDiv.className = 'agent-status';
            
            const indicator = document.createElement('div');
            indicator.className = 'agent-indicator';
            
            // Color based on status
            const statusColors = {
                'IDLE': '#4ade80',
                'THINKING': '#fbbf24',
                'COMMUNICATING': '#3b82f6',
                'USING_TOOL': '#f97316'
            };
            
            indicator.style.background = statusColors[agentData.status] || '#9ca3af';
            
            const nameSpan = document.createElement('span');
            nameSpan.textContent = `${agentId}: ${agentData.status}`;
            
            statusDiv.appendChild(indicator);
            statusDiv.appendChild(nameSpan);
            agentList.appendChild(statusDiv);
        });
    }
    
    onWindowResize() {
        this.camera.aspect = window.innerWidth / window.innerHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
    }
    
    animate() {
        requestAnimationFrame(() => this.animate());
        
        const delta = this.clock.getDelta();
        const time = this.clock.getElapsedTime();
        
        // Update controls
        this.controls.update();
        
        // Smooth agent movement
        Object.values(this.agentMeshes).forEach(agentData => {
            const mesh = agentData.mesh;
            const target = agentData.targetPosition;
            
            // Interpolate position
            mesh.position.lerp(target, 0.05);
            
            // Idle animation (gentle bobbing)
            if (agentData.currentState === 'IDLE') {
                mesh.position.y = Math.sin(time * 2) * 0.1;
                mesh.rotation.y = Math.sin(time * 0.5) * 0.1;
            }
            
            // Thinking animation (slight rotation)
            if (agentData.currentState === 'THINKING') {
                mesh.rotation.y = Math.sin(time * 3) * 0.05;
            }
            
            // Animate thought effects
            if (agentData.thoughtEffect) {
                agentData.thoughtEffect.position.copy(mesh.position);
                agentData.thoughtEffect.position.y += 2;
                
                // Rotate particles
                agentData.thoughtEffect.rotation.y += delta;
                
                // Remove old effects
                if (Date.now() - agentData.thoughtEffect.userData.createdAt > 2000) {
                    this.scene.remove(agentData.thoughtEffect);
                    agentData.thoughtEffect = null;
                }
            }
        });
        
        // Auto rotate scene
        if (this.autoRotate) {
            this.scene.rotation.y += delta * 0.1;
        }
        
        this.renderer.render(this.scene, this.camera);
    }
}

// Global control functions
let world3D = null;

function init3D() {
    world3D = new IVAWorld3D();
}

function toggleAutoRotate() {
    if (world3D) {
        world3D.autoRotate = !world3D.autoRotate;
    }
}

function resetCamera() {
    if (world3D) {
        world3D.camera.position.set(0, 25, 30);
        world3D.camera.lookAt(0, 0, 0);
        world3D.scene.rotation.y = 0;
    }
}

function toggleWireframe() {
    if (world3D) {
        world3D.wireframe = !world3D.wireframe;
        Object.values(world3D.agentMeshes).forEach(agentData => {
            agentData.mesh.traverse(child => {
                if (child.material) {
                    child.material.wireframe = world3D.wireframe;
                }
            });
        });
    }
}

// Initialize when page loads
window.addEventListener('load', init3D);
