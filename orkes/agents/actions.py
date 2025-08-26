from pydantic import BaseModel, Field, ValidationError
from typing import Any, Dict, Optional, Type

'''
# example of params
params = {
    "search_query": {
        "type": str,
        "default": None,
        "desc": "Query that is optimized for RAG search.",
    },
    "justification": {
        "type": str,
        "default": None,
        "desc": "Why this query is relevant to the user's request.",
    },
}
'''

class ActionBuilder:
    def __init__(self, func_name: str, params: Dict[str, Dict[str, Any]], description: str = ""):
        self.func_name = func_name
        self.description = description
        self._model_class: Optional[Type[BaseModel]] = None
        self.memory_buffer = []
        self.build(params)

    def build(self, params: Dict[str, Dict[str, Any]]) -> None:
        annotations = {}
        namespace = {}

        for field_name, field_info in params.items():
            field_type = field_info.get("type", Any)
            desc = field_info.get("desc", "")

            annotations[field_name] = field_type
            # Use Ellipsis '...' as default to make the field required
            namespace[field_name] = Field(..., description=desc)

        namespace["__annotations__"] = annotations
        self._model_class = type("DynamicInputModel", (BaseModel,), namespace)

    def get_model_class(self) -> Type[BaseModel]:
        if self._model_class is None:
            raise ValueError("Model class not built yet. Call build() first.")
        return self._model_class

    def get_schema_detail(self) -> Dict[str, Any]:
        model_cls = self.get_model_class()
        return {
            "name": self.func_name,
            "description": self.description,
            "parameters": model_cls.model_json_schema()
        }

    def get_schema_tool(self, if_desc=False) -> Dict[str, Any]:
        model_cls = self.get_model_class()
        
        schema = {
            "properties": {},
            "required": []
        }

        for field_name, field in model_cls.model_fields.items():
            field_type = field.annotation.__name__.lower()  # crude type mapping, e.g. 'str'

            
            # Add to properties
            schema["properties"][field_name] = {
                "type": field_type
            }

            if if_desc:
                field_desc = field.description.lower()  # crude type mapping, e.g. 'str'
                schema["properties"][field_name]['description'] = field_desc

            # Add to required if no default
            if field.is_required():
                schema["required"].append(field_name)

        return {
            "type": "function",
            "function": {
                "name": self.func_name,
                "description": self.description,
                "parameters": schema
            }
        }
    
    def validate_params(self, data: Dict[str, Any]) -> BaseModel:
        model_cls = self.get_model_class()
        try:
            return model_cls(**data)
        except ValidationError as e:
            # You can customize error handling here
            raise e