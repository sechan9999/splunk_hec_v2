# tool_manager.py
"""
MCP Tool Management System
MCP 도구 관리 시스템

다양한 MCP 서버를 플러그인 형태로 등록하고 관리합니다.
Google Drive, Slack, GitHub 등 외부 서비스 연동을 지원합니다.
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import asyncio


class ToolCategory(Enum):
    """도구 카테고리 (Tool Category)"""
    STORAGE = "storage"           # Google Drive, S3, etc.
    COMMUNICATION = "communication"  # Slack, Email, etc.
    DEVELOPMENT = "development"   # GitHub, GitLab, etc.
    DATABASE = "database"         # SQL, NoSQL, etc.
    AI = "ai"                     # LLM, Vision, etc.
    ANALYTICS = "analytics"       # BigQuery, Snowflake, etc.
    CUSTOM = "custom"             # Custom tools


class ToolStatus(Enum):
    """도구 상태 (Tool Status)"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING = "pending"


class PermissionLevel(Enum):
    """권한 레벨 (Permission Level)"""
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    ADMIN = "admin"


@dataclass
class ToolCredential:
    """도구 자격 증명 (Tool Credential)"""
    type: str  # api_key, oauth, basic, etc.
    data: Dict[str, str] = field(default_factory=dict)
    expires_at: Optional[datetime] = None
    is_valid: bool = True


@dataclass
class ToolConfig:
    """도구 설정 (Tool Configuration)"""
    tool_id: str
    name: str
    description: str
    category: ToolCategory
    
    # 연결 정보
    server_url: str = ""
    version: str = "1.0.0"
    protocol: str = "mcp"  # mcp, rest, graphql
    
    # 권한
    permission: PermissionLevel = PermissionLevel.READ_ONLY
    allowed_users: List[str] = field(default_factory=list)
    allowed_roles: List[str] = field(default_factory=list)
    
    # 자격 증명
    credential: Optional[ToolCredential] = None
    
    # 상태
    status: ToolStatus = ToolStatus.INACTIVE
    last_health_check: Optional[datetime] = None
    error_message: str = ""
    
    # 메타데이터
    icon: str = "🔧"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 사용 통계
    call_count: int = 0
    success_count: int = 0
    avg_latency_ms: float = 0.0


@dataclass
class ToolMethod:
    """도구 메서드 (Tool Method)"""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema
    returns: Dict[str, Any]     # JSON Schema
    requires_permission: PermissionLevel = PermissionLevel.READ_ONLY


class MCPServerPlugin:
    """MCP 서버 플러그인 기본 클래스"""
    
    def __init__(self, config: ToolConfig):
        self.config = config
        self._methods: Dict[str, ToolMethod] = {}
    
    async def connect(self) -> bool:
        """연결"""
        raise NotImplementedError
    
    async def disconnect(self) -> None:
        """연결 해제"""
        raise NotImplementedError
    
    async def health_check(self) -> bool:
        """상태 확인"""
        raise NotImplementedError
    
    async def call(self, method: str, params: Dict) -> Any:
        """메서드 호출"""
        raise NotImplementedError
    
    def get_methods(self) -> List[ToolMethod]:
        """사용 가능한 메서드 목록"""
        return list(self._methods.values())


class GoogleDrivePlugin(MCPServerPlugin):
    """Google Drive 플러그인"""
    
    def __init__(self, config: ToolConfig):
        super().__init__(config)
        self._methods = {
            "list_files": ToolMethod(
                name="list_files",
                description="List files in a folder",
                parameters={"folder_id": "string", "limit": "integer"},
                returns={"files": "array"}
            ),
            "read_file": ToolMethod(
                name="read_file",
                description="Read file content",
                parameters={"file_id": "string"},
                returns={"content": "string", "metadata": "object"}
            ),
            "upload_file": ToolMethod(
                name="upload_file",
                description="Upload a file",
                parameters={"name": "string", "content": "string", "folder_id": "string"},
                returns={"file_id": "string"},
                requires_permission=PermissionLevel.READ_WRITE
            ),
        }
    
    async def connect(self) -> bool:
        # OAuth 연결 로직
        print(f"🔗 Connecting to Google Drive...")
        self.config.status = ToolStatus.ACTIVE
        return True
    
    async def disconnect(self) -> None:
        self.config.status = ToolStatus.INACTIVE
    
    async def health_check(self) -> bool:
        # API 상태 확인
        return True
    
    async def call(self, method: str, params: Dict) -> Any:
        # 시뮬레이션
        return {"status": "success", "method": method}


class SlackPlugin(MCPServerPlugin):
    """Slack 플러그인"""
    
    def __init__(self, config: ToolConfig):
        super().__init__(config)
        self._methods = {
            "send_message": ToolMethod(
                name="send_message",
                description="Send a message to a channel",
                parameters={"channel": "string", "text": "string"},
                returns={"ts": "string"},
                requires_permission=PermissionLevel.READ_WRITE
            ),
            "list_channels": ToolMethod(
                name="list_channels",
                description="List available channels",
                parameters={},
                returns={"channels": "array"}
            ),
        }
    
    async def connect(self) -> bool:
        print(f"🔗 Connecting to Slack...")
        self.config.status = ToolStatus.ACTIVE
        return True
    
    async def disconnect(self) -> None:
        self.config.status = ToolStatus.INACTIVE
    
    async def health_check(self) -> bool:
        return True
    
    async def call(self, method: str, params: Dict) -> Any:
        return {"status": "success", "method": method}


class GitHubPlugin(MCPServerPlugin):
    """GitHub 플러그인"""
    
    def __init__(self, config: ToolConfig):
        super().__init__(config)
        self._methods = {
            "list_repos": ToolMethod(
                name="list_repos",
                description="List repositories",
                parameters={"user": "string"},
                returns={"repos": "array"}
            ),
            "get_file": ToolMethod(
                name="get_file",
                description="Get file content from repo",
                parameters={"repo": "string", "path": "string"},
                returns={"content": "string"}
            ),
            "create_issue": ToolMethod(
                name="create_issue",
                description="Create a new issue",
                parameters={"repo": "string", "title": "string", "body": "string"},
                returns={"issue_url": "string"},
                requires_permission=PermissionLevel.READ_WRITE
            ),
            "create_pr": ToolMethod(
                name="create_pr",
                description="Create a pull request",
                parameters={"repo": "string", "title": "string", "head": "string", "base": "string"},
                returns={"pr_url": "string"},
                requires_permission=PermissionLevel.READ_WRITE
            ),
        }
    
    async def connect(self) -> bool:
        print(f"🔗 Connecting to GitHub...")
        self.config.status = ToolStatus.ACTIVE
        return True
    
    async def disconnect(self) -> None:
        self.config.status = ToolStatus.INACTIVE
    
    async def health_check(self) -> bool:
        return True
    
    async def call(self, method: str, params: Dict) -> Any:
        return {"status": "success", "method": method}


class SplunkPlugin(MCPServerPlugin):
    """Splunk Analytics 플러그인 — SplunkMCPTool 래퍼"""

    def __init__(self, config: ToolConfig):
        super().__init__(config)
        from tools.splunk_mcp_tool import SplunkMCPTool
        self._splunk = SplunkMCPTool()
        self._methods = {
            "splunk_query": ToolMethod(
                name="splunk_query",
                description="Natural language or SPL query on index=mcp_agents",
                parameters={
                    "query":       {"type": "string"},
                    "timerange":   {"type": "string", "default": "-1h"},
                    "max_results": {"type": "integer", "default": 50},
                },
                returns={"results": "array", "spl": "string", "summary": "string"},
                requires_permission=PermissionLevel.READ_ONLY,
            )
        }

    async def connect(self) -> bool:
        self.config.status = ToolStatus.ACTIVE
        return True

    async def disconnect(self) -> None:
        self.config.status = ToolStatus.INACTIVE

    async def health_check(self) -> bool:
        return self._splunk._mcp_available or bool(self._splunk._rest.base_url)

    async def call(self, method: str, params: Dict) -> Any:
        if method == "splunk_query":
            return self._splunk.execute(**params)
        raise ValueError(f"Unknown method: {method}")


class DataHubPlugin(MCPServerPlugin):
    """DataHub context-graph plugin — DataHubMCPTool wrapper"""

    def __init__(self, config: ToolConfig):
        super().__init__(config)
        from tools.datahub_mcp_tool import DataHubMCPTool
        self._datahub = DataHubMCPTool()
        self._methods = {
            "datahub_query": ToolMethod(
                name="datahub_query",
                description="Natural language query on the DataHub context graph "
                            "(dataset search, ownership, lineage, quality)",
                parameters={
                    "query": {"type": "string"},
                },
                returns={"results": "array", "method": "string"},
                requires_permission=PermissionLevel.READ_ONLY,
            ),
            "datahub_context": ToolMethod(
                name="datahub_context",
                description="Full DatasetContext (owners, deprecation, tags, "
                            "assertions, lineage) for a dataset URN",
                parameters={
                    "urn": {"type": "string"},
                },
                returns={"context": "object"},
                requires_permission=PermissionLevel.READ_ONLY,
            ),
        }

    async def connect(self) -> bool:
        self.config.status = ToolStatus.ACTIVE
        return True

    async def disconnect(self) -> None:
        self.config.status = ToolStatus.INACTIVE

    async def health_check(self) -> bool:
        return self._datahub.configured

    async def call(self, method: str, params: Dict) -> Any:
        if method == "datahub_query":
            return self._datahub.execute(**params)
        if method == "datahub_context":
            ctx = self._datahub.get_context(params["urn"])
            return {"context": ctx.to_dict() if ctx else None}
        raise ValueError(f"Unknown method: {method}")


# 플러그인 레지스트리
PLUGIN_REGISTRY: Dict[str, type] = {
    "google_drive": GoogleDrivePlugin,
    "slack":        SlackPlugin,
    "github":       GitHubPlugin,
    "splunk":       SplunkPlugin,
    "datahub":      DataHubPlugin,
}


class ToolManager:
    """도구 관리자 (Tool Manager)
    
    모든 MCP 서버 플러그인을 중앙에서 관리합니다.
    """
    
    def __init__(self):
        self._tools: Dict[str, ToolConfig] = {}
        self._plugins: Dict[str, MCPServerPlugin] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
    
    def register_tool(self, config: ToolConfig) -> bool:
        """도구 등록"""
        if config.tool_id in self._tools:
            print(f"⚠️ Tool {config.tool_id} already exists")
            return False
        
        self._tools[config.tool_id] = config
        
        # 플러그인 생성
        plugin_class = PLUGIN_REGISTRY.get(config.tool_id)
        if plugin_class:
            self._plugins[config.tool_id] = plugin_class(config)
        
        self._emit("tool_registered", config)
        print(f"✓ Tool registered: {config.name} ({config.tool_id})")
        return True
    
    def unregister_tool(self, tool_id: str) -> bool:
        """도구 등록 해제"""
        if tool_id not in self._tools:
            return False
        
        config = self._tools.pop(tool_id)
        self._plugins.pop(tool_id, None)
        
        self._emit("tool_unregistered", config)
        return True
    
    def get_tool(self, tool_id: str) -> Optional[ToolConfig]:
        """도구 조회"""
        return self._tools.get(tool_id)
    
    def list_tools(
        self,
        category: ToolCategory = None,
        status: ToolStatus = None
    ) -> List[ToolConfig]:
        """도구 목록 조회"""
        tools = list(self._tools.values())
        
        if category:
            tools = [t for t in tools if t.category == category]
        if status:
            tools = [t for t in tools if t.status == status]
        
        return tools
    
    async def connect_tool(self, tool_id: str) -> bool:
        """도구 연결"""
        plugin = self._plugins.get(tool_id)
        if not plugin:
            return False
        
        try:
            success = await plugin.connect()
            if success:
                self._tools[tool_id].status = ToolStatus.ACTIVE
                self._tools[tool_id].last_health_check = datetime.now()
            return success
        except Exception as e:
            self._tools[tool_id].status = ToolStatus.ERROR
            self._tools[tool_id].error_message = str(e)
            return False
    
    async def disconnect_tool(self, tool_id: str) -> None:
        """도구 연결 해제"""
        plugin = self._plugins.get(tool_id)
        if plugin:
            await plugin.disconnect()
            self._tools[tool_id].status = ToolStatus.INACTIVE
    
    async def call_tool(
        self,
        tool_id: str,
        method: str,
        params: Dict,
        user_id: str = ""
    ) -> Any:
        """도구 메서드 호출"""
        config = self._tools.get(tool_id)
        if not config:
            raise ValueError(f"Tool not found: {tool_id}")
        
        if config.status != ToolStatus.ACTIVE:
            raise RuntimeError(f"Tool not active: {tool_id}")
        
        # 권한 확인
        if config.allowed_users and user_id not in config.allowed_users:
            raise PermissionError(f"User {user_id} not allowed")
        
        plugin = self._plugins.get(tool_id)
        if not plugin:
            raise RuntimeError(f"Plugin not found: {tool_id}")
        
        # 메서드 호출
        import time
        start = time.time()
        
        try:
            result = await plugin.call(method, params)
            
            # 통계 업데이트
            config.call_count += 1
            config.success_count += 1
            latency = (time.time() - start) * 1000
            config.avg_latency_ms = (
                (config.avg_latency_ms * (config.call_count - 1) + latency) / 
                config.call_count
            )
            
            return result
            
        except Exception as e:
            config.call_count += 1
            raise
    
    async def health_check_all(self) -> Dict[str, bool]:
        """모든 도구 상태 확인"""
        results = {}
        for tool_id, plugin in self._plugins.items():
            try:
                results[tool_id] = await plugin.health_check()
                self._tools[tool_id].last_health_check = datetime.now()
            except:
                results[tool_id] = False
                self._tools[tool_id].status = ToolStatus.ERROR
        return results
    
    def get_tool_methods(self, tool_id: str) -> List[ToolMethod]:
        """도구 메서드 목록"""
        plugin = self._plugins.get(tool_id)
        if plugin:
            return plugin.get_methods()
        return []
    
    def on(self, event: str, handler: Callable):
        """이벤트 핸들러 등록"""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)
    
    def _emit(self, event: str, data: Any):
        """이벤트 발생"""
        for handler in self._event_handlers.get(event, []):
            try:
                handler(data)
            except Exception as e:
                print(f"Event handler error: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """통계 조회"""
        tools = self.list_tools()
        
        active_count = len([t for t in tools if t.status == ToolStatus.ACTIVE])
        total_calls = sum(t.call_count for t in tools)
        total_success = sum(t.success_count for t in tools)
        
        return {
            "total_tools": len(tools),
            "active_tools": active_count,
            "inactive_tools": len(tools) - active_count,
            "total_calls": total_calls,
            "success_rate": total_success / total_calls if total_calls > 0 else 0,
            "by_category": {
                cat.value: len([t for t in tools if t.category == cat])
                for cat in ToolCategory
            }
        }
    
    def export_config(self) -> Dict[str, Any]:
        """설정 내보내기 (자격 증명 제외)"""
        return {
            "tools": [
                {
                    "tool_id": t.tool_id,
                    "name": t.name,
                    "description": t.description,
                    "category": t.category.value,
                    "server_url": t.server_url,
                    "permission": t.permission.value,
                    "status": t.status.value,
                    "tags": t.tags
                }
                for t in self._tools.values()
            ]
        }


# === 테스트 ===
async def test_tool_manager():
    """도구 관리자 테스트"""
    print("=" * 60)
    print("🔧 Tool Manager Test")
    print("=" * 60)
    
    manager = ToolManager()
    
    # 도구 등록
    tools = [
        ToolConfig(
            tool_id="google_drive",
            name="Google Drive",
            description="Cloud storage by Google",
            category=ToolCategory.STORAGE,
            icon="📁",
            tags=["storage", "cloud", "google"]
        ),
        ToolConfig(
            tool_id="slack",
            name="Slack",
            description="Team communication platform",
            category=ToolCategory.COMMUNICATION,
            icon="💬",
            tags=["chat", "team", "communication"]
        ),
        ToolConfig(
            tool_id="github",
            name="GitHub",
            description="Code hosting and collaboration",
            category=ToolCategory.DEVELOPMENT,
            permission=PermissionLevel.READ_WRITE,
            icon="🐙",
            tags=["git", "code", "vcs"]
        ),
    ]
    
    print("\n📋 Registering tools...")
    for tool in tools:
        manager.register_tool(tool)
    
    # 연결
    print("\n🔗 Connecting tools...")
    for tool_id in ["google_drive", "slack", "github"]:
        await manager.connect_tool(tool_id)
    
    # 메서드 목록
    print("\n📝 Available methods:")
    for tool_id in ["google_drive", "github"]:
        methods = manager.get_tool_methods(tool_id)
        print(f"\n   {tool_id}:")
        for m in methods:
            print(f"   - {m.name}: {m.description}")
    
    # 도구 호출
    print("\n🚀 Calling tool...")
    result = await manager.call_tool(
        "github",
        "list_repos",
        {"user": "sechan9999"}
    )
    print(f"   Result: {result}")
    
    # 통계
    print("\n" + "=" * 60)
    print("📊 Statistics")
    print("=" * 60)
    stats = manager.get_statistics()
    print(f"   Total Tools: {stats['total_tools']}")
    print(f"   Active: {stats['active_tools']}")
    print(f"   By Category: {stats['by_category']}")
    
    print("\n✅ Tool Manager Test Complete!")


if __name__ == "__main__":
    asyncio.run(test_tool_manager())
