.. _services:

============
Services
============

.. currentmodule:: orkes.services

Configuration
-------------

.. autosummary::
   :toctree: ../api/

   LLMConfig

Clients
-------

.. autosummary::
   :toctree: ../api/

   vLLMConnection
   UniversalLLMClient
   LLMFactory

Response Handling
-----------------

.. autosummary::
   :toctree: ../api/

   ResponseInterface
   ChatResponse
   StreamResponseBuffer

Schemas
-------

.. autosummary::
   :toctree: ../api/

   ToolCallSchema
   RequestSchema
   LLMProviderStrategy
   LLMInterface

Strategies
----------

.. autosummary::
   :toctree: ../api/

   OpenAIStyleStrategy
   AnthropicStrategy
   GoogleGeminiStrategy
