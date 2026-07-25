"""
IVA-World Master Bootup Script
Starts gRPC server, FastAPI server with WebSocket, and initializes IVA orchestrator.
"""

import asyncio
import argparse
import signal
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


class IVASystem:
    """Main system coordinator for IVA-World."""
    
    def __init__(self, grpc_host: str = "localhost", grpc_port: int = 50051, 
                 api_host: str = "0.0.0.0", api_port: int = 8000,
                 sandbox_dir: str = "./sandbox"):
        self.grpc_host = grpc_host
        self.grpc_port = grpc_port
        self.api_host = api_host
        self.api_port = api_port
        self.sandbox_dir = sandbox_dir
        
        self.grpc_server = None
        self.api_server_task = None
        self.running = False
        
        # Import components
        from communication.grpc_server import GRPCServer
        from simulation.engine import get_simulation_engine
        from core.orchestrator import get_iva_instance
        from core.agent_factory import get_agent_factory
        
        self.GRPCServer = GRPCServer
        self.engine = get_simulation_engine(sandbox_dir)
        self.iva = get_iva_instance(sandbox_dir=sandbox_dir)
        self.agent_factory = get_agent_factory(sandbox_dir=sandbox_dir)
    
    async def start(self):
        """Start all system components."""
        print("=" * 60)
        print("IVA-World System Starting...")
        print("=" * 60)
        
        self.running = True
        
        # Start gRPC server
        print(f"\n[1/3] Starting gRPC server on {self.grpc_host}:{self.grpc_port}")
        grpc_server_instance = self.GRPCServer(self.grpc_host, self.grpc_port)
        self.grpc_server = await grpc_server_instance.start()
        
        # Connect IVA to gRPC channel
        import grpc
        grpc_channel = grpc.aio.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
        self.iva.grpc_channel = grpc_channel
        self.iva.grpc_stub = None  # Will be created when needed
        
        # Register state callback for IVA
        from simulation.engine import get_simulation_engine
        engine = get_simulation_engine()
        
        async def iva_state_callback(state_data):
            """Broadcast IVA state changes."""
            # Update simulation engine with IVA state
            engine.update_agent_status(
                "iva_001",
                state_data.get("status", "IDLE"),
                state_data.get("message", "")
            )
        
        self.iva.set_state_callback(iva_state_callback)
        
        # Register agent factory callbacks
        def broadcast_agent_state(state_data):
            """Register callback for all agents."""
            pass
        
        self.agent_factory.register_state_callback(broadcast_agent_state)
        
        print("[2/3] IVA Orchestrator initialized")
        print("[2/3] Agent Factory initialized with Luna, Archie, Byte, Pixel, Guardian")
        
        # Start FastAPI server in background
        print(f"\n[3/3] Starting FastAPI server on {self.api_host}:{self.api_port}")
        self.api_server_task = asyncio.create_task(
            self._run_api_server()
        )
        
        print("\n" + "=" * 60)
        print("IVA-World System Ready!")
        print("=" * 60)
        print(f"\nFrontend: http://localhost:{self.api_port}")
        print(f"WebSocket: ws://localhost:{self.api_port}/ws")
        print(f"gRPC: {self.grpc_host}:{self.grpc_port}")
        print(f"Sandbox: {Path(self.sandbox_dir).resolve()}")
        print("\nPress Ctrl+C to stop the system\n")
    
    async def _run_api_server(self):
        """Run the FastAPI server."""
        import uvicorn
        from simulation.server import app
        
        config = uvicorn.Config(
            app,
            host=self.api_host,
            port=self.api_port,
            log_level="info",
            access_log=False
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    async def run(self):
        """Run the system until shutdown."""
        await self.start()
        
        # Wait for shutdown signal
        shutdown_event = asyncio.Event()
        
        def signal_handler():
            print("\n\nShutdown signal received...")
            self.running = False
            shutdown_event.set()
        
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)
        
        # Keep running
        while self.running:
            await asyncio.sleep(0.5)
            
            # Check if API server task is done (error)
            if self.api_server_task.done():
                exception = self.api_server_task.exception()
                if exception:
                    print(f"API server error: {exception}")
                    break
        
        await self.shutdown()
    
    async def shutdown(self):
        """Gracefully shutdown all components."""
        print("\nShutting down IVA-World...")
        
        # Stop gRPC server
        if self.grpc_server:
            await self.grpc_server.stop(grace=0.5)
            print("[✓] gRPC server stopped")
        
        # Cancel API server
        if self.api_server_task and not self.api_server_task.done():
            self.api_server_task.cancel()
            try:
                await self.api_server_task
            except asyncio.CancelledError:
                pass
            print("[✓] FastAPI server stopped")
        
        # Stop simulation engine
        self.engine.stop()
        print("[✓] Simulation engine stopped")
        
        # Close gRPC channel
        if hasattr(self.iva, 'grpc_channel') and self.iva.grpc_channel:
            await self.iva.grpc_channel.close()
        
        print("\n" + "=" * 60)
        print("IVA-World System Shutdown Complete")
        print("=" * 60)


async def run_demo():
    """Run a quick demo of the system."""
    print("Running IVA-World Demo Mode...\n")
    
    from core.orchestrator import get_iva_instance
    from simulation.engine import get_simulation_engine
    
    engine = get_simulation_engine()
    iva = get_iva_instance()
    
    # Print initial agent states
    print("Initial Agent States:")
    print("-" * 40)
    for agent in engine.get_all_states():
        print(f"  {agent['name']:10} - {agent['avatar']:15} @ ({agent['position'][0]}, {agent['position'][1]}) - {agent['status']}")
    
    # Process a sample request
    print("\n\nProcessing sample request: 'Research AI competitors and build a Python web app'")
    print("-" * 40)
    
    result = await iva.process_user_request(
        "Research AI competitors and build a Python web app with UI design"
    )
    
    print("\n" + "=" * 60)
    print(result)
    print("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="IVA-World: Multi-Agent Orchestrator with 2D Visualization"
    )
    parser.add_argument(
        "--grpc-host",
        default="localhost",
        help="gRPC server host (default: localhost)"
    )
    parser.add_argument(
        "--grpc-port",
        type=int,
        default=50051,
        help="gRPC server port (default: 50051)"
    )
    parser.add_argument(
        "--api-host",
        default="0.0.0.0",
        help="FastAPI server host (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=8000,
        help="FastAPI server port (default: 8000)"
    )
    parser.add_argument(
        "--sandbox",
        default="./sandbox",
        help="Sandbox directory for agent file operations (default: ./sandbox)"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run in demo mode (process a sample request and exit)"
    )
    
    args = parser.parse_args()
    
    if args.demo:
        asyncio.run(run_demo())
    else:
        system = IVASystem(
            grpc_host=args.grpc_host,
            grpc_port=args.grpc_port,
            api_host=args.api_host,
            api_port=args.api_port,
            sandbox_dir=args.sandbox
        )
        
        try:
            asyncio.run(system.run())
        except KeyboardInterrupt:
            print("\nInterrupted by user")
        except Exception as e:
            print(f"System error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
