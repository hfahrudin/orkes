from orkes.graph.core import OrkesGraph
from orkes.services.connectors import LLMFactory
from orkes.shared.schema import OrkesMessagesSchema
from typing import TypedDict, List
import json
from dotenv import load_dotenv
import os

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")

llm_client = LLMFactory.create_openai(api_key=openai_api_key)

class SearchState(TypedDict):
    user_query: str
    search_queries: List[str]
    current_index: int
    raw_results: List[str]
    is_finished: bool
    final_answer: str
# --- Node 1: LLM Planner ---
def planner_node(state: SearchState):
    """LLM looks at the user query and generates a list of 3 search queries."""
    prompt = (
        f"The user wants to know: {state['user_query']}\n"
        "Break this down into few specific search queries to gather comprehensive data. "
        "Return the response as a JSON list of strings only. Example: [\"query1\", \"query2\"]"
    )
    
    messages = OrkesMessagesSchema(messages=[{"role": "user", "content": prompt}])
    response = llm_client.send_message(messages)
    
    # Extract content using your provided parsing logic
    content = response.get('raw', {}).get('choices', [{}])[0].get('message', {}).get('content')
    
    # Parse the JSON string into a Python list
    try:
        # Removing potential markdown code blocks if the LLM adds them
        clean_content = content.replace("```json", "").replace("```", "").strip()
        state['search_queries'] = json.loads(clean_content)
    except Exception as e:
        print(f"Error parsing LLM response: {e}")
        state['search_queries'] = [state['user_query']] # Fallback to original query
        
    state['current_index'] = 0
    state['raw_results'] = []
    print(f"📋 Planner generated queries: {state['search_queries']}")
    return state

# --- Node 2: Search Execution ---
def execute_search_node(state: SearchState):
    idx = state['current_index']
    query = state['search_queries'][idx]
    
    print(f"📡 Searching for ({idx+1}/{len(state['search_queries'])}): {query}")
    
    # Simulating a search result (Replace with actual API call like Google/Tavily)
    state['raw_results'].append(f"Source {idx+1} result for '{query}': [Simulated Data Content]")
    
    state['current_index'] += 1
    state['is_finished'] = state['current_index'] >= len(state['search_queries'])
    return state

# --- Node 3: Final LLM Synthesis ---
def synthesis_node(state: SearchState):
    context = "\n".join(state['raw_results'])
    prompt = f"Using this data:\n{context}\n\nAnswer: {state['user_query']}"
    
    messages = OrkesMessagesSchema(messages=[{"role": "user", "content": prompt}])
    response = llm_client.send_message(messages)
    
    #TESTING DOUBLE TRACE
    messages2 = OrkesMessagesSchema(messages=[{"role": "user", "content": prompt}])
    _ = llm_client.send_message(messages2)

    state['final_answer'] = response.get('raw', {}).get('choices', [{}])[0].get('message', {}).get('content')
    print(f"\n✨ Final Answer:\n{state['final_answer']}")
    return state

def retrieval_consolidator(state: SearchState):

    return state

# --- Router Logic ---
def check_loop_condition(state: SearchState):
    return 'complete' if state.get('is_finished') else 'loop'

# --- Build the Graph ---
graph = OrkesGraph(SearchState)

graph.add_node('planner', planner_node)
graph.add_node('search_step', execute_search_node)
graph.add_node('synthesizer', synthesis_node)
graph.add_node('consolidate', retrieval_consolidator)

graph.add_edge(graph.START, 'planner')
graph.add_edge('planner', 'search_step')
graph.add_edge('consolidate', 'search_step')

# Loop logic
graph.add_conditional_edge(
    'search_step',
    check_loop_condition,
    {
        'loop': 'consolidate',
        'complete': 'synthesizer'
    }
)

graph.add_edge('synthesizer', graph.END)

# --- Execute ---
runner = graph.compile()
initial_state: SearchState = {
    "user_query": "What are the key differences between Orkes Conductor and Temporal?",
    "search_queries": [],
    "current_index": 0,
    "raw_results": [],
    "is_finished": False,
    "final_answer": ""
}

runner.run(initial_state)

runner.visualize_trace()
