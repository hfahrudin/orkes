from orkes.services.connections import LLMInterface
from orkes.services.prompts import PromptInterface
from orkes.agents.actions import ActionBuilder
from abc import ABC, abstractmethod
from orkes.services.responses import ResponseInterface
from typing import Dict, List
import json

class AgentInterface(ABC):

    @abstractmethod
    def invoke(self, queries, chat_history):
        """Invoke the agent with a message."""
        pass

    @abstractmethod
    async def stream(self, queries, chat_history, **kwargs):
        """Invoke the agent with streaming."""
        pass

class Agent(AgentInterface):
    def __init__(self, name: str, prompt_handler: PromptInterface, 
                 llm_connection: LLMInterface, response_handler: ResponseInterface):
        self.name = name
        self.prompt_handler = prompt_handler
        self.llm_handler = llm_connection
        self.response_handler = response_handler
        self.query_keys = self.prompt_handler.get_all_keys()
        self.buffer_size = 0

    def invoke(self, queries, chat_history=None):
        message = self.prompt_handler.gen_messages(queries, chat_history)
        response = self.llm_handler.send_message(message)
        response_json = response.json()
        return response_json

    #TODO: ITS NOT WORKING STILL
    async def stream(self, queries, chat_history=None, stream_buffer=False, client_connection=None):
        message = self.prompt_handler.gen_messages(queries, chat_history)
        yield message
        async for chunk in self.llm_handler.stream_message(message):
            text_delta = self.response_handler.parse_stream_response(chunk)
            
            # if stream_buffer and client_connection:
            #     await client_connection(text_delta)  # send incremental update
            
            yield text_delta  # optionally yield for other 
    
class ToolAgent(AgentInterface):
    def __init__(self, name: str, llm_connection: LLMInterface):
        self.name = name
        self.llm_handler = llm_connection
        self.tools: Dict[str, ActionBuilder] = {}

        self.default_system_prompt =  (
            "<|start_of_role|>system<|end_of_role|>\n"
            "You are an AI assistant with access to a set of tools that can help answer user queries.\n\n"
            "When a tool is required to answer the user's query, respond with <|tool_call|> "
            "followed by a JSON list of tools used.\n\n"
            "If a tool does not exist in the provided list of tools, notify the user that you do not have the ability to fulfill the request.\n"
            "<|end_of_text|>"
        )

        self.default_tools_wrapper = {
            "start_token" : "<|start_of_role|>tools<|end_of_role|>",
            "end_token" : "<|end_of_text|>"

        }

    def add_tools(self, actions: List[ActionBuilder]):
        for action in actions:
            if not isinstance(action, ActionBuilder):
                raise TypeError("add_tools expects an ActionBuilder instance")
            if action.func_name in self.tools:
                raise ValueError(f"Tool with name '{action.func_name}' already exists")
            self.tools[action.func_name] = action

    def _build_tools_prompt(self):
        """
        Build a full prompt including the default system instructions
        and the current list of tools in JSON format.
        
        Returns:
            str: formatted prompt for the LLM
        """
        # Start with the default system prompt
        prompt = self.default_system_prompt.strip() + "\n\n"

        # Add the tools JSON block with wrapper tokens
        start_token = self.default_tools_wrapper["start_token"]
        end_token = self.default_tools_wrapper["end_token"]

        tool_schemas = [tool.get_schema_tool() for tool in self.tools.values()]
        tool_schemas_string = json.dumps(tool_schemas, indent=4)

        tools_block = f"{start_token}\n{tool_schemas_string}\n{end_token}"

        return prompt + tools_block
    
    def invoke(self, queries, chat_history=None):

        return 1
    
    async def stream(self, queries, chat_history=None, stream_buffer=False, client_connection=None):
        return 1