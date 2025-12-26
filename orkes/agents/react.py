from typing import TypedDict, List, Dict, Optional, Callable
from orkes.graph.core import OrkesGraph
from orkes.services.schema import LLMInterface
from orkes.shared.schema import OrkesToolSchema, OrkesMessagesSchema, OrkesMessageSchema
from orkes.agents.schema import Agent
import asyncio

class ReactAgentState(TypedDict):
    """
    The state for the ReAct agent's internal graph.
    """
    query: str
    messages: OrkesMessagesSchema
    max_iterations: int
    current_iteration: int
    final_answer: Optional[str]
    # To store the tool calls from the LLM's response
    tool_calls: Optional[List[Dict]]

class ReactAgent(Agent):
    """
    A ReAct (Reasoning and Acting) agent that uses an OrkesGraph to orchestrate its execution.
    """
    def __init__(self, llm: LLMInterface, tools: List[OrkesToolSchema], name: str = "ReactAgent", trace_mode: str = "none"):
        super().__init__(name, llm)
        self.tools = {tool.name: tool for tool in tools}
        self.trace_mode = trace_mode
        self.graph = self._build_graph()

    def _build_graph(self) -> OrkesGraph:
        """
        Builds the internal OrkesGraph for the ReAct loop.
        """
        graph = OrkesGraph(state=ReactAgentState, name=f"{self.name}_Graph")

        graph.add_node("reason_and_act", self._reason_and_act)
        graph.add_node("execute_tool", self._execute_tool)

        graph.add_edge(graph.START, "reason_and_act")
        
        graph.add_conditional_edge("reason_and_act", self._decide_next_step, {
            "tool_call": "execute_tool",
            "finish": "END",
        })
        
        graph.add_edge("execute_tool", "reason_and_act")

        app = graph.compile()
        app.auto_save_trace = (self.trace_mode == "all") # Set auto_save_trace based on trace_mode
        return app

    def invoke(self, query: str, max_iterations: int = 5) -> str:
        """
        Invokes the agent with a query.
        """
        initial_state = {
            "query": query,
            "messages": OrkesMessagesSchema(messages=[OrkesMessageSchema(role="user", content=query)]),
            "max_iterations": max_iterations,
            "current_iteration": 0,
            "final_answer": None,
            "tool_calls": None
        }
        
        final_state = self.graph.run(initial_state)

        if self.trace_mode == "all":
            self.graph.visualize_trace()
        
        return final_state.get('final_answer', "No answer found.")

    async def ainvoke(self, query: str, max_iterations: int = 5) -> str:
        """
        Asynchronously invokes the agent with a query.
        """
        initial_state = {
            "query": query,
            "messages": OrkesMessagesSchema(messages=[OrkesMessageSchema(role="user", content=query)]),
            "max_iterations": max_iterations,
            "current_iteration": 0,
            "final_answer": None,
            "tool_calls": None
        }
        
        final_state = await asyncio.to_thread(self.graph.run, initial_state)
        
        return final_state.get('final_answer', "No answer found.")

    # --- Node Functions for the Graph ---

    def _reason_and_act(self, state: ReactAgentState) -> Dict:
        """
        Calls the LLM to get the next action or final answer.
        """
        # Reset tool calls from previous iteration
        state['tool_calls'] = None

        tool_schemas = list(self.tools.values())
        
        response = self.llm_interface.send_message(state['messages'], tools=tool_schemas)
        
        content_type = response['content'].get("content_type")
        content = response['content'].get("content")

        if content_type == "tool_calls":
            state['tool_calls'] = content
            # Add the assistant's tool call message to the history
            assistant_message = OrkesMessageSchema(role="assistant", content=content, content_type="tool_calls")
            state['messages'].messages.append(assistant_message)
        else:
            state['final_answer'] = content
        
        return state

    def _execute_tool(self, state: ReactAgentState) -> Dict:
        """
        Executes the tool specified by the LLM.
        """
        if not state.get('tool_calls'):
            return state

        for tool_call in state['tool_calls']:
            tool_name = tool_call['function_name']
            tool_args = tool_call['arguments']
            
            if tool_name in self.tools:
                # Assuming the tools are simple functions for now
                # A more robust implementation would handle tools that are classes or have complex dependencies
                tool_function = self.tools[tool_name].function
                
                try:
                    # In a real scenario, you'd want to serialize the output properly
                    tool_output = tool_function(**tool_args)
                    
                    tool_message = OrkesMessageSchema(
                        role="tool",
                        content=str(tool_output),
                        tool_call_id=tool_call.get('id', '') # Assuming the LLM provides an ID for the tool call
                    )
                    state['messages'].messages.append(tool_message)

                except Exception as e:
                    error_message = OrkesMessageSchema(
                        role="tool",
                        content=f"Error executing tool {tool_name}: {e}",
                        tool_call_id=tool_call.get('id', '')
                    )
                    state['messages'].messages.append(error_message)
            else:
                error_message = OrkesMessageSchema(
                    role="tool",
                    content=f"Tool '{tool_name}' not found.",
                    tool_call_id=tool_call.get('id', '')
                )
                state['messages'].messages.append(error_message)

        # Clear tool_calls after execution
        state['tool_calls'] = None
        
        return state
    
    # --- Gate Function for Conditional Edge ---

    def _decide_next_step(self, state: ReactAgentState) -> str:
        """
        Decides whether to call a tool, finish, or continue.
        """
        state['current_iteration'] += 1
        if state['current_iteration'] > state['max_iterations']:
            # Force finish if max iterations reached
            state['final_answer'] = "Max iterations reached. Could not find an answer."
            return "finish"
            
        if state.get('tool_calls'):
            return "tool_call"
        else:
            return "finish"
