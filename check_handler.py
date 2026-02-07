from langfuse.langchain import CallbackHandler
import inspect

print(f"CallbackHandler signature: {inspect.signature(CallbackHandler.__init__)}")
print(f"CallbackHandler attributes: {[attr for attr in dir(CallbackHandler) if not attr.startswith('_')]}")

handler = CallbackHandler()
print(f"Instance attributes: {[attr for attr in dir(handler) if not attr.startswith('_')]}")
