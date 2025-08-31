import string
from abc import ABC, abstractmethod
from requests import Response

class PromptInterface(ABC):
    @abstractmethod
    def gen_messages(self, queries, chat_history: list = None):
        """generate messages for the LLM."""
        pass

    @abstractmethod
    def get_all_keys(self):
        """generate messages for the LLM."""
        pass

class ChatPromptHandler(PromptInterface):
    def __init__(self, system_prompt_template: str, user_prompt_template: str):
        """ Args:
            system_prompt (str): The initial system prompt.
            user_prompt (str): The initial user prompt.
            
            example:
            system_prompt="{persona}. You must acknowledge that an exact match could not be found in your knowledge database. State this clearly and inform the user that you will do your best to assist them. Then, provide a detailed, relevant, and informative response based on your general knowledge. Respond directly and in the language of the user's latest message when requested.",
            user_prompt="{language}{input}, do not give out any external link"
        """
        self.system_prompt_template = system_prompt_template
        self.user_prompt_template = user_prompt_template  # Fixed variable assignment
        self._tools_prompt = None
        
    def gen_messages(self, queries, chat_history: list = None):
        # queries should look like this
        # queries = {
        #     "system": {
        #         "context": bb,
        #         "persona" : ccc
        #     },
        #     "user": {
        #         "sample": aaa,
        #         "input": ccc
        #     }
        # }
        system_query, user_query = queries["system"] , queries["user"]
        sys_prompt = {
            "role" : "system",
            "content" :self._format_prompt(self.system_prompt_template, system_query)
        }
        user_prompt = {
            "role" : "user",
            "content" :self._format_prompt(self.user_prompt_template, user_query)
        }
        
        if chat_history:
            messages_payload = chat_history
            messages_payload.insert(0, sys_prompt)  
            messages_payload.append(user_prompt)    
        else:
            messages_payload = []
            messages_payload.append(sys_prompt)
            messages_payload.append(user_prompt)  
        
        return messages_payload
        
    def _format_prompt(self, template: str, values: dict) -> str:
        """
        Formats a prompt template using values from a dictionary for LLM prompting.

        Args:
            template (str): The prompt template containing placeholders.
            values (dict): A dictionary with keys corresponding to placeholders in the template.

        Returns:
            str: The formatted prompt.
        """

        # Check for excesive params
        missing_keys = [key for key in values.keys() if f"{{{key}}}" not in template]
        if missing_keys:
            raise ValueError(f"Unused keys in values dictionary: {', '.join(missing_keys)}")

        try:
            return template.format(**values)
        except KeyError as e:
            raise KeyError(f"Missing key: {e.args[0]}")
    
    def get_all_keys(self):
        return {
            "system" : [field_name for _, field_name, _, _ in string.Formatter().parse(self.system_prompt_template ) if field_name], 
            "user" : [field_name for _, field_name, _, _ in string.Formatter().parse(self.user_prompt_template ) if field_name], 
            }
