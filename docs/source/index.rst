*********************
Orkes Documentations
*********************

**Date**: |today| **Version**: |version|

**Useful links**:
`Binary Installers <https://pypi.org/project/orkes/>`__ |
`Source Repository <https://github.com/hfahrudin/orkes>`__ |
`Issues & Ideas <https://github.com/hfahrudin/orkes/issues>`__ 

What's New
==========

- **Graph Traceability**: This feature introduces a powerful visualization tool for debugging and understanding graph executions. When a graph is run, it can now generate a detailed execution trace, capturing the state, timing, and data flow at every step. This trace is then used to create a self-contained, interactive HTML file that provides a visual representation of the graph's execution.

- **API Overhaul**: The library's core API has been fundamentally redesigned to be more flexible, observable, and intuitive. The previous agent-centric, linear execution model has been replaced with a new graph-based architecture centered around the ``OrkesGraph`` class.

Roadmap
=======

.. list-table::
   :widths: 25 50 15
   :header-rows: 1

   * - Feature
     - Description
     - Status
   * - Boilerplate Agent
     - Provide a well-structured boilerplate for creating new agents to accelerate the development of agentic systems.
     - Planned
   * - Parallel Graph Execution
     - Enhance the graph runner to support parallel execution of independent branches for improved performance.
     - Planned
   * - Tracer Web Platform
     - Develop a standalone web-based platform for visualizing and inspecting graph traces in real-time.
     - Planned



.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Contents:

   getting_started/index
   user_guide/index
   api
