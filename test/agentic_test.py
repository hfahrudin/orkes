from duckduckgo_search import DDGS
#FOR LOCAL TESTING
import sys
import os
from prompt_test import planner_prompt_system, planner_prompt_input
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orkes.graph.core import OrkesGraph
from typing import TypedDict
from orkes.agents.core import Agent
from orkes.services.connections import vLLMConnection
from orkes.services.prompts import ChatPromptHandler
from orkes.services.responses import ChatResponse
import json
import re

# ------------------ Utils Definition ------------------ #

def extract_json(raw_text):
    """
    Extract and parse JSON from a string that may contain
    markdown code fences or extra characters.
    
    Args:
        raw_text (str): Input string containing JSON.
        
    Returns:
        dict: Parsed JSON object.
    """
    # Remove markdown code fences if present
    cleaned = re.sub(r"```json\s*|```", "", raw_text, flags=re.IGNORECASE).strip()
    
    # Parse the cleaned JSON string
    return json.loads(cleaned)

# ------------------ State Definition ------------------ #

# Define the state structure
class State(TypedDict):
    query: str
    user_profile: dict
    search_results: list
    filtered_results: list
    ranked_results: list
    personalized_evaluation: dict
    final_recommendations: list
    tools: list
    plan :list
    status: str

connection = vLLMConnection()

# ------------------ Action Definition ------------------ #

# Minimal search function
def search(query, max_results=10):
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append(r)
    return results


# ------------------ Node Definition ------------------ #

#Entry Node
def entry_node(state: State):
    result = state.get('initial', 0) + 3
    state['add_result'] = result
    return state

#Planner Node
def planner_node(state: State):
    cR = ChatResponse()
    cP = ChatPromptHandler(system_prompt_template=planner_prompt_system, user_prompt_template=planner_prompt_input)
    user_profile = state['user_profile']
    queries = {
        "system" : {
            "genre" : user_profile["favorite_genres"],
            "watched_anime" : user_profile["watched_anime"],
            "preferred_length" : user_profile["preferred_length"],
            "query" : "recommend me some anime similar to Inuyasha"
        },
        "user" : {
        }
    }
    planner_agent = Agent(name="agent_0", prompt_handler=cP, llm_connection=connection, response_handler=cR)
    res = planner_agent.invoke(queries=queries)
    raw = res["choices"][0]['message']['content']
    plan = extract_json(raw)
    state['plan'] = plan
    return state


#Action Node -> Search Queries, Result Aggregation, and Recommendation

#Eval Node

#Exit Node


# ------------------ Graph Definition ------------------ #

#INIT GRAPH
agent_graph = OrkesGraph(State)
START_node = agent_graph.START
END_node = agent_graph.END

#Entry Node -> Planner Node

# Planner Node -> Action Node

# Action Node -> Eval Node

# Eval Node -> Planner Node or Exit Node


# ------------------ Test Execution ------------------ #


query = "recommend me some anime similar to Inuyasha"
user_profile = {
    "favorite_genres": ["Fantasy", "Adventure", "Romance"],
    "watched_anime": ["Naruto", "Bleach", "Inuyasha"],
    "preferred_length": "short_to_medium"
}

planner_context = {
    "user_query": query,
    "user_profile": user_profile,
    "available_tools": ["DDGS_search", "filter_and_rank", "evaluate_personalization", "format_response"],
    "goals": "Recommendations must be personalized and avoid duplicates, present at least 3 results, and rank by genre similarity.",
    "output_format": "JSON plan for action agent execution"
}
