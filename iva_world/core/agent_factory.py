"""
Agent Factory - Spawns and manages all IVA-World agents.
Creates Tier 2 (Luna, Archie) and Tier 3 (Byte, Pixel, Guardian) agents.
Now integrated with persistent memory for context retention.
"""

import asyncio
import json
from typing import Optional, Dict, Any, List
from enum import Enum

# Import tools
from core.tools import ToolRegistry, ToolResult

# Import memory system
from core.memory import global_memory_manager

# Import gRPC generated code
try:
    from protos.generated import agent_comms_pb2
    from protos.generated import agent_comms_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False


class AgentType(Enum):
    """All agent types in the system."""
    IVA = "iva"
    LUNA = "luna"
    ARCHIE = "archie"
    BYTE = "byte"
    PIXEL = "pixel"
    GUARDIAN = "guardian"


class BaseAgent:
    """Base class for all agents with common functionality."""
    
    # Class-level configuration to be overridden by subclasses
    AGENT_TYPE: AgentType = AgentType.IVA
    AVATAR_TYPE: str = "unknown"
    DEFAULT_POSITION: tuple = (0, 0)
    WORKSTATION_POSITION: tuple = (0, 0)
    
    def __init__(self, agent_id: str, grpc_channel=None, sandbox_dir: str = "./sandbox"):
        self.agent_id = agent_id
        self.name = self.AGENT_TYPE.value.capitalize()
        self.status = "IDLE"
        self.current_position = self.DEFAULT_POSITION
        self.target_position = self.DEFAULT_POSITION
        
        # Initialize persistent memory for this agent
        self.memory = global_memory_manager.get_memory(self.name.lower())
        
        self.grpc_channel = grpc_channel
        self.grpc_stub = None
        if grpc_channel and GRPC_AVAILABLE:
            self.grpc_stub = agent_comms_pb2_grpc.AgentCommunicationStub(grpc_channel)
        
        self.tool_registry = ToolRegistry(sandbox_dir)
        self.state_callback = None
        self._current_message = ""
    
    def set_state_callback(self, callback):
        """Set callback for broadcasting state changes."""
        self.state_callback = callback
    
    async def _broadcast_state(self):
        """Broadcast current state to frontend."""
        if self.state_callback:
            state_data = {
                "agent_id": self.agent_id,
                "name": self.name,
                "avatar": self.AVATAR_TYPE,
                "status": self.status,
                "position": list(self.current_position),
                "target_position": list(self.target_position),
                "message": self._current_message
            }
            await self.state_callback(state_data)
    
    async def set_status(self, status: str, message: str = ""):
        """Update status and broadcast."""
        self.status = status
        self._current_message = message
        await self._broadcast_state()
    
    async def move_to(self, x: int, y: int):
        """Move to a position on the grid."""
        self.target_position = (x, y)
        await self._broadcast_state()
        
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
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task - to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement execute_task")


class Luna(BaseAgent):
    """
    Luna - Market Research Agent (Tier 2)
    Avatar: Siamese Cat
    Tools: Web Search, Playwright browser automation, Document summarizer
    """
    
    AGENT_TYPE = AgentType.LUNA
    AVATAR_TYPE = "siamese"
    DEFAULT_POSITION = (18, 2)  # Research Lab
    WORKSTATION_POSITION = (18, 2)
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute research tasks."""
        await self.set_status("THINKING", "Analyzing research request...")
        await self.move_to(*self.WORKSTATION_POSITION)
        
        description = task.get("description", "")
        
        # Check memory for similar past research
        past_research = self.memory.search_context(description, n_results=2)
        if past_research:
            print(f"[Luna] Found {len(past_research)} relevant past research entries")
            # Could use this to skip redundant research or augment results
        
        await self.set_status("USING_TOOL", f"Searching web for: {description[:50]}...")
        
        # Perform web search
        search_query = description.replace("Research: ", "").replace("Analyze: ", "")
        search_result = await self.tool_registry.web_search.search(search_query, num_results=5)
        
        if not search_result.success:
            await self.set_status("ERROR", f"Search failed: {search_result.error}")
            return {"success": False, "error": search_result.error}
        
        await self.set_status("THINKING", "Summarizing findings...")
        
        # Compile results into a report
        results_data = search_result.data
        report_content = f"# Research Report: {search_query}\n\n"
        report_content += f"## Search Results\n\n"
        
        for i, result in enumerate(results_data, 1):
            report_content += f"### {i}. {result.get('title', 'No title')}\n"
            report_content += f"**URL:** {result.get('url', 'N/A')}\n"
            report_content += f"{result.get('snippet', 'No snippet')}\n\n"
        
        # Save findings to memory for future reference
        self.memory.save_context(
            f"Research on '{search_query}': {json.dumps([r.get('title', '') for r in results_data])}",
            metadata={"type": "research", "query": search_query}
        )
        
        # Write report to sandbox
        timestamp = int(asyncio.get_event_loop().time())
        report_filename = f"research_{search_query.replace(' ', '_')[:30]}_{timestamp}.md"
        
        await self.set_status("USING_TOOL", "Writing research report...")
        write_result = await self.tool_registry.file_io.write_file(report_filename, report_content)
        
        if not write_result.success:
            await self.set_status("ERROR", f"Failed to write report: {write_result.error}")
            return {"success": False, "error": write_result.error}
        
        await self.set_status("IDLE", "Research complete!")
        
        return {
            "success": True,
            "report_file": report_filename,
            "results_count": len(results_data),
            "summary": f"Researched '{search_query}', found {len(results_data)} results"
        }


class Archie(BaseAgent):
    """
    Archie - Software Engineering Agent (Tier 2)
    Avatar: Tabby Cat
    Task: Tech lead, spawns Tier 3 mini-agents
    """
    
    AGENT_TYPE = AgentType.ARCHIE
    AVATAR_TYPE = "tabby"
    DEFAULT_POSITION = (15, 5)  # Code Forge
    WORKSTATION_POSITION = (15, 5)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mini_agents: Dict[str, BaseAgent] = {}
    
    async def spawn_mini_agent(self, agent_type: AgentType) -> BaseAgent:
        """Dynamically spawn a mini-agent for specific tasks."""
        agent_id = f"{agent_type.value}_{asyncio.get_event_loop().time()}"
        
        if agent_type == AgentType.BYTE:
            agent = Byte(agent_id, self.grpc_channel)
        elif agent_type == AgentType.PIXEL:
            agent = Pixel(agent_id, self.grpc_channel)
        elif agent_type == AgentType.GUARDIAN:
            agent = Guardian(agent_id, self.grpc_channel)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        agent.set_state_callback(self.state_callback)
        self.mini_agents[agent_id] = agent
        
        return agent
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute development tasks by coordinating mini-agents."""
        await self.set_status("THINKING", "Analyzing development requirements...")
        await self.move_to(*self.WORKSTATION_POSITION)
        
        description = task.get("description", "")
        language = task.get("language", "python")
        
        # Determine which mini-agents to spawn
        agents_to_spawn = []
        
        if language == "python" or ".py" in description:
            agents_to_spawn.append(AgentType.BYTE)
        
        if "ui" in description.lower() or "design" in description.lower():
            agents_to_spawn.append(AgentType.PIXEL)
        
        # Always spawn Guardian for QA
        agents_to_spawn.append(AgentType.GUARDIAN)
        
        results = []
        
        for agent_type in agents_to_spawn:
            await self.set_status("COMMUNICATING", f"Spawning {agent_type.value}...")
            
            mini_agent = await self.spawn_mini_agent(agent_type)
            
            # Delegate task to mini-agent
            mini_task = {
                "type": f"{agent_type.value}_task",
                "description": description,
                "parent_task": task.get("task_id", "unknown"),
                "language": language
            }
            
            result = await mini_agent.execute_task(mini_task)
            results.append({
                "agent": agent_type.value,
                "result": result
            })
        
        await self.set_status("IDLE", "Development coordination complete!")
        
        return {
            "success": all(r["result"].get("success", False) for r in results),
            "mini_agent_results": results,
            "summary": f"Coordinated {len(results)} mini-agents"
        }


class Byte(BaseAgent):
    """
    Byte - Code Writer Mini-Agent (Tier 3)
    Avatar: Black Cat
    Task: Generates Python/JS/HTML files
    """
    
    AGENT_TYPE = AgentType.BYTE
    AVATAR_TYPE = "black"
    DEFAULT_POSITION = (12, 8)  # Coding Station
    WORKSTATION_POSITION = (12, 8)
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Write code files."""
        await self.set_status("THINKING", "Planning code structure...")
        await self.move_to(*self.WORKSTATION_POSITION)
        
        description = task.get("description", "")
        language = task.get("language", "python")
        
        await self.set_status("USING_TOOL", f"Writing {language} code...")
        
        # Generate sample code based on description
        if language == "python":
            code_content = self._generate_python_code(description)
            extension = "py"
        elif language == "javascript" or language == "js":
            code_content = self._generate_javascript_code(description)
            extension = "js"
        elif language == "html":
            code_content = self._generate_html_code(description)
            extension = "html"
        else:
            code_content = f"# {language} code for: {description}\nprint('Hello World')"
            extension = "txt"
        
        # Write file
        filename = f"generated_{task.get('type', 'code')}.{extension}"
        write_result = await self.tool_registry.file_io.write_file(filename, code_content)
        
        if not write_result.success:
            await self.set_status("ERROR", f"Failed to write file: {write_result.error}")
            return {"success": False, "error": write_result.error}
        
        await self.set_status("IDLE", f"Code written: {filename}")
        
        return {
            "success": True,
            "file": filename,
            "language": language,
            "bytes_written": write_result.data.get("bytes_written", 0)
        }
    
    def _generate_python_code(self, description: str) -> str:
        """Generate Python code template."""
        return f'''"""
Generated Python module
Description: {description}
"""

def main():
    """Main entry point."""
    print("Executing: {description}")
    
    # TODO: Implement functionality
    pass


if __name__ == "__main__":
    main()
'''
    
    def _generate_javascript_code(self, description: str) -> str:
        """Generate JavaScript code template."""
        return f'''/**
 * Generated JavaScript module
 * Description: {description}
 */

function main() {{
    console.log("Executing: {description}");
    
    // TODO: Implement functionality
}}

module.exports = {{ main }};
'''
    
    def _generate_html_code(self, description: str) -> str:
        """Generate HTML template."""
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{description[:50]}</title>
</head>
<body>
    <h1>{description}</h1>
    <!-- TODO: Add content -->
</body>
</html>
'''


class Pixel(BaseAgent):
    """
    Pixel - UI/UX Designer Mini-Agent (Tier 3)
    Avatar: Calico Cat
    Task: Generates CSS, design tokens, layout wireframes
    """
    
    AGENT_TYPE = AgentType.PIXEL
    AVATAR_TYPE = "calico"
    DEFAULT_POSITION = (8, 15)  # Design Studio
    WORKSTATION_POSITION = (8, 15)
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Generate UI/UX design assets."""
        await self.set_status("THINKING", "Designing UI components...")
        await self.move_to(*self.WORKSTATION_POSITION)
        
        description = task.get("description", "")
        
        await self.set_status("USING_TOOL", "Creating design tokens and CSS...")
        
        # Generate design tokens
        design_tokens = self._generate_design_tokens()
        css_content = self._generate_css_template(description)
        
        # Write files
        tokens_result = await self.tool_registry.file_io.write_file(
            "design_tokens.json",
            design_tokens
        )
        
        css_result = await self.tool_registry.file_io.write_file(
            "styles.css",
            css_content
        )
        
        if not tokens_result.success or not css_result.success:
            await self.set_status("ERROR", "Failed to write design files")
            return {"success": False}
        
        await self.set_status("IDLE", "Design assets created!")
        
        return {
            "success": True,
            "files": ["design_tokens.json", "styles.css"],
            "summary": "Generated design tokens and CSS styles"
        }
    
    def _generate_design_tokens(self) -> str:
        """Generate JSON design tokens."""
        import json
        tokens = {
            "colors": {
                "primary": "#4F46E5",
                "secondary": "#7C3AED",
                "accent": "#EC4899",
                "background": "#F9FAFB",
                "text": "#1F2937"
            },
            "spacing": {
                "xs": "4px",
                "sm": "8px",
                "md": "16px",
                "lg": "24px",
                "xl": "32px"
            },
            "typography": {
                "fontFamily": "Inter, system-ui, sans-serif",
                "fontSize": {
                    "sm": "14px",
                    "base": "16px",
                    "lg": "18px",
                    "xl": "20px"
                }
            },
            "borderRadius": {
                "sm": "4px",
                "md": "8px",
                "lg": "12px",
                "full": "9999px"
            }
        }
        return json.dumps(tokens, indent=2)
    
    def _generate_css_template(self, description: str) -> str:
        """Generate CSS template."""
        return f'''/*
 * Generated Stylesheet
 * Project: {description}
 */

:root {{
    --color-primary: #4F46E5;
    --color-secondary: #7C3AED;
    --color-accent: #EC4899;
    --color-background: #F9FAFB;
    --color-text: #1F2937;
    
    --spacing-sm: 8px;
    --spacing-md: 16px;
    --spacing-lg: 24px;
    
    --font-family: Inter, system-ui, sans-serif;
    --border-radius: 8px;
}}

* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: var(--font-family);
    background-color: var(--color-background);
    color: var(--color-text);
    line-height: 1.6;
}}

.container {{
    max-width: 1200px;
    margin: 0 auto;
    padding: var(--spacing-lg);
}}

.btn {{
    display: inline-block;
    padding: var(--spacing-sm) var(--spacing-md);
    background-color: var(--color-primary);
    color: white;
    border: none;
    border-radius: var(--border-radius);
    cursor: pointer;
    transition: opacity 0.2s;
}}

.btn:hover {{
    opacity: 0.9;
}}
'''


class Guardian(BaseAgent):
    """
    Guardian - Security & QA Mini-Agent (Tier 3)
    Avatar: Sphynx Cat
    Task: Code review, linting, security checks, testing
    """
    
    AGENT_TYPE = AgentType.GUARDIAN
    AVATAR_TYPE = "sphynx"
    DEFAULT_POSITION = (5, 18)  # Security Office
    WORKSTATION_POSITION = (5, 18)
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Perform security and QA checks."""
        await self.set_status("THINKING", "Analyzing code for security issues...")
        await self.move_to(*self.WORKSTATION_POSITION)
        
        # List files in sandbox to review
        files_result = await self.tool_registry.file_io.list_files()
        
        if not files_result.success:
            await self.set_status("ERROR", "Failed to list files for review")
            return {"success": False}
        
        files = files_result.data
        issues = []
        warnings = []
        
        await self.set_status("USING_TOOL", "Running security scans...")
        
        # Simple static analysis
        for file_info in files:
            if file_info.get("is_directory"):
                continue
            
            filename = file_info.get("name", "")
            
            # Check for potentially dangerous patterns
            if filename.endswith(".py"):
                read_result = await self.tool_registry.file_io.read_file(filename)
                if read_result.success:
                    content = read_result.data
                    
                    # Basic security checks
                    if "eval(" in content:
                        warnings.append(f"{filename}: Use of eval() detected")
                    if "exec(" in content:
                        warnings.append(f"{filename}: Use of exec() detected")
                    if "os.system(" in content:
                        warnings.append(f"{filename}: Use of os.system() detected")
        
        # Generate QA report
        report_content = "# Security & QA Report\n\n"
        report_content += f"## Files Reviewed: {len(files)}\n\n"
        
        if issues:
            report_content += "### 🔴 Critical Issues\n"
            for issue in issues:
                report_content += f"- {issue}\n"
            report_content += "\n"
        
        if warnings:
            report_content += "### ⚠️ Warnings\n"
            for warning in warnings:
                report_content += f"- {warning}\n"
            report_content += "\n"
        
        if not issues and not warnings:
            report_content += "### ✅ No issues found!\n\n"
        
        report_content += "## Recommendations\n"
        report_content += "- Continue following secure coding practices\n"
        report_content += "- Add unit tests for critical functions\n"
        report_content += "- Consider adding input validation\n"
        
        # Write report
        timestamp = int(asyncio.get_event_loop().time())
        report_filename = f"qa_report_{timestamp}.md"
        
        write_result = await self.tool_registry.file_io.write_file(report_filename, report_content)
        
        if not write_result.success:
            await self.set_status("ERROR", f"Failed to write QA report: {write_result.error}")
            return {"success": False}
        
        status = "IDLE" if not issues else "ERROR"
        message = "QA complete - No critical issues!" if not issues else f"QA complete - {len(issues)} issues found"
        
        await self.set_status(status, message)
        
        return {
            "success": len(issues) == 0,
            "report_file": report_filename,
            "files_reviewed": len(files),
            "issues_count": len(issues),
            "warnings_count": len(warnings),
            "has_critical_issues": len(issues) > 0
        }


class AgentFactory:
    """Factory for creating and managing all agents."""
    
    _instance = None
    
    def __new__(cls, grpc_channel=None, sandbox_dir: str = "./sandbox"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, grpc_channel=None, sandbox_dir: str = "./sandbox"):
        if self._initialized:
            return
        
        self.grpc_channel = grpc_channel
        self.sandbox_dir = sandbox_dir
        self.agents: Dict[str, BaseAgent] = {}
        
        # Pre-instantiate Tier 2 agents
        self._create_tier2_agents()
        
        self._initialized = True
    
    def _create_tier2_agents(self):
        """Create Tier 2 specialist agents."""
        self.agents["luna"] = Luna("luna_001", self.grpc_channel, self.sandbox_dir)
        self.agents["archie"] = Archie("archie_001", self.grpc_channel, self.sandbox_dir)
    
    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """Get an agent by name."""
        return self.agents.get(agent_name.lower())
    
    def get_all_agents(self) -> List[BaseAgent]:
        """Get all registered agents."""
        return list(self.agents.values())
    
    def register_state_callback(self, callback):
        """Register state callback for all agents."""
        for agent in self.agents.values():
            agent.set_state_callback(callback)
    
    async def execute_task_for_agent(self, agent_name: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task for a specific agent."""
        agent = self.get_agent(agent_name)
        if not agent:
            return {"success": False, "error": f"Agent {agent_name} not found"}
        
        return await agent.execute_task(task)


# Convenience function
def get_agent_factory(grpc_channel=None, sandbox_dir: str = "./sandbox") -> AgentFactory:
    """Get or create the singleton AgentFactory instance."""
    return AgentFactory(grpc_channel, sandbox_dir)
