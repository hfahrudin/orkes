import requests
#FOR LOCAL TESTING
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orkes.agents.actions import ActionBuilder
from orkes.agents.core import ToolAgent
from orkes.services.connections import vLLMConnection

# ------------------ API CALL Function ------------------ #
def get_ip_info(ip: str):
    """
    Fetch IP information from ipinfo.io.
    """
    url = f"https://ipinfo.io/{ip}/geo"
    response = requests.get(url)
    try:
        return response.json()
    except ValueError:
        return response.text

def get_domain_details(domain: str):
    """
    Fetch SSL/domain information from ssl-checker.io.
    """
    url = f"https://ssl-checker.io/api/v1/check/{domain}"
    response = requests.get(url)
    try:
        return response.json()
    except ValueError:
        return response.text

# ------------------ Action Definition ------------------ #

tool1 = ActionBuilder(func_name="get_ip_info", params= {
    "ip": {"type": str, "desc": "The IP address to look up"}
}, description="Fetch IP information from ipinfo.io", func=get_ip_info)


tool2 = ActionBuilder(func_name="get_domain_details", params={
    "domain": {"type": str, "desc": "The domain name to check"}
}, description="Fetch SSL/domain info", func=get_domain_details)


connection = vLLMConnection(url="http://localhost:8000/", model_name="auto")

tool_agent = ToolAgent(name="agent_0", llm_connection=connection)

tool_agent.add_tools([tool1, tool2])

print(tool_agent._build_tools_prompt())

# # print(my_agent.invoke())

 # UPLOAD TO AGENT

 # CHECK IF THE TOOLING IS RIGHT LY IMPLEMENTED ON PROMPT

 #TEST WHETHER AGENT COULD SELECT PROPER TOOLS, OR EVEN NOT CHOOSING AT ALL
