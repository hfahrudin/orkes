from duckduckgo_search import DDGS
#FOR LOCAL TESTING
import sys
import os
from prompt_test import *
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orkes.graph.core import OrkesGraph
from typing import TypedDict
from orkes.agents.core import Agent, ToolAgent
from orkes.agents.actions import ActionBuilder
from orkes.services.connectors import vLLMConnection
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
    final_recommendations: list
    feedback: str
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
def action_node(state: State):
    plans = state['plan']
    feedback = state["feedback"]
    for p in plans:
        agent = p["agent"]
        task = p["task"]
        if agent == "SearchEngine":
            query, search_results = search_engine_agent(task, feedback) 
            state['search_results'].append({
                "task" : task,
                "query" : query,
                "search_result" : search_results
            })
    return state


def search_engine_agent(task, feedback):
    """
    Executes the plan using ToolAgent with a single search tool.
    Uses DuckDuckGo Search (DDGS) to gather information according to the plan.
    """
    cR = ChatResponse()
    cP = ChatPromptHandler(system_prompt_template=action_prompt_system, user_prompt_template=action_prompt_input)
    queries = {
        "system" : {
        },
        "user" : {
            "task" : task,
            "feedback" : feedback
        }
    }
    planner_agent = Agent(name="agent_1", prompt_handler=cP, llm_connection=connection, response_handler=cR)
    res = planner_agent.invoke(queries=queries)
    raw = res["choices"][0]['message']['content']
    cleaned_res = extract_json(raw)
    query = cleaned_res['query']
    search_results = search(query)
    return query, search_results

#Eval Node
def eval_node(state: State):
    search_results = state['search_results']
    cR = ChatResponse()
    cP = ChatPromptHandler(system_prompt_template=eval_prompt_system, user_prompt_template=eval_prompt_input)
    queries = {
        "system" : {
        },
        "user" : {
            "results" : search_results
        }
    }
    planner_agent = Agent(name="agent_2", prompt_handler=cP, llm_connection=connection, response_handler=cR)
    res = planner_agent.invoke(queries=queries)
    raw = res["choices"][0]['message']['content']
    cleaned_res = extract_json(raw)

    need_additional_search = cleaned_res['need_additional_search']
    feedback = cleaned_res['feedback']

    if need_additional_search:
        state["status"] = "RETRY"
        state["feedback"] =feedback
    else:
        state['status'] = "DONE"
    
    return state

def conditional_node(state: State):
    # Example: check the condition_result
    if state.get('status') == 'DONE':
        return 'DONE'   # name of the next node if condition is True
    else:
        return 'RETRY'  # name o
    
def exit_node(state: State):
    search_results = state['search_results']
    cR = ChatResponse()
    cP = ChatPromptHandler(system_prompt_template=final_recom_prompt_system, user_prompt_template=final_recom_input)
    queries = {
        "system" : {
        },
        "user" : {
            "results" : search_results
        }
    }

    planner_agent = Agent(name="agent_2", prompt_handler=cP, llm_connection=connection, response_handler=cR)
    res = planner_agent.invoke(queries=queries)
    raw = res["choices"][0]['message']['content']
    final_recommendations = extract_json(raw)

    state['final_recommendations'] = final_recommendations
    return state

# ------------------ Graph Definition ------------------ #

#INIT GRAPH
agent_graph = OrkesGraph(State)
START_node = agent_graph.START
END_node = agent_graph.END

agent_graph.add_node('action_node', action_node)
agent_graph.add_node('planner_node', planner_node)
agent_graph.add_node('eval_node', eval_node)
agent_graph.add_node('exit_node', exit_node)

agent_graph.add_edge(START_node, 'planner_node', max_passes=5)
agent_graph.add_edge('planner_node', 'action_node', max_passes=5)
agent_graph.add_edge('action_node', 'eval_node', max_passes=5)
agent_graph.add_conditional_edge('eval_node', conditional_node, {'DONE' : 'exit_node', 'RETRY' : 'action_node'}, max_passes=5)
agent_graph.add_edge('exit_node', END_node)

runner = agent_graph.compile()

# ------------------ Test Execution ------------------ #

query = "recommend me some anime similar to Inuyasha"

user_profile = {
    "favorite_genres": ["Fantasy", "Adventure", "Romance"],
    "watched_anime": ["Naruto", "Bleach", "Inuyasha"],
    "preferred_length": "short_to_medium"
}

state = {
    "query": query,
    "user_profile": user_profile,
    "search_results": [],
    "final_recommendations": [],
    "feedback" : "",
    "plan" : [],
    "status" : "DONE"
}

result= runner.run(state)
