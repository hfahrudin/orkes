from services.connections import LLMInterface
from services.prompts import PromptInterface
from abc import ABC, abstractmethod
from services.responses import ResponseInterface, StreamResponseBuffer

class AgentInterface(ABC):

    @abstractmethod
    def invoke(self, queries, chat_history):
        """Invoke the agent with a message."""
        pass

    @abstractmethod
    def stream(self, queries, chat_history, **kwargs):
        """Invoke the agent with a message."""
        pass
    

class Agent(AgentInterface):
    def __init__(self, name: str, prompt_handler: PromptInterface, llm_connection: LLMInterface, response_handler: ResponseInterface ):
        self.name = name
        self.prompt_handler = prompt_handler
        self.llm_handler = llm_connection
        self.response_handler = response_handler
        self.tools = []
        self.query_keys = self.prompt_handler.get_all_keys()
        self.buffer_size = 0
    
    # def add_tools():
    #     pass


    def invoke(self, queries, chat_history=None):
        message = self.prompt_handler.gen_messages(queries, chat_history)
        response = self.llm_handler.send_message(message)
        response_json = response.json()
        return response_json

    def stream(self, queries, chat_history=None, stream_buffer=False, client_connection=None):
        #TODO: Properly Implement Async def, the infrastructure should work.
        message = self.prompt_handler.gen_messages(queries, chat_history)
        bufferer = StreamResponseBuffer(llm_response=self.response_handler)
        response = self.llm_handler.stream_message(message)
        bufferer.stream(response=response, buffer_size=self.buffer_size, trigger_connection=client_connection)
