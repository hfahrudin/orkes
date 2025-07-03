from agents.core import AgentInterface

class Orkes:
    def __init__(self):
        self.agent_pools = {}
        pass

    def add_agent(self, name: str, agent: AgentInterface):
        if name in self.agent_pools:
            raise ValueError(f"Agent '{name}' already exists.")
        self.agent_pools[name] = agent

        
"function with state argument + agent is the agreed node"
"Orkes need accept state as memory management"
"belajar langchain/graph memory management"