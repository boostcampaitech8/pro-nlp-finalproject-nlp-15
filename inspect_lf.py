import langfuse
import inspect

print("Langfuse version:", getattr(langfuse, "__version__", "unknown"))
print("Attributes of langfuse:", dir(langfuse))

try:
    lf = langfuse.Langfuse()
    print("Attributes of Langfuse instance:", dir(lf))
except Exception as e:
    print("Could not instantiate Langfuse:", e)

try:
    from langfuse.callback import LangfuseCallbackHandler
    print("Successfully imported LangfuseCallbackHandler from langfuse.callback")
except ImportError as e:
    print("ImportError:", e)
