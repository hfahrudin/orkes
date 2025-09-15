from duckduckgo_search import DDGS
#FOR LOCAL TESTING
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orkes.graph.core import OrkesGraph
from typing import TypedDict


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

#Planner Node

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
