import json
from abc import ABC, abstractmethod


class LLMResponse:
    """
    Abstract base class for LLM response.
    Defines methods to parse messages.
    """
    @abstractmethod
    def _parse_response(self, response):
        """Parse the response from the LLM."""
        pass

    