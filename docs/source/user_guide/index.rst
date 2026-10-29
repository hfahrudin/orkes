.. _user_guide:

==========
User Guide
==========

Welcome to the Orkes User Guide. This guide provides a comprehensive overview of the library, from core concepts to advanced features. Whether you are building your first graph or looking for best practices, these documents will help you get the most out of Orkes.

This guide is structured to be read sequentially, but feel free to jump to the section that is most relevant to your needs.

.. toctree::
   :maxdepth: 4
   :hidden:

   core_concepts
   building_your_first_graph
   advanced_control_flow
   async_execution
   custom_llm_services
   tool_calling
   tracing
   orkes_watcher
   best_practices

Here is a brief overview of what you will find in this guide:

- **Core Concepts**: An introduction to the fundamental building blocks of Orkes.
- **Building Your First Graph**: A step-by-step tutorial on how to create and run a simple workflow.
- **Async Execution**: A guide to running graphs with ``arun()``, mixing sync and async node/gate functions, and running multiple graphs concurrently.
- **Connecting Custom LLMs**: Learn how to connect Orkes to any LLM service.
- **Tool Calling**: A guide to have fine-grained control over how tools are defined and used.
- **Orkes Tracer**: A guide to using the powerful tracing and visualization tools.
- **Sending Traces to Watcher**: Stream runs to Orkes Watcher, a web dashboard for live runs and run history, and write your own trace sinks.
- **Best Practices**: A collection of tips and recommendations for using Orkes effectively.
