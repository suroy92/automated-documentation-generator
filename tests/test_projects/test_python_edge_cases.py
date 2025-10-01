"""
test_python_edge_cases.py

A collection of Python functions and classes designed to test the robustness 
and accuracy of a documentation generation tool. Covers various docstring styles, 
parameter types, and structural edge cases.
"""

import math
from typing import List, Optional, Dict, Any

# 1. Function without a docstring (Should trigger LLM generation)
def calculate_hypotenuse(a, b):
    """Calculates the hypotenuse of a right-angled triangle."""
    return math.sqrt(a**2 + b**2)

# 2. Function with standard docstring (Numpy Style)
def process_data(data: List[int], threshold: int = 10) -> List[int]:
    """
    Filters a list of integers based on a specified threshold.

    Parameters
    ----------
    data : list of int
        The input list of numerical data to be filtered.
    threshold : int, optional
        The minimum value an element must have to be included. 
        Defaults to 10.

    Returns
    -------
    list of int
        A new list containing only elements greater than the threshold.
    """
    return [x for x in data if x > threshold]

# 3. Function with complex parameters (*args, **kwargs) and multi-line return description
def configure_system(*args: str, **kwargs: Dict[str, Any]) -> str:
    """
    Configures a simulated system using positional and keyword arguments.

    This function is primarily for testing parameter handling logic.

    :param args: Positional arguments representing configuration steps.
    :type args: str
    :param kwargs: Keyword arguments mapping setting names to values.
    :type kwargs: dict
    :raises ValueError: If an argument is 'error'.
    :returns: A configuration summary string detailing the number of arguments 
              and the presence of a 'verbose' flag. The description is quite long 
              and spans multiple lines to test parser robustness.
    :rtype: str
    """
    if 'error' in args:
        raise ValueError("Configuration failed due to 'error' step.")
    
    summary = f"Steps: {len(args)}, Settings: {len(kwargs)}"
    if kwargs.get('verbose'):
        summary += " (Verbose Mode)"
    return summary

# 4. Class with inheritance and private method (Should be ignored by default)
class BaseComponent:
    """
    A foundational class for all system components.

    It provides a basic initialization and status tracking.
    """
    def __init__(self, name: str):
        """Initializes the base component."""
        self.name = name

class DataProcessor(BaseComponent):
    """
    A concrete component for processing and validating data batches.

    Inherits from BaseComponent.
    """
    def __init__(self, name: str, batch_size: int):
        """
        Initializes the data processor.

        :param name: The name of the processor instance.
        :type name: str
        :param batch_size: The number of items to process at once.
        :type batch_size: int
        """
        super().__init__(name)
        self.batch_size = batch_size

    def _validate_batch(self, batch: List) -> bool:
        """
        Internal method to validate data integrity.

        This method should ideally be ignored or marked as private in documentation.

        :param batch: The list of data items.
        :type batch: list
        :returns: True if valid, False otherwise.
        :rtype: bool
        """
        return len(batch) <= self.batch_size

    def process(self, batch: List[Any]) -> Optional[List[Any]]:
        """
        Processes a single batch of data after validation.

        :param batch: The list of data to process.
        :type batch: list
        :returns: The processed batch, or None if validation fails.
        :rtype: Optional[list]
        """
        if self._validate_batch(batch):
            return [str(x).upper() for x in batch]
        return None

# 5. Function with multiple return types in docstring
def get_user_status(user_id: int) -> tuple or None:
    """
    Retrieves the status of a user from a dummy database.

    :param user_id: The unique identifier of the user.
    :type user_id: int
    :returns: A tuple (username: str, is_active: bool) if found, or None if not found.
    :rtype: tuple or None
    """
    if user_id % 2 == 0:
        return ("user_A", True)
    return None

# 6. Function using yield (Generator)
def sequence_generator(start: int, end: int):
    """
    A generator function that yields integers in a sequence.

    :param start: The starting integer of the sequence (inclusive).
    :type start: int
    :param end: The ending integer of the sequence (exclusive).
    :type end: int
    :yields: The next integer in the sequence.
    :rtype: int
    """
    current = start
    while current < end:
        yield current
        current += 1

# 7. Function defined inside a class method (Should not be documented standalone)
class Utility:
    """A collection of utility methods."""
    def run_calculation(self, base: int, iterations: int):
        """
        Executes a calculation loop.

        Contains a nested function to test scope handling.

        :param base: The starting value.
        :type base: int
        :param iterations: The number of times to iterate.
        :type iterations: int
        :returns: The final calculated value.
        :rtype: int
        """
        def nested_adder(x):
            # This nested function should NOT be documented.
            return x + 1

        result = base
        for _ in range(iterations):
            result = nested_adder(result)
        return result
