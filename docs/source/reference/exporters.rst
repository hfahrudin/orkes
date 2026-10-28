.. _exporters:

============
Exporters
============

Trace sinks receive a graph's trace while it runs. Attach them with
``OrkesGraph(..., trace_sinks=[...])``.

.. currentmodule:: orkes.exporters

Interface
---------

.. autosummary::
   :toctree: ../api/

   TraceSink

Orkes Watcher
-------------

Requires ``pip install "orkes[watcher]"``.

.. currentmodule:: orkes.exporters.watcher

.. autosummary::
   :toctree: ../api/

   WatcherSink
