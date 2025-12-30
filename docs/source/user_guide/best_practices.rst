.. _best_practices:

===============
Best Practices
===============

This section provides a collection of tips and recommendations for using Orkes efficiently and effectively.

1. Design a Clear State
-----------------------
The state is the heart of your workflow. A well-designed state `TypedDict` makes your graph easier to understand, debug, and maintain.

- **Be specific**: Use descriptive names for your state variables.
- **Avoid overly complex types**: If a state variable becomes a very complex nested dictionary, consider if it can be simplified.
- **Initialize your state**: Ensure all keys are present in your initial state object, even if they are just set to `None` or an empty list.

2. Write Modular and Reusable Nodes
-----------------------------------
Treat your node functions as small, focused, and pure functions.

- **Single responsibility**: Each node should do one thing well. For example, have separate nodes for fetching data, processing it, and formatting the output.
- ** Stateless logic**: As much as possible, the node's logic should only depend on its inputs from the state. Avoid relying on external global variables.
- **Test nodes independently**: A well-designed node can be tested as a regular Python function, without needing to run the entire graph.

3. Use the Visualizer as a Development Tool
-------------------------------------------
The interactive tracer is not just for debugging. Use it as a primary tool during development to:

- **Verify your logic**: Run your graph with sample data and inspect the trace to ensure it behaves as expected.
- **Understand state changes**: The visualizer makes it easy to see how the state is modified at each step.
- **Communicate your workflow**: The trace is a great way to share and explain your graph's logic to other developers.

4. Describe Your Graph
---------------------
While the code for your nodes should be clear, the overall structure of your graph might not be immediately obvious.

- **Always provide a description argument**: If the directive interface supports a description or caption argument, always use it!
- **Use descriptive node names**: `plan_search_queries` is better than `node1`.
- **Add comments to your graph definition**: A few lines of comments explaining the purpose of a complex conditional edge can be very helpful.

