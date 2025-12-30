import string
from abc import ABC, abstractmethod
from requests import Response

class PromptInterface(ABC):
    """
    An interface for prompt handlers, defining the methods that all prompt handlers
    must implement.
    """
    @abstractmethod
    def gen_messages(self, queries: dict, chat_history: list = None) -> list:
        """
        Generates a list of messages for the LLM based on the given queries and chat
        history.

        Args:
            queries (dict): A dictionary containing the queries for the system and user
                          prompts.
            chat_history (list, optional): A list of previous chat messages. Defaults
                                         to None.

        Returns:
            list: A list of messages ready to be sent to the LLM.
        """
        pass

    @abstractmethod
    def get_all_keys(self) -> dict:
        """
        Returns a dictionary of all the keys used in the system and user prompt
        templates.

        Returns:
            dict: A dictionary with 'system' and 'user' keys, each containing a list
                  of keys used in their respective prompt templates.
        """
        pass

class ChatPromptHandler(PromptInterface):
    """
    A prompt handler for chat-based interactions with an LLM.

    This class takes system and user prompt templates and generates a list of
    messages that can be sent to an LLM. It supports filling in the templates
    with dynamic values and can incorporate chat history.

    Attributes:
        system_prompt_template (str): The template for the system prompt.
        user_prompt_template (str): The template for the user prompt.
    """
    def __init__(self, system_prompt_template: str, user_prompt_template: str):
        """
        Initializes the ChatPromptHandler.

        Args:
            system_prompt_template (str): The template for the system prompt.
                Example: "{persona}. You must acknowledge that an exact match could not be
                found in your knowledge database."
            user_prompt_template (str): The template for the user prompt.
                Example: "{language}{input}, do not give out any external link"
        """
        self.system_prompt_template = system_prompt_template
        self.user_prompt_template = user_prompt_template
        self._tools_prompt = None
        
    def gen_messages(self, queries: dict, chat_history: list = None) -> list:
        """
        Generates a list of messages for the LLM.

        The `queries` dictionary should have 'system' and 'user' keys, each
        containing a dictionary of values to fill in the respective prompt
        templates.

        Args:
            queries (dict): A dictionary of queries for the system and user prompts.
                Example:
                {
                    "system": {"persona": "AI assistant"},
                    "user": {"language": "en", "input": "Hello"}
                }
            chat_history (list, optional): A list of previous chat messages. Defaults
                                         to None.

        Returns:
            list: A list of messages ready to be sent to the LLM.
        """
        system_query, user_query = queries["system"], queries["user"]
        sys_prompt = {
            "role": "system",
            "content": self._format_prompt(self.system_prompt_template, system_query)
        }
        user_prompt = {
            "role": "user",
            "content": self._format_prompt(self.user_prompt_template, user_query)
        }
        
        if chat_history:
            messages_payload = chat_history
            messages_payload.insert(0, sys_prompt)  
            messages_payload.append(user_prompt)    
        else:
            messages_payload = [sys_prompt, user_prompt]
        
        return messages_payload
        
    def _format_prompt(self, template: str, values: dict) -> str:
        """
        Formats a prompt template using values from a dictionary.

        Args:
            template (str): The prompt template with placeholders.
            values (dict): A dictionary with keys corresponding to the placeholders.

        Returns:
            str: The formatted prompt.
        """
        # Check for any keys in `values` that are not in the template.
        extra_keys = [key for key in values.keys() if f"{{{key}}}" not in template]
        if extra_keys:
            raise ValueError(f"Unused keys in values dictionary: {', '.join(extra_keys)}")

        try:
            return template.format(**values)
        except KeyError as e:
            raise KeyError(f"Missing key in prompt template: {e.args[0]}")
    
    def get_all_keys(self) -> dict:
        """
        Gets all the keys used in the system and user prompt templates.

        Returns:
            dict: A dictionary with 'system' and 'user' keys, each containing a list
                  of keys used in their respective prompt templates.
        """
        return {
            "system": [field_name for _, field_name, _, _ in string.Formatter().parse(self.system_prompt_template) if field_name],
            "user": [field_name for _, field_name, _, _ in string.Formatter().parse(self.user_prompt_template) if field_name],
        }
