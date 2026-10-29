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

- **Orkes Watcher Export**: stream runs to a live dashboard with ``WatcherSink``. See :ref:`orkes_watcher`.
- **Richer Traces**: failed runs record the traceback and failing node; steps record node time.
- **Lighter Graph API**: no third-party dependencies; LLM requests now have timeouts.
- **Graph Traceability**: every run can be viewed as an interactive HTML trace.
- **API Overhaul**: a graph-based API built around ``OrkesGraph``.

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
     - Implemented
   * - Orkes Watcher Export
     - Stream graph traces to Orkes Watcher, a separate web platform for inspecting runs live and across history.
     - Implemented



.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Contents:

   getting_started/index
   user_guide/index
   api
