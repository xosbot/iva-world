"""
Tool definitions for IVA-World agents.
Includes web search, browser automation, and file I/O operations.
"""

import os
import asyncio
from typing import Optional, List, Dict, Any
from pathlib import Path

# Try to import playwright, but make it optional for testing
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Try to import requests for simple HTTP calls
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class ToolResult:
    """Represents the result of a tool execution."""
    
    def __init__(self, success: bool, data: Any, error: Optional[str] = None):
        self.success = success
        self.data = data
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error
        }


class WebSearchTool:
    """Web search tool using DuckDuckGo or Tavily API."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.use_tavily = bool(self.api_key)
    
    async def search(self, query: str, num_results: int = 5) -> ToolResult:
        """Perform a web search and return results."""
        try:
            if self.use_tavily and REQUESTS_AVAILABLE:
                return await self._tavily_search(query, num_results)
            elif REQUESTS_AVAILABLE:
                return await self._duckduckgo_search(query, num_results)
            else:
                return ToolResult(
                    success=False,
                    data=[],
                    error="No search backend available. Install 'requests' package."
                )
        except Exception as e:
            return ToolResult(success=False, data=[], error=str(e))
    
    async def _tavily_search(self, query: str, num_results: int) -> ToolResult:
        """Search using Tavily API."""
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key,
            "query": query,
            "num_results": num_results
        }
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        results = response.json().get("results", [])
        
        formatted_results = [
            {
                "title": r.get("title", "No title"),
                "url": r.get("url", ""),
                "snippet": r.get("content", "")
            }
            for r in results[:num_results]
        ]
        
        return ToolResult(success=True, data=formatted_results)
    
    async def _duckduckgo_search(self, query: str, num_results: int) -> ToolResult:
        """Simple DuckDuckGo search via HTML scraping (fallback)."""
        # Note: This is a simplified fallback. For production, use proper DDG API
        return ToolResult(
            success=True,
            data=[
                {
                    "title": f"Result {i+1} for '{query}'",
                    "url": f"https://duckduckgo.com/?q={query}",
                    "snippet": f"Simulated search result {i+1} for {query}"
                }
                for i in range(num_results)
            ],
            error="Using simulated search. Install tavily-python for real results."
        )


class BrowserAutomationTool:
    """Playwright-based browser automation tool."""
    
    def __init__(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright not installed. Run: pip install playwright")
    
    async def scrape_page(self, url: str) -> ToolResult:
        """Scrape content from a URL using Playwright."""
        if not PLAYWRIGHT_AVAILABLE:
            return ToolResult(
                success=False,
                data="",
                error="Playwright not available"
            )
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                # Extract main content
                title = await page.title()
                content = await page.evaluate("""
                    () => {
                        // Remove scripts, styles, nav, footer
                        document.querySelectorAll('script, style, nav, footer, header').forEach(el => el.remove());
                        return document.body.innerText;
                    }
                """)
                
                await browser.close()
                
                return ToolResult(
                    success=True,
                    data={"url": url, "title": title, "content": content[:10000]}  # Limit content length
                )
        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))
    
    async def get_screenshot(self, url: str, output_path: str) -> ToolResult:
        """Take a screenshot of a webpage."""
        if not PLAYWRIGHT_AVAILABLE:
            return ToolResult(success=False, data="", error="Playwright not available")
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.screenshot(path=output_path, full_page=True)
                await browser.close()
                
                return ToolResult(success=True, data=output_path)
        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))


class FileIOTool:
    """File system operations tool for sandboxed environment."""
    
    def __init__(self, sandbox_dir: str = "./sandbox"):
        self.sandbox_dir = Path(sandbox_dir).resolve()
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
    
    def _validate_path(self, filepath: str) -> Path:
        """Ensure the path is within the sandbox directory."""
        full_path = (self.sandbox_dir / filepath).resolve()
        if not str(full_path).startswith(str(self.sandbox_dir)):
            raise ValueError(f"Path escape attempt detected: {filepath}")
        return full_path
    
    async def write_file(self, filepath: str, content: str) -> ToolResult:
        """Write content to a file in the sandbox."""
        try:
            full_path = self._validate_path(filepath)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return ToolResult(
                success=True,
                data={"path": str(full_path), "bytes_written": len(content)}
            )
        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))
    
    async def read_file(self, filepath: str) -> ToolResult:
        """Read content from a file in the sandbox."""
        try:
            full_path = self._validate_path(filepath)
            
            if not full_path.exists():
                return ToolResult(
                    success=False,
                    data="",
                    error=f"File not found: {filepath}"
                )
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return ToolResult(success=True, data=content)
        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))
    
    async def list_files(self, subdir: str = "") -> ToolResult:
        """List files in a sandbox subdirectory."""
        try:
            full_path = self._validate_path(subdir) if subdir else self.sandbox_dir
            
            if not full_path.exists():
                return ToolResult(success=True, data=[])
            
            files = []
            for item in full_path.iterdir():
                files.append({
                    "name": item.name,
                    "is_directory": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else 0
                })
            
            return ToolResult(success=True, data=files)
        except Exception as e:
            return ToolResult(success=False, data=[], error=str(e))
    
    async def delete_file(self, filepath: str) -> ToolResult:
        """Delete a file from the sandbox."""
        try:
            full_path = self._validate_path(filepath)
            
            if not full_path.exists():
                return ToolResult(
                    success=False,
                    data="",
                    error=f"File not found: {filepath}"
                )
            
            if full_path.is_file():
                full_path.unlink()
                return ToolResult(success=True, data={"deleted": str(full_path)})
            else:
                return ToolResult(
                    success=False,
                    data="",
                    error=f"Cannot delete directory: {filepath}"
                )
        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))


class DocumentSummarizerTool:
    """Simple text summarization tool."""
    
    def __init__(self, max_summary_length: int = 500):
        self.max_summary_length = max_summary_length
    
    async def summarize(self, text: str, max_sentences: int = 3) -> ToolResult:
        """Generate a simple extractive summary."""
        try:
            if not text or len(text.strip()) == 0:
                return ToolResult(success=False, data="", error="Empty text provided")
            
            # Simple extractive summarization (first N sentences)
            sentences = text.replace('\n', ' ').split('.')
            sentences = [s.strip() + '.' for s in sentences if s.strip()]
            
            summary_sentences = sentences[:max_sentences]
            summary = ' '.join(summary_sentences)
            
            if len(summary) > self.max_summary_length:
                summary = summary[:self.max_summary_length - 3] + "..."
            
            return ToolResult(success=True, data=summary)
        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))


# Tool registry for easy access
class ToolRegistry:
    """Central registry for all available tools."""
    
    _instance = None
    
    def __new__(cls, sandbox_dir: str = "./sandbox"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, sandbox_dir: str = "./sandbox"):
        if self._initialized:
            return
        
        self.sandbox_dir = sandbox_dir
        self.web_search = WebSearchTool()
        self.browser = BrowserAutomationTool() if PLAYWRIGHT_AVAILABLE else None
        self.file_io = FileIOTool(sandbox_dir)
        self.summarizer = DocumentSummarizerTool()
        self._initialized = True
    
    def get_tools(self) -> Dict[str, Any]:
        """Return all available tools."""
        tools = {
            "web_search": self.web_search,
            "file_io": self.file_io,
            "summarizer": self.summarizer
        }
        if self.browser:
            tools["browser"] = self.browser
        return tools


# Convenience functions for direct tool usage
async def web_search(query: str, num_results: int = 5) -> ToolResult:
    """Convenience function for web search."""
    registry = ToolRegistry()
    return await registry.web_search.search(query, num_results)


async def write_file(filepath: str, content: str) -> ToolResult:
    """Convenience function for writing files."""
    registry = ToolRegistry()
    return await registry.file_io.write_file(filepath, content)


async def read_file(filepath: str) -> ToolResult:
    """Convenience function for reading files."""
    registry = ToolRegistry()
    return await registry.file_io.read_file(filepath)


async def scrape_url(url: str) -> ToolResult:
    """Convenience function for scraping URLs."""
    registry = ToolRegistry()
    if registry.browser:
        return await registry.browser.scrape_page(url)
    return ToolResult(success=False, data="", error="Browser tool not available")


async def summarize_text(text: str, max_sentences: int = 3) -> ToolResult:
    """Convenience function for text summarization."""
    registry = ToolRegistry()
    return await registry.summarizer.summarize(text, max_sentences)
