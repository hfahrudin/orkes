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
   * - Pilot: Run Control
     - Stop, pause and resume a running graph from Orkes Watcher. orkes checks for commands between nodes, never inside one, and a stopped run ends cleanly with its own status.
     - Planned
   * - Pilot: Human Feedback
     - Let a node ask a person a question from Orkes Watcher (text, optional choices, timeout) and wait for the answer before continuing.
     - Planned
   * - Concurrent Branch Execution
     - Run the branches of a parallel split at the same time, as an opt-in for ``arun()``. Today branches run one after another; for concurrent calls, use ``asyncio.gather`` inside a node.
     - Under consideration



.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Contents:

   getting_started/index
   user_guide/index
   api
