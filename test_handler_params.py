from langfuse.langchain import CallbackHandler
import os
from dotenv import load_dotenv

load_dotenv()

try:
    # Try initializing with trace_name and tags which are commonly supported via **kwargs
    handler = CallbackHandler(
        trace_name="Test Trace Name",
        tags=["experiment", "test"]
    )
    print("SUCCESS: CallbackHandler initialized with trace_name and tags")
    print(f"Handler metadata/context: {handler.__dict__.get('trace_context', 'N/A')}")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
