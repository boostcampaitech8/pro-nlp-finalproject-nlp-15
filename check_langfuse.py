from langfuse import Langfuse
import os
from dotenv import load_dotenv

load_dotenv()

lf = Langfuse()
print(f"Langfuse object type: {type(lf)}")
print(f"Available attributes: {[attr for attr in dir(lf) if not attr.startswith('_')]}")

try:
    trace = lf.trace(name="test")
    print("SUCCESS: lf.trace() exists")
except AttributeError:
    print("FAILED: lf.trace() does not exist")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
