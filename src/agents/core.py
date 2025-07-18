from services.connections import LLMInterface
from services.prompts import PromptInterface
from agents.actions import ActionBuilder
from abc import ABC, abstractmethod
from services.responses import ResponseInterface
from typing import Dict
import json

class AgentInterface(ABC):

    @abstractmethod
    def invoke(self, queries, chat_history):
        """Invoke the agent with a message."""
        pass

    @abstractmethod
    def stream(self, queries, chat_history, **kwargs):
        """Invoke the agent with streaming."""
        pass

    @abstractmethod
    def add_tools(self, **kwargs):
        """Invoke the agent with a message."""
        pass

class Agent(AgentInterface):
    def __init__(self, name: str, prompt_handler: PromptInterface, llm_connection: LLMInterface, response_handler: ResponseInterface ):
        #TODO: Xgrammar integration
        self.name = name
        self.prompt_handler = prompt_handler
        self.llm_handler = llm_connection
        self.response_handler = response_handler
        self.tools: Dict[str, ActionBuilder] = {}
        self.query_keys = self.prompt_handler.get_all_keys()
        self.buffer_size = 0
    
    def add_tools(self, function_name, description, properties):
        action = ActionBuilder(func_name=function_name, description=description)
        action.build(params=properties)
        self.tools[function_name] = action

    def _build_tools_prompt(self, start_token = "<|start_of_role|>tools<|end_of_role|>", end_token= "<|end_of_text|>"):

        tool_schemas = []

        for k, action in self.tools.items():
            tool_schemas.append(action.get_schema_tool())

        tool_schemas_string = json.dumps(tool_schemas, indent=4)

        tools_prompt = f"{start_token}\n{tool_schemas_string}\n{end_token}"

        return tools_prompt

    def invoke(self, queries, chat_history=None):
        message = self.prompt_handler.gen_messages(queries, chat_history)
        response = self.llm_handler.send_message(message)
        response_json = response.json()
        return self.response_handler.parse_full_response(response_json)

    def stream(self, queries, chat_history=None, stream_buffer=False, client_connection=None):
        #TODO: Properly Implement Async for steamBuffer feature, the infrastructure should work. 
        message = self.prompt_handler.gen_messages(queries, chat_history)
        # bufferer = StreamResponseBuffer(llm_response=self.response_handler)
        response = self.llm_handler.stream_message(message)
        # bufferer.stream(response=response, buffer_size=self.buffer_size, trigger_connection=client_connection)
        return response,  self.response_handler.parse_stream_response
