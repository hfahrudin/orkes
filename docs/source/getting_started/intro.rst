.. _intro:

===============
Introduction
===============

Built for developers who need total control, Orkes is a low-abstraction, lightweight, Python library focused on (not limited) orchestrating agentic workflows. It combines the ability to deeply customize core components with native observation tools, allowing you to monitor execution and inspect agentic behavior in real-time. Orkes provides the transparency required to move complex systems from experimental hacks to reliable, observable environments.

Background
----------

The High Abstraction Gap
~~~~~~~~~~~~~~~~~~~~~~~~
Today’s higher-level libraries are often abstractions on top of abstractions, hidden under layers of dependencies. While this simplifies the "happy path," it turns niche production requirements (like properly closing an underlying HTTP connection on a client disconnect) into a complete clusterfuck.

In a self-hosted LLM environment, these hanging *ghost connections* are detrimental. They act as resource parasites, holding onto VRAM and compute cycles. When your framework buries the low-level hooks needed to manage these lifecycles, a simple networking fix becomes an archeological dig through source code.

The Observability Gap
~~~~~~~~~~~~~~~~~~~~~
Because some populare frameworks gatekeep it's Visualization platform, observability for developer often becomes a second priority. Without out-of-the-box I/O and state observation, we faced a *black box* effect.

The result? The we cannot understand where on when agent began to hallucinate. We fell into the trap of "spray and pray" prompt engineering, only to realize the "intelligence" wasn't the problem, turned out (for example) the failure lay in the framewrok inherent tool calling prompt.

Mission
~~~~~~~
Orkes was built to close these gaps. By keeping abstractions low and making I/O and execution observation a first-class citizen, ensure that the intelligence of your agents isn't undermined by the "complex" networking layer.


Installation
------------

From PyPI
~~~~~~~~~

You can install the latest stable version of the Orkes using pip:

.. code-block:: bash

    pip install orkes

Verifying the Installation
~~~~~~~~~~~~~~~~~~~~~~~~~~

You can verify the installation by running a simple import:

.. code-block:: python

    import orkes
    print(orkes.__version__)

If no errors occur and a version number is printed, the installation was successful.
