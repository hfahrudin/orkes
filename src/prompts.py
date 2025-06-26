import string

class PromptHandler:
    def __init__(self, system_prompt: str, user_prompt: str):
        """ Args:
            system_prompt (str): The initial system prompt.
            user_prompt (str): The initial user prompt.
        """
        self.system_prompt_template = system_prompt
        self.user_prompt_template = user_prompt  # Fixed variable assignment
        
    def gen_messages(self, queries):
        sys_message = {
            "role" : "system",
            "content" :self._format_prompt(self.system_prompt_template, queries['system'])
        }
        user_message = {
            "role" : "user",
            "content" :self._format_prompt(self.user_prompt_template, queries['user'])
        }
        
        return sys_message, user_message
    
        
    def _format_prompt(self, template: str, values: dict) -> str:
        """
        Formats a prompt template using values from a dictionary for LLM prompting.

        Args:
            template (str): The prompt template containing placeholders.
            values (dict): A dictionary with keys corresponding to placeholders in the template.

        Returns:
            str: The formatted prompt.
        """

        # Check for missing placeholders
        missing_keys = [key for key in values.keys() if f"{{{key}}}" not in template]
        
        if missing_keys:
            raise ValueError(f"Unused keys in values dictionary: {', '.join(missing_keys)}")

        # Return the formatted prompt
        return template.format(**values)
    
    def get_all_keys(self):
        return {
            "system" : [field_name for _, field_name, _, _ in string.Formatter().parse(self.system_prompt_template ) if field_name], 
            "user" : [field_name for _, field_name, _, _ in string.Formatter().parse(self.user_prompt_template ) if field_name], 
            }
