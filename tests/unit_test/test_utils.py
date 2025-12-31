from orkes.shared.utils import callable_to_orkes_tool_schema

def sample_function(name: str, age: int, city: str = "New York") -> str:
    """
    This is a sample function.

    Args:
        name (str): The name of the person.
        age (int): The age of the person.
        city (str): The city where the person lives.

    Returns:
        str: A greeting message.
    """
    return f"Hello, {name}! You are {age} years old and live in {city}."

def test_callable_to_orkes_tool_schema():
    """
    Tests the callable_to_orkes_tool_schema function.
    """
    tool_schema = callable_to_orkes_tool_schema(sample_function)

    assert tool_schema.name == "sample_function"
    assert tool_schema.description == "This is a sample function."
    #LATER WILL SUPPORT FUNCTION HERE
    # assert tool_schema.function == sample_function

    parameters = tool_schema.parameters
    assert parameters.type == "object"
    assert "name" in parameters.properties
    assert "age" in parameters.properties
    assert "city" in parameters.properties

    assert parameters.properties["name"]["type"] == "string"
    assert parameters.properties["name"]["description"] == "The name of the person."
    assert "default" not in parameters.properties["name"]

    assert parameters.properties["age"]["type"] == "integer"
    assert parameters.properties["age"]["description"] == "The age of the person."
    assert "default" not in parameters.properties["age"]

    assert parameters.properties["city"]["type"] == "string"
    assert parameters.properties["city"]["description"] == "The city where the person lives."
    assert parameters.properties["city"]["default"] == "New York"

    assert "name" in parameters.required
    assert "age" in parameters.required
    assert "city" not in parameters.required
