import os
import pytest
import asyncio
from typing import TypedDict, Dict

from orkes.graph.core import OrkesGraph
from orkes.services.connectors import LLMFactory
from orkes.shared.schema import OrkesMessagesSchema, OrkesMessageSchema
from dotenv import load_dotenv
from functools import partial

# 1. Define the state for the race condition test
class RaceConditionState(TypedDict):
    run_id: str
    llm_output: str

# 2. Define the node function that calls the LLM
def llm_node(state: RaceConditionState, api_key: str) -> Dict:
    """
    This node function simulates calling a live LLM.
    It passes the run_id to the LLM and stores the output.
    """
    llm_client = LLMFactory.create_openai(api_key=api_key)
    
    messages = OrkesMessagesSchema(messages=[
        OrkesMessageSchema(role="user", content=f"Echo back the following identifier: {state['run_id']}")
    ])
    
    response = llm_client.send_message(messages)
    
    state['llm_output'] = response['content'].get('content', '')
    
    return state

# 3. Define the integration test
@pytest.mark.asyncio
async def test_llm_trace_race_condition_live():
    """
    Tests for race conditions in LLM tracing by running five graphs concurrently
    against a live OpenAI API.
    """
    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not found. Skipping live race condition test.")

    num_concurrent_runs = 5
    apps = []
    
    # Create graph definitions
    def create_graph(name: str):
        graph = OrkesGraph(state=RaceConditionState, name=name)
        node_with_key = partial(llm_node, api_key=openai_api_key)
        graph.add_node("LLM_NODE", node_with_key)
        graph.add_edge(graph.START, "LLM_NODE")
        graph.add_edge("LLM_NODE", graph.END)
        app = graph.compile()
        app.auto_save_trace = True
        return app

    for i in range(num_concurrent_runs):
        apps.append(create_graph(f"graph{i+1}"))

    # Define async functions to run the graphs
    async def run_graph(app, run_id):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, app.run, {"run_id": run_id, "llm_output": ""})

    # Create tasks for concurrent execution
    tasks = []
    for i, app in enumerate(apps):
        tasks.append(run_graph(app, f"run{i+1}"))

    # Run the graphs concurrently
    await asyncio.gather(*tasks)

    # --- Assertions ---
    
    trace_files = [f"traces/trace_{app.run_id}.json" for app in apps]
    viz_files = [f"traces/trace_{app.run_id}_inspector.html" for app in apps]

    try:
        for i, app in enumerate(apps):
            run_id = f"run{i+1}"
            trace = app.trace
            
            edge_with_llm_trace = next((edge for edge in trace.edges_trace if edge.llm_traces), None)
            assert edge_with_llm_trace is not None, f"Graph {run_id} should have an edge with LLM traces"
            
            assert len(edge_with_llm_trace.llm_traces) == 1, f"Graph {run_id}'s LLM edge should have 1 trace"

            llm_trace = edge_with_llm_trace.llm_traces[0]
            response_content = llm_trace.parsed_response.content
            
            assert run_id in response_content, f"Graph {run_id}'s trace should contain '{run_id}'"
            
            # Check for leakage from other runs
            for j in range(num_concurrent_runs):
                other_run_id = f"run{j+1}"
                if i != j:
                    assert other_run_id not in response_content, f"Graph {run_id}'s trace should not contain '{other_run_id}'"
    finally:
        # Clean up the generated files
        for trace_file in trace_files:
            if os.path.exists(trace_file):
                os.remove(trace_file)
        for viz_file in viz_files:
            if os.path.exists(viz_file):
                os.remove(viz_file)
