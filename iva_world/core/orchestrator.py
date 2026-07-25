"""
IVA - Intelligent Virtual Assistant (Tier 1 Orchestrator)
Primary user interface and Project Manager for the IVA-World system.
Now integrated with persistent memory for context retention.
"""

import asyncio
import json
from typing import Optional, Dict, Any, List
from enum import Enum

# Import our tools
from core.tools import ToolRegistry, ToolResult

# Import memory system
from core.memory import global_memory_manager

# Import gRPC generated code (will be available after Phase 1)
try:
    from protos.generated import agent_comms_pb2
    from protos.generated import agent_comms_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False


class AgentStatus(Enum):
    """Agent status states matching the proto definitions."""
    IDLE = "IDLE"
    THINKING = "THINKING"
    COMMUNICATING = "COMMUNICATING"
    USING_TOOL = "USING_TOOL"
    ERROR = "ERROR"


class IVA:
    """
    Intelligent Virtual Assistant - Tier 1 Orchestrator
    
    Responsibilities:
    - Receive natural language project requirements from users
    - Parse and build a DAG execution plan
    - Dispatch instructions to specialized Sub-Agents via gRPC
    - Aggregate results and report back to users
    """
    
    # Avatar configuration
    AVATAR_TYPE = "white_persian"
    DEFAULT_POSITION = (2, 2)  # IVA's desk location on the 20x20 grid
    
    def __init__(self, grpc_channel=None, sandbox_dir: str = "./sandbox"):
        self.agent_id = "iva_001"
        self.name = "IVA"
        self.role = "Orchestrator"
        self.status = AgentStatus.IDLE
        self.current_position = self.DEFAULT_POSITION
        self.target_position = self.DEFAULT_POSITION
        
        # Initialize persistent memory
        self.memory = global_memory_manager.get_memory(self.name)
        
        self.grpc_channel = grpc_channel
        self.grpc_stub = None
        if grpc_channel and GRPC_AVAILABLE:
            self.grpc_stub = agent_comms_pb2_grpc.AgentCommunicationStub(grpc_channel)
        
        self.tool_registry = ToolRegistry(sandbox_dir)
        self.active_tasks: Dict[str, Any] = {}
        self.execution_plan: List[Dict[str, Any]] = []
        
        # WebSocket callback for state broadcasting
        self.state_callback = None
    
    def set_state_callback(self, callback):
        """Set callback function for broadcasting state changes."""
        self.state_callback = callback
    
    async def _broadcast_state(self):
        """Broadcast current state to frontend via WebSocket."""
        if self.state_callback:
            state_data = {
                "agent_id": self.agent_id,
                "name": self.name,
                "avatar": self.AVATAR_TYPE,
                "status": self.status.value,
                "position": list(self.current_position),
                "target_position": list(self.target_position),
                "message": getattr(self, '_current_message', "")
            }
            await self.state_callback(state_data)
    
    async def set_status(self, status: AgentStatus, message: str = ""):
        """Update agent status and broadcast change."""
        self.status = status
        self._current_message = message
        await self._broadcast_state()
    
    async def move_to(self, x: int, y: int):
        """Move agent to a new position on the grid."""
        self.target_position = (x, y)
        await self._broadcast_state()
        
        # Simulate movement (in real implementation, this would be animated on frontend)
        steps = max(abs(x - self.current_position[0]), abs(y - self.current_position[1]))
        if steps > 0:
            dx = (x - self.current_position[0]) / steps
            dy = (y - self.current_position[1]) / steps
            
            for i in range(steps):
                self.current_position = (
                    int(self.current_position[0] + dx),
                    int(self.current_position[1] + dy)
                )
                await self._broadcast_state()
                await asyncio.sleep(0.1)
        
        self.current_position = (x, y)
        await self._broadcast_state()
    
    def parse_user_request(self, user_input: str) -> Dict[str, Any]:
        """
        Parse natural language user input into a structured execution plan.
        
        In a full implementation, this would use an LLM to understand intent
        and create a proper DAG. For now, we use simple keyword matching.
        Enhanced with memory retrieval for context-aware planning.
        """
        # Retrieve relevant past context from memory
        context_memories = self.memory.search_context(user_input, n_results=3)
        if context_memories:
            print(f"[IVA] Retrieved {len(context_memories)} relevant memories from past projects")
        
        user_input_lower = user_input.lower()
        
        execution_plan = []
        
        # Detect research tasks
        if any(word in user_input_lower for word in ["research", "search", "find", "analyze", "competitor", "market"]):
            execution_plan.append({
                "task_type": "research",
                "agent": "luna",
                "description": f"Research: {user_input}",
                "priority": 1
            })
        
        # Detect coding tasks
        if any(word in user_input_lower for word in ["code", "build", "develop", "create", "implement", "program", "write code"]):
            execution_plan.append({
                "task_type": "development",
                "agent": "archie",
                "description": f"Development: {user_input}",
                "priority": 2
            })
            
            # If specific file types mentioned, add mini-agent tasks
            if "python" in user_input_lower or ".py" in user_input_lower:
                execution_plan.append({
                    "task_type": "code_writing",
                    "agent": "byte",
                    "language": "python",
                    "parent_agent": "archie",
                    "priority": 3
                })
            
            if "ui" in user_input_lower or "design" in user_input_lower or "css" in user_input_lower:
                execution_plan.append({
                    "task_type": "ui_design",
                    "agent": "pixel",
                    "parent_agent": "archie",
                    "priority": 3
                })
        
        # Always add security check if code is being written
        if any(task.get("task_type") in ["code_writing", "development"] for task in execution_plan):
            execution_plan.append({
                "task_type": "security_qa",
                "agent": "guardian",
                "description": "Security and QA review",
                "priority": 4
            })
        
        # Default: if no specific tasks detected, create a general research task
        if not execution_plan:
            execution_plan.append({
                "task_type": "general",
                "agent": "luna",
                "description": f"Process: {user_input}",
                "priority": 1
            })
        
        # Sort by priority
        execution_plan.sort(key=lambda x: x.get("priority", 99))
        
        return {
            "original_request": user_input,
            "execution_plan": execution_plan,
            "timestamp": asyncio.get_event_loop().time()
        }
    
    async def execute_plan(self, execution_plan: Dict[str, Any]):
        """Execute the generated DAG execution plan."""
        self.execution_plan = execution_plan.get("execution_plan", [])
        
        await self.set_status(AgentStatus.THINKING, "Analyzing project requirements...")
        await self.move_to(2, 2)  # Move to IVA's desk
        
        results = []
        
        for task in self.execution_plan:
            await self.set_status(AgentStatus.COMMUNICATING, f"Dispatching task to {task['agent']}...")
            
            # Move to meeting area for communication
            await self.move_to(10, 10)
            
            # Dispatch task via gRPC
            task_result = await self._dispatch_task(task)
            results.append(task_result)
            
            # Return to desk
            await self.move_to(2, 2)
        
        await self.set_status(AgentStatus.THINKING, "Aggregating results...")
        
        # Generate final report
        final_report = self._generate_final_report(results)
        
        await self.set_status(AgentStatus.IDLE, "Task completed!")
        
        return {
            "success": True,
            "results": results,
            "final_report": final_report
        }
    
    async def _dispatch_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch a single task to the appropriate sub-agent via gRPC."""
        agent_name = task.get("agent", "luna")
        
        if not GRPC_AVAILABLE or not self.grpc_stub:
            # Fallback: simulate task dispatch without gRPC
            return await self._simulate_task_dispatch(task)
        
        try:
            # Create gRPC request
            request = agent_comms_pb2.TaskRequest(
                task_id=f"task_{asyncio.get_event_loop().time()}",
                source_agent=self.agent_id,
                target_agent=agent_name,
                task_type=task.get("task_type", "general"),
                description=task.get("description", ""),
                parameters=json.dumps(task)
            )
            
            # Send via gRPC
            response = await self.grpc_stub.DispatchTask(request)
            
            return {
                "task_id": request.task_id,
                "agent": agent_name,
                "success": response.success,
                "result": response.result,
                "error": response.error if not response.success else None
            }
            
        except Exception as e:
            return {
                "task_id": f"task_{asyncio.get_event_loop().time()}",
                "agent": agent_name,
                "success": False,
                "error": str(e)
            }
    
    async def _simulate_task_dispatch(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate task dispatch when gRPC is not available."""
        agent_name = task.get("agent", "luna")
        
        # Simulate processing time
        await asyncio.sleep(1)
        
        return {
            "task_id": f"task_{asyncio.get_event_loop().time()}",
            "agent": agent_name,
            "task_type": task.get("task_type"),
            "success": True,
            "result": f"Simulated result for {task.get('description', 'unknown task')}",
            "note": "gRPC not available - using simulation mode"
        }
    
    def _generate_final_report(self, results: List[Dict[str, Any]]) -> str:
        """Generate a final summary report from all task results."""
        # Save the execution summary to memory for future context
        summary_data = {
            "total_tasks": len(results),
            "successful": sum(1 for r in results if r.get("success", False)),
            "failed": len(results) - sum(1 for r in results if r.get("success", False)),
            "timestamp": asyncio.get_event_loop().time()
        }
        self.memory.save_context(
            f"Project execution summary: {json.dumps(summary_data)}",
            metadata={"type": "execution_summary"}
        )
        
        report_lines = [
            "# IVA-World Project Report",
            "",
            f"**Orchestrator:** {self.name}",
            f"**Tasks Executed:** {len(results)}",
            ""
        ]
        
        successful = sum(1 for r in results if r.get("success", False))
        failed = len(results) - successful
        
        report_lines.append(f"## Summary")
        report_lines.append(f"- Successful tasks: {successful}")
        report_lines.append(f"- Failed tasks: {failed}")
        report_lines.append("")
        
        report_lines.append("## Task Results")
        for i, result in enumerate(results, 1):
            agent = result.get("agent", "unknown")
            task_type = result.get("task_type", "general")
            status = "✅" if result.get("success") else "❌"
            
            report_lines.append(f"{i}. {status} **{agent}** ({task_type})")
            if result.get("result"):
                report_lines.append(f"   - {result['result'][:200]}")
            if result.get("error"):
                report_lines.append(f"   - Error: {result['error']}")
        
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("*Generated by IVA - Intelligent Virtual Assistant*")
        
        return "\n".join(report_lines)
    
    async def process_user_request(self, user_input: str) -> str:
        """Main entry point: process a user's natural language request."""
        print(f"\n[IVA] Received request: {user_input}")
        
        # Parse the request
        plan = self.parse_user_request(user_input)
        print(f"[IVA] Execution plan: {json.dumps(plan, indent=2)}")
        
        # Execute the plan
        result = await self.execute_plan(plan)
        
        # Return final report
        final_report = result.get("final_report", "No report generated")
        print(f"\n[IVA] {final_report}")
        
        return final_report


# Singleton instance
_iva_instance: Optional[IVA] = None


def get_iva_instance(grpc_channel=None, sandbox_dir: str = "./sandbox") -> IVA:
    """Get or create the singleton IVA instance."""
    global _iva_instance
    if _iva_instance is None:
        _iva_instance = IVA(grpc_channel, sandbox_dir)
    return _iva_instance
