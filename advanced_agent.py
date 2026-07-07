# advanced_agent.py
"""
Advanced MCP Agent - 고급 MCP 에이전트
Context7 + Playwright + 지능형 라우터 통합

최신 라이브러리 문서 자동 조회 + 브라우저 자동화 + 스마트 라우팅
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio
import json
import time


class AgentCapability(Enum):
    """에이전트 기능 (Agent Capabilities)"""
    CODE_GENERATION = "code_generation"
    WEB_BROWSING = "web_browsing"
    DOCUMENTATION = "documentation"
    DATA_ANALYSIS = "data_analysis"
    FILE_OPERATION = "file_operation"
    API_INTEGRATION = "api_integration"


@dataclass
class AgentContext:
    """에이전트 컨텍스트 (Agent Context)"""
    session_id: str
    user_id: str
    query: str
    capabilities: List[AgentCapability] = field(default_factory=list)
    memory: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""


@dataclass
class AgentResponse:
    """에이전트 응답 (Agent Response)"""
    success: bool
    result: Any
    steps: List[Dict[str, Any]]
    tokens_used: int = 0
    cost: float = 0.0
    duration_ms: float = 0.0


class Context7Client:
    """Context7 MCP 클라이언트
    
    최신 라이브러리 문서를 실시간으로 가져옵니다.
    """
    
    def __init__(self, api_endpoint: str = "https://context7.upstash.io"):
        self.endpoint = api_endpoint
        self._cache: Dict[str, Dict] = {}
    
    async def get_library_docs(self, library: str, topic: str = None) -> Dict[str, Any]:
        """라이브러리 문서 조회"""
        cache_key = f"{library}:{topic or 'general'}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 시뮬레이션 (실제로는 API 호출)
        docs = {
            "library": library,
            "version": "latest",
            "topic": topic,
            "content": self._get_mock_docs(library, topic),
            "examples": self._get_mock_examples(library),
            "timestamp": datetime.now().isoformat()
        }
        
        self._cache[cache_key] = docs
        return docs
    
    def _get_mock_docs(self, library: str, topic: str) -> str:
        """모의 문서 생성"""
        docs_db = {
            "react": {
                "hooks": "React Hooks allow you to use state and lifecycle features in functional components. useState, useEffect, useContext...",
                "components": "React components are reusable UI pieces. Use functional components with hooks for modern React development."
            },
            "pandas": {
                "dataframe": "DataFrame is the primary pandas data structure. Create with pd.DataFrame(data). Key methods: head(), describe(), groupby()...",
                "series": "Series is a one-dimensional labeled array. Create with pd.Series(data, index=index)."
            },
            "langchain": {
                "agents": "LangChain agents use LLMs to determine actions. Key components: Agent, Tools, AgentExecutor...",
                "chains": "Chains combine multiple components. Use LCEL (LangChain Expression Language) for composition."
            }
        }
        
        lib_docs = docs_db.get(library.lower(), {})
        return lib_docs.get(topic, f"Documentation for {library} - {topic or 'general'}")
    
    def _get_mock_examples(self, library: str) -> List[str]:
        """모의 코드 예제 생성"""
        examples_db = {
            "react": [
                "const [count, setCount] = useState(0);",
                "useEffect(() => { fetchData(); }, [dependency]);"
            ],
            "pandas": [
                "df = pd.read_csv('data.csv')",
                "df.groupby('category').agg({'value': 'mean'})"
            ],
            "langchain": [
                "agent = create_react_agent(llm, tools, prompt)",
                "result = agent_executor.invoke({'input': query})"
            ]
        }
        return examples_db.get(library.lower(), [f"# Example for {library}"])


class PlaywrightClient:
    """Playwright MCP 클라이언트
    
    웹 브라우저를 프로그래밍 방식으로 제어합니다.
    """
    
    def __init__(self):
        self._browser = None
        self._page = None
    
    async def launch(self, headless: bool = True) -> bool:
        """브라우저 시작"""
        try:
            # 시뮬레이션 (실제로는 Playwright 호출)
            print("🌐 Browser launched (headless mode)")
            return True
        except Exception as e:
            print(f"⚠️ Browser launch failed: {e}")
            return False
    
    async def navigate(self, url: str) -> Dict[str, Any]:
        """페이지 이동"""
        print(f"📍 Navigating to: {url}")
        
        # 시뮬레이션된 페이지 정보
        return {
            "url": url,
            "title": f"Page - {url.split('/')[-1]}",
            "status": 200,
            "load_time_ms": 450
        }
    
    async def extract_content(self, selector: str = "body") -> str:
        """콘텐츠 추출"""
        return f"Extracted content from {selector}"
    
    async def screenshot(self, path: str = "screenshot.png") -> str:
        """스크린샷 저장"""
        print(f"📸 Screenshot saved: {path}")
        return path
    
    async def click(self, selector: str) -> bool:
        """요소 클릭"""
        print(f"🖱️ Clicked: {selector}")
        return True
    
    async def fill(self, selector: str, value: str) -> bool:
        """입력 필드 채우기"""
        print(f"⌨️ Filled {selector} with: {value[:20]}...")
        return True
    
    async def close(self):
        """브라우저 종료"""
        print("🔒 Browser closed")


class MemoryStore:
    """메모리 저장소 (Knowledge Graph 기반)"""
    
    def __init__(self):
        self._entities: Dict[str, Dict] = {}
        self._relations: List[Dict] = []
    
    def add_entity(self, name: str, type: str, properties: Dict = None):
        """엔티티 추가"""
        self._entities[name] = {
            "type": type,
            "properties": properties or {},
            "created_at": datetime.now().isoformat()
        }
    
    def add_relation(self, from_entity: str, relation: str, to_entity: str):
        """관계 추가"""
        self._relations.append({
            "from": from_entity,
            "relation": relation,
            "to": to_entity
        })
    
    def query(self, entity_name: str) -> Optional[Dict]:
        """엔티티 조회"""
        return self._entities.get(entity_name)
    
    def get_related(self, entity_name: str) -> List[Dict]:
        """관련 엔티티 조회"""
        related = []
        for rel in self._relations:
            if rel["from"] == entity_name:
                related.append({"relation": rel["relation"], "entity": rel["to"]})
            elif rel["to"] == entity_name:
                related.append({"relation": f"inverse_{rel['relation']}", "entity": rel["from"]})
        return related


class AdvancedMCPAgent:
    """고급 MCP 에이전트
    
    Context7 + Playwright + 지능형 라우터를 통합한 강력한 에이전트
    """
    
    def __init__(self):
        self.context7 = Context7Client()
        self.playwright = PlaywrightClient()
        self.memory = MemoryStore()
        
        # 도구 레지스트리
        self._tools: Dict[str, Callable] = {}
        self._register_default_tools()
        
        # 실행 이력
        self._execution_history: List[Dict] = []

        # DLP + SOAR lazy init
        self._dlp = None
        self._soar = None
    
    def _register_default_tools(self):
        """기본 도구 등록"""
        self._tools = {
            "get_docs":      self._tool_get_docs,
            "browse_web":    self._tool_browse_web,
            "search_web":    self._tool_search_web,
            "extract_data":  self._tool_extract_data,
            "generate_code": self._tool_generate_code,
            "analyze_data":  self._tool_analyze_data,
            "remember":      self._tool_remember,
            "recall":        self._tool_recall,
            "splunk_query":  self._tool_splunk_query,
            "supabase_query": self._tool_supabase_query,
            "datahub_query": self._tool_datahub_query,
        }
    
    async def execute(self, query: str, context: AgentContext = None) -> AgentResponse:
        """쿼리 실행"""
        from splunk_telemetry import get_telemetry
        start_time = time.time()
        steps = []

        if context is None:
            context = AgentContext(
                session_id=f"sess_{int(time.time())}",
                user_id="default",
                query=query
            )

        try:
            tel = get_telemetry()
            tel.set_session(context.session_id, context.user_id)
            tel.emit_agent_start(query)
        except Exception:
            tel = None

        try:
            if self._dlp is None:
                from enterprise_mcp_connector.dlp_policy import DLPPolicyEngine
                from security.soar_bridge import get_soar_bridge, patch_dlp_engine_with_soar
                self._dlp = DLPPolicyEngine()
                self._soar = get_soar_bridge()
                patch_dlp_engine_with_soar(self._dlp, self._soar)
        except Exception:
            self._dlp = None

        try:
            # 1. 쿼리 분석
            step1 = await self._analyze_query(query)
            steps.append({"step": "analyze", "result": step1})

            # 2. 도구 선택
            selected_tools = self._select_tools(step1)
            steps.append({"step": "select_tools", "tools": selected_tools})

            # 3. 도구 실행
            results = []
            for tool_name in selected_tools:
                if tool_name in self._tools:
                    t0 = time.time()
                    result = await self._tools[tool_name](query, context)
                    results.append({"tool": tool_name, "result": result})
                    steps.append({"step": f"execute_{tool_name}", "result": result})
                    try:
                        if self._dlp:
                            from enterprise_mcp_connector.dlp_policy import TransferDirection
                            self._dlp.scan(
                                result,
                                TransferDirection.OUTBOUND,
                                tool_name=tool_name,
                                user_id=context.user_id,
                            )
                    except Exception:
                        pass
                    try:
                        if tel:
                            tel.emit_tool_call(
                                tool_name=tool_name,
                                tool_args={"query": query},
                                result_size=len(str(result)),
                                latency_ms=(time.time() - t0) * 1000,
                                success=True
                            )
                    except Exception:
                        pass

            # 4. 결과 통합
            final_result = self._synthesize_results(query, results)
            steps.append({"step": "synthesize", "result": final_result})

            # 5. 메모리에 저장
            self.memory.add_entity(
                name=f"query_{context.session_id}",
                type="query",
                properties={"query": query, "result": str(final_result)[:500]}
            )

            duration = (time.time() - start_time) * 1000

            self._execution_history.append({
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "success": True,
                "duration_ms": duration
            })

            try:
                if tel:
                    tel.emit_agent_complete(
                        query,
                        tools_used=selected_tools,
                        total_steps=len(steps),
                        duration_ms=duration,
                        success=True
                    )
            except Exception:
                pass

            return AgentResponse(
                success=True,
                result=final_result,
                steps=steps,
                duration_ms=duration
            )

        except Exception as e:
            duration = (time.time() - start_time) * 1000
            try:
                if tel:
                    tel.emit_agent_complete(
                        query,
                        total_steps=len(steps),
                        duration_ms=duration,
                        success=False,
                        error=str(e)
                    )
            except Exception:
                pass
            return AgentResponse(
                success=False,
                result={"error": str(e)},
                steps=steps,
                duration_ms=duration
            )
    
    async def _analyze_query(self, query: str) -> Dict[str, Any]:
        """쿼리 분석"""
        query_lower = query.lower()
        
        analysis = {
            "intent": "general",
            "entities": [],
            "requires_web": False,
            "requires_docs": False,
            "requires_code": False,
            "requires_splunk": False,
            "requires_supabase": False,
        }

        # Supabase 누적 방문자 데이터 의도 (가장 구체적이므로 먼저 확인)
        supabase_keywords = [
            "방문자", "누적 방문자", "방문자 수", "누적 방문", "방문 수",
            "visitor", "visitors", "cumulative visitor", "cumulative visitors",
            "total visitors", "visitor count", "number of visitors", "supabase",
        ]
        if any(w in query_lower for w in supabase_keywords):
            analysis["intent"] = "supabase_query"
            analysis["requires_supabase"] = True
            return analysis

        # Splunk 운영 데이터 쿼리 의도 (다른 의도보다 먼저 확인)
        splunk_keywords = [
            "비용", "cost", "얼마", "지출", "spend",
            "에러", "error", "실패", "fail", "error rate",
            "dlp", "보안위반", "violation", "위반",
            "레이턴시", "latency", "느림", "slow", "응답속도",
            "캐시", "cache", "절감", "cache saving",
            "라우터", "router", "routing", "모델선택",
            "이상", "anomaly", "스파이크", "spike",
            "추세", "trend", "시간별", "hourly",
            "사용자별", "top user", "splunk",
        ]
        datahub_keywords = [
            "owner", "who owns", "lineage", "upstream", "downstream",
            "metadata", "datahub", "소유자", "리니지", "계보",
        ]
        if any(w in query_lower for w in datahub_keywords):
            analysis["intent"] = "datahub_query"
            analysis["requires_datahub"] = True
        elif any(w in query_lower for w in splunk_keywords):
            analysis["intent"] = "splunk_query"
            analysis["requires_splunk"] = True
        elif any(w in query_lower for w in ["코드", "code", "implement", "구현", "함수", "function"]):
            analysis["intent"] = "code_generation"
            analysis["requires_code"] = True
        elif any(w in query_lower for w in ["검색", "search", "find", "찾아"]):
            analysis["intent"] = "search"
            analysis["requires_web"] = True
        elif any(w in query_lower for w in ["문서", "docs", "documentation", "api", "사용법"]):
            analysis["intent"] = "documentation"
            analysis["requires_docs"] = True
        elif any(w in query_lower for w in ["분석", "analyze", "데이터", "data"]):
            analysis["intent"] = "analysis"
        
        # 엔티티 추출
        libraries = ["react", "pandas", "langchain", "numpy", "tensorflow", "pytorch"]
        for lib in libraries:
            if lib in query_lower:
                analysis["entities"].append({"type": "library", "value": lib})
        
        return analysis
    
    def _select_tools(self, analysis: Dict) -> List[str]:
        """도구 선택"""
        tools = []

        if analysis.get("requires_supabase"):
            tools.append("supabase_query")
        if analysis.get("requires_splunk"):
            tools.append("splunk_query")
        if analysis.get("requires_datahub"):
            tools.append("datahub_query")
        if analysis.get("requires_docs"):
            tools.append("get_docs")
        if analysis.get("requires_web"):
            tools.append("browse_web")
        if analysis.get("requires_code"):
            tools.append("generate_code")
        if analysis["intent"] == "analysis":
            tools.append("analyze_data")

        # 기본 도구
        if not tools:
            tools = ["recall", "generate_code"]

        return tools
    
    async def _tool_get_docs(self, query: str, context: AgentContext) -> Dict:
        """문서 조회 도구"""
        # 라이브러리 추출
        libraries = ["react", "pandas", "langchain"]
        found_lib = None
        for lib in libraries:
            if lib in query.lower():
                found_lib = lib
                break
        
        if found_lib:
            docs = await self.context7.get_library_docs(found_lib)
            return {"library": found_lib, "docs": docs}
        
        return {"message": "No specific library found in query"}
    
    async def _tool_browse_web(self, query: str, context: AgentContext) -> Dict:
        """웹 브라우징 도구"""
        await self.playwright.launch()
        
        # URL 추출 또는 검색
        if "http" in query:
            import re
            urls = re.findall(r'https?://[^\s]+', query)
            if urls:
                result = await self.playwright.navigate(urls[0])
                content = await self.playwright.extract_content()
                await self.playwright.close()
                return {"url": urls[0], "content": content, **result}
        
        # 검색 시뮬레이션
        await self.playwright.close()
        return {"action": "search", "query": query}
    
    async def _tool_search_web(self, query: str, context: AgentContext) -> Dict:
        """웹 검색 도구"""
        return {
            "query": query,
            "results": [
                {"title": f"Result 1 for {query}", "url": "https://example.com/1"},
                {"title": f"Result 2 for {query}", "url": "https://example.com/2"},
            ]
        }
    
    async def _tool_extract_data(self, query: str, context: AgentContext) -> Dict:
        """데이터 추출 도구"""
        return {"extracted": True, "data_count": 10}
    
    async def _tool_generate_code(self, query: str, context: AgentContext) -> Dict:
        """코드 생성 도구"""
        # 간단한 코드 생성 시뮬레이션
        code_templates = {
            "react": """
import React, { useState } from 'react';

function Component() {
    const [data, setData] = useState([]);
    
    return (
        <div>
            {data.map(item => <div key={item.id}>{item.name}</div>)}
        </div>
    );
}

export default Component;
""",
            "pandas": """
import pandas as pd

# Load data
df = pd.read_csv('data.csv')

# Analysis
summary = df.describe()
grouped = df.groupby('category').agg({'value': ['mean', 'sum']})

print(grouped)
""",
            "default": """
def process_data(data):
    \"\"\"Process the input data.\"\"\"
    results = []
    for item in data:
        processed = transform(item)
        results.append(processed)
    return results
"""
        }
        
        for lib, template in code_templates.items():
            if lib in query.lower():
                return {"language": lib, "code": template.strip()}
        
        return {"language": "python", "code": code_templates["default"].strip()}
    
    async def _tool_analyze_data(self, query: str, context: AgentContext) -> Dict:
        """데이터 분석 도구"""
        return {
            "analysis_type": "statistical",
            "metrics": {
                "mean": 45.6,
                "median": 42.0,
                "std": 12.3,
                "count": 1000
            }
        }
    
    async def _tool_remember(self, query: str, context: AgentContext) -> Dict:
        """기억 저장 도구"""
        self.memory.add_entity("user_preference", "preference", {"query": query})
        return {"stored": True}
    
    async def _tool_recall(self, query: str, context: AgentContext) -> Dict:
        """기억 회상 도구"""
        entity = self.memory.query("user_preference")
        return {"memory": entity}

    async def _tool_splunk_query(self, query: str, context: AgentContext) -> Dict:
        """Splunk 운영 데이터 쿼리 도구"""
        try:
            from tools.splunk_mcp_tool import SplunkMCPTool
            tool = SplunkMCPTool()
            return tool.execute(query, timerange="-1h")
        except Exception as e:
            return {"error": str(e), "results": [], "summary": "Splunk query failed"}

    async def _tool_datahub_query(self, query: str, context: AgentContext) -> Dict:
        """DataHub context-graph 쿼리 도구 (ownership/lineage/quality)"""
        try:
            from tools.datahub_mcp_tool import DataHubMCPTool
            tool = DataHubMCPTool()
            return tool.execute(query)
        except Exception as e:
            return {"error": str(e), "results": [],
                    "summary": "DataHub query failed"}

    def _guardrail_preflight(self, table: str) -> Dict:
        """Metadata guardrail before data-tool calls (degrades to allow)."""
        try:
            from security.governance_bridge import get_guardrail, get_governance_bridge
            verdict = get_guardrail().check(table)
            if verdict.action == "block" and verdict.context is not None:
                get_governance_bridge().record_block(
                    verdict.context.urn, verdict.reasons)
            return verdict.to_dict()
        except Exception as e:
            return {"action": "allow",
                    "reasons": [f"guardrail unavailable: {e}"], "context": None}

    async def _tool_supabase_query(self, query: str, context: AgentContext) -> Dict:
        """Supabase 누적 방문자 조회 도구.

        SUPABASE_URL / SUPABASE_KEY 환경변수가 설정되면 실제 Supabase REST(PostgREST)
        에서 누적(전체) 방문자 수를 집계한다. 미설정 시 데모 값으로 폴백한다.
        테이블: SUPABASE_VISITORS_TABLE(기본 visitors).
        """
        import os

        url   = os.getenv("SUPABASE_URL", "").rstrip("/")
        key   = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
        table = os.getenv("SUPABASE_VISITORS_TABLE", "visitors")

        guardrail = self._guardrail_preflight(table)
        if guardrail["action"] == "block":
            owners = (guardrail.get("context") or {}).get("owners") or []
            return {
                "source": "guardrail", "metric": "cumulative_visitors",
                "count": None, "guardrail": guardrail,
                "summary": (f"Blocked by metadata guardrail: "
                            f"{'; '.join(guardrail['reasons'])}. "
                            f"Contact owner: {', '.join(owners) or 'unknown'}."),
            }

        if not url or not key:
            import random
            n = random.randint(5000, 50000)
            return {
                "source": "demo", "metric": "cumulative_visitors",
                "count": n, "table": table, "guardrail": guardrail,
                "summary": (f"[Demo] Cumulative visitors: {n:,} "
                            f"(SUPABASE_URL/KEY not set — simulated). "
                            f"Real data: set env vars; total rows in {table}."),
            }

        try:
            import requests
            r = requests.get(
                f"{url}/rest/v1/{table}",
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Prefer": "count=exact",
                    "Range": "0-0",
                },
                params={"select": "*"},
                timeout=10,
            )
            total = None
            cr = r.headers.get("content-range", "")
            if "/" in cr:
                tail = cr.split("/")[-1]
                if tail.isdigit():
                    total = int(tail)
            if total is None:
                try:
                    total = len(r.json())
                except Exception:
                    total = 0
            return {
                "source": "supabase", "metric": "cumulative_visitors",
                "count": total, "table": table, "guardrail": guardrail,
                "summary": f"Cumulative visitors: {total:,} (Supabase {table}).",
            }
        except Exception as e:
            return {
                "source": "error", "metric": "cumulative_visitors",
                "count": None, "error": str(e),
                "summary": f"Supabase query failed: {e}",
            }

    def _synthesize_results(self, query: str, results: List[Dict]) -> Dict:
        """결과 통합"""
        synthesized = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "tool_results": results,
            "summary": f"Processed query with {len(results)} tools"
        }
        
        # 코드가 있으면 강조
        for r in results:
            if "code" in r.get("result", {}):
                synthesized["generated_code"] = r["result"]["code"]
                break
        
        # 문서가 있으면 추가
        for r in results:
            if "docs" in r.get("result", {}):
                synthesized["documentation"] = r["result"]["docs"]
                break

        # 방문자 등 요약 답변이 있으면 상단 응답으로 노출
        for r in results:
            res = r.get("result", {})
            if isinstance(res, dict) and res.get("metric") == "cumulative_visitors":
                synthesized["response"] = res.get("summary", "")
                break

        return synthesized
    
    def get_execution_history(self, limit: int = 10) -> List[Dict]:
        """실행 이력 조회"""
        return self._execution_history[-limit:]


# === 테스트 ===
async def test_advanced_agent():
    """고급 에이전트 테스트"""
    print("=" * 60)
    print("🤖 Advanced MCP Agent Test")
    print("=" * 60)
    
    agent = AdvancedMCPAgent()
    
    test_queries = [
        "React hooks 사용법을 알려주고 예제 코드를 만들어줘",
        "pandas로 데이터 분석하는 코드를 작성해줘",
        "langchain agent 문서를 찾아줘",
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: {query}")
        print("-" * 50)
        
        response = await agent.execute(query)
        
        print(f"✅ Success: {response.success}")
        print(f"⏱️ Duration: {response.duration_ms:.1f}ms")
        print(f"📊 Steps: {len(response.steps)}")
        
        if "generated_code" in response.result:
            print(f"\n💻 Generated Code:")
            print(response.result["generated_code"][:300] + "...")
        
        if "documentation" in response.result:
            print(f"\n📚 Documentation found")
    
    print("\n" + "=" * 60)
    print("✅ Advanced Agent Test Complete!")


if __name__ == "__main__":
    asyncio.run(test_advanced_agent())
