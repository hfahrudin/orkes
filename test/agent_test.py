
import sys
import os

# Get the absolute path of folder A and add it to sys.path
sys.path.insert(0, os.path.abspath('../src')) 

from agents.core import Agent
from services.connections import vLLMConnection
from services.prompts import ChatPromptHandler
from services.responses import ChatResponse

system_prompt="{persona} Provide accurate and detailed answers based solely on the retrieved context: {context}."
user_prompt="{input}"

cR = ChatResponse()
cP = ChatPromptHandler(system_prompt_template=system_prompt, user_prompt_template=user_prompt)
connection = vLLMConnection(url="http://localhost:8000/", model_name="ibm-granite/granite-3.1-2b-instruct")


my_agent = Agent(name="agent_0", prompt_handler=cP, llm_connection=connection, response_handler=cR)

queries = {
    "system" : {
        "persona" : "You are funny AI bot.",
        "context" : "This user love inuyasha movie"
    },
    "user" : {
        "input" : "guess what my favorite anime is!"
    }
}

chat_history = []

print(my_agent.invoke(queries))


my_agent.stream(queries)