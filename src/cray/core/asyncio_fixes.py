# In cray/src/cray/core/asyncio_fixes.py
import asyncio
import sys

class AsyncioFixes:
    """Handle deprecated asyncio patterns."""
    
    @staticmethod
    def get_event_loop_safely():
        """Get event loop in a backward-compatible way."""
        try:
            # For Python 3.7+
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # For Python 3.5.2+ and for when there's no running loop
            loop = asyncio.get_event_loop()
        except Exception:
            # Fallback
            loop = asyncio.new_event_loop()
        return loop

# Fix for asyncio.get_event_loop() deprecation
if sys.version_info >= (3, 7):
    # Use get_running_loop() when available
    def get_event_loop():
        """Get the current event loop or create a new one."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop
else:
    # For older Python versions, use the older get_event_loop
    def get_event_loop():
        """Get event loop for older Python versions."""
        try:
            loop = asyncio.get_event_loop()
        except:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop