.. _dev:

===================
Development Guide
===================

This guide will help you set up your development environment for Orkes, enabling you to contribute or simply run the project from source.

Setup
-----

To get started with development, follow these steps:

1.  **Clone the repository:**
    First, clone the Orkes repository from its source:

    .. code-block:: bash

        git clone https://github.com/hfahrudin/orkes.git
        cd orkes

2.  **Install in editable mode:**
    Install the project in editable mode, which allows you to make changes to the source code without reinstalling:

    .. code-block:: bash

        pip install -e .

2.  **Install project dependencies:**
    Run pip to install all necessary dependencies. This sets up the local environment required to run and develop the project.

    .. code-block:: bash

        pip install -r requirements.txt
                

.. warning:: 
    Remember to add test cases for any newly implemented features. Ensure that new functionality is covered by unit or integration tests to maintain high code quality and prevent future regressions.

Running Tests
-------------

It's crucial to run tests to ensure that your changes don't introduce regressions and that new features work as expected.

To run all tests, use the provided test runner script:

.. code-block:: bash

    python tests/run_all_tests.py

Viewing Test Reports
--------------------

After running the tests, a detailed HTML report is generated using `pytest-html`. You can view this report to see a comprehensive overview of test results, including passed, failed, and skipped tests.

The report is located in the `reports` folder at the root of your project:

.. code-block:: text

    reports/report_{test_type}_{timestamp}.html

Open this file in your web browser to examine the test outcomes.
