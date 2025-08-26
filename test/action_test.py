import requests
#FOR LOCAL TESTING
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orkes.agents.actions import ActionBuilder

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
}, description="Fetch IP information from ipinfo.io")


tool2 = ActionBuilder(func_name="get_domain_details", params={
    "domain": {"type": str, "desc": "The domain name to check"}
}, description="Fetch SSL/domain info")


print(tool1.get_schema_tool(if_desc=True))
print(tool2.get_schema_tool())