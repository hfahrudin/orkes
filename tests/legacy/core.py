from orkes.services.connectors import LLMInterface
from orkes.services.prompts import PromptInterface
from orkes.agents.actions import ActionBuilder
from orkes.services.prompts import ChatPromptHandler

from orkes.services.responses import ResponseInterface
from typing import Dict, List
import json
from requests import Response
import re
from orkes.agents.schema import AgentInterface


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


    async def stream(self, queries, chat_history=None, client_connection=None, mode="default"):
        message = self.prompt_handler.gen_messages(queries, chat_history)
        async for chunk in self.llm_handler.stream_message(message):
            if mode == 'default':
                text_delta = self.response_handler.parse_stream_response(chunk)
            elif mode == 'raw':
                text_delta = chunk
            elif mode == 'sse':
                text_delta = self.response_handler.parse_stream_response(chunk, sse=True)
            
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
            "followed by a list of tools used.\n\n"
            "Each tool call must have this exact structure:\n"
            "{\n"
            "  \"function\": <function_name_as_string>,\n"
            "  \"parameters\": { <parameter_name>: <value>, ... }\n"
            "}\n"
            "Do NOT add any extra text or fields.\n"
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
    
    def invoke(self, query, chat_history=None, execute_tools=False):
        system_prompt="{tools}"
        user_prompt="{input}"
        queries = {
            "system" : {"tools" : self._build_tools_prompt()},
            "user" : {"input" : query}
        }
        cP = ChatPromptHandler(system_prompt_template=system_prompt, user_prompt_template=user_prompt)
        message = cP.gen_messages(queries, chat_history)
        response = self.llm_handler.send_message(message)
        tools_called = self._parse_tool_response(response)
        if execute_tools:
            result = {}
            for tool_call in tools_called:
                tool_name = tool_call["function"]
                params = tool_call["parameters"]
                if tool_name in self.tools:
                    tool = self.tools[tool_name]
                    try:
                        tool_result =  tool.execute(params)
                        result[tool_name] = tool_result
                    except Exception as e:
                        result[tool_name] = f"Error executing tool '{tool_name}': {str(e)}"
                else:
                    result[tool_name] = f"Tool '{tool_name}' not found"
            return result
        
        return tools_called
    

    def _parse_tool_response(self, response: Response):
        """
        Parse LLM response for tool calls and normalize them.
        Accepts both:
        1) {'type': 'function', 'function': {'name': '...', 'parameters': {...}}}
        2) {'function': '...', 'parameters': {...}}
        """
        response_json = response.json()
        content = response_json['choices'][0]['message']['content']
        content = re.sub(r"<\|.*?\|>", "", content).strip()
        # Extract JSON array from text
        tool_calls = []
        try:
            candidate_calls = json.loads(content)
        except json.JSONDecodeError:
            candidate_calls = []

        for call in candidate_calls:
            # Case 1: nested 'function' dict
            if isinstance(call.get("function"), dict):
                func = call["function"]
                if "name" in func and "parameters" in func:
                    tool_calls.append({
                        "function": func["name"],
                        "parameters": func["parameters"]
                    })
            # Case 2: simple format
            elif "function" in call and "parameters" in call:
                tool_calls.append({
                    "function": call["function"],
                    "parameters": call["parameters"]
                })

        return tool_calls
