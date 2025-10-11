"""
Mock LLM Gateway for testing purposes.
"""
import json
import time
from typing import Dict, Any, List
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import structlog

logger = structlog.get_logger()


class MockLLMGatewayHandler(BaseHTTPRequestHandler):
    """Mock LLM Gateway HTTP handler for testing."""
    
    def do_POST(self):
        """Handle POST requests to LLM Gateway."""
        if self.path == '/api/v1/chat':
            self.handle_chat_request()
        elif self.path == '/health':
            self.handle_health_request()
        else:
            self.send_error(404, "Not Found")
    
    def handle_chat_request(self):
        """Handle chat completion requests."""
        try:
            # Read request body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data.decode('utf-8'))
            
            # Extract messages
            messages = request_data.get('messages', [])
            
            # Generate mock response based on content
            response_content = self._generate_mock_response(messages)
            
            # Create response
            response = {
                "choices": [{
                    "message": {
                        "content": response_content
                    }
                }],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150
                }
            }
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('x-llm-tokens-in', '100')
            self.send_header('x-llm-tokens-out', '50')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            logger.error("Mock LLM Gateway error", error=str(e))
            self.send_error(500, "Internal Server Error")
    
    def handle_health_request(self):
        """Handle health check requests."""
        response = {"status": "healthy", "service": "mock-llm-gateway"}
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def _generate_mock_response(self, messages: List[Dict[str, str]]) -> str:
        """Generate mock response based on input messages."""
        # Look for evidence in the messages
        user_message = None
        for msg in messages:
            if msg.get('role') == 'user':
                user_message = msg.get('content', '')
                break
        
        if not user_message:
            return json.dumps({"sections": []})
        
        # Check if this is an action extraction request
        if 'evidence' in user_message.lower() or 'actions' in user_message.lower():
            return self._generate_action_response(user_message)
        else:
            return self._generate_summary_response(user_message)
    
    def _generate_action_response(self, content: str) -> str:
        """Generate mock action extraction response."""
        # Simple heuristic: if content contains action words, generate actions
        action_words = ['urgent', 'please', 'review', 'meeting', 'deadline', 'срочно', 'пожалуйста']
        
        has_actions = any(word in content.lower() for word in action_words)
        
        if has_actions:
            response = {
                "sections": [{
                    "title": "Мои действия",
                    "items": [{
                        "title": "Mock Action Item",
                        "owners_masked": ["[[REDACT:NAME]]"],
                        "due": "2024-01-16",
                        "evidence_id": "ev-mock-001",
                        "confidence": 0.85,
                        "source_ref": {
                            "type": "email",
                            "msg_id": "msg-mock-001",
                            "conversation_id": "conv-mock-001"
                        }
                    }]
                }]
            }
        else:
            response = {"sections": []}
        
        return json.dumps(response)
    
    def _generate_summary_response(self, content: str) -> str:
        """Generate mock summary response."""
        return """# Дайджест действий - 2024-01-15

*Trace ID: mock-trace-id*

## Мои действия

### 1. Mock Action Item
**Срок:** 2024-01-16
**Уверенность:** Высокая
**Источник:** email, evidence ev-mock-001
**Ответственные:** [[REDACT:NAME]]

## Источники

### Evidence ev-mock-001
*ID: ev-mock-001*"""
    
    def log_message(self, format, *args):
        """Override to suppress default logging."""
        pass


class MockLLMGateway:
    """Mock LLM Gateway server for testing."""
    
    def __init__(self, port: int = 8080):
        self.port = port
        self.server = None
        self.thread = None
    
    def start(self):
        """Start the mock server."""
        self.server = HTTPServer(('localhost', self.port), MockLLMGatewayHandler)
        
        def serve():
            logger.info("Mock LLM Gateway started", port=self.port)
            self.server.serve_forever()
        
        self.thread = threading.Thread(target=serve, daemon=True)
        self.thread.start()
        
        # Give server time to start
        time.sleep(0.1)
    
    def stop(self):
        """Stop the mock server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1.0)
    
    def get_endpoint(self) -> str:
        """Get the mock server endpoint."""
        return f"http://localhost:{self.port}/api/v1/chat"


def create_mock_llm_config(port: int = 8080) -> Dict[str, Any]:
    """Create mock LLM configuration for testing."""
    return {
        "endpoint": f"http://localhost:{port}/api/v1/chat",
        "model": "mock/gpt-4o-mini",
        "timeout_s": 30,
        "headers": {},
        "max_tokens_per_run": 30000,
        "cost_limit_per_run": 5.0
    }


if __name__ == "__main__":
    # For testing the mock server directly
    mock_gateway = MockLLMGateway(port=8080)
    try:
        mock_gateway.start()
        print(f"Mock LLM Gateway running on http://localhost:8080")
        print("Press Ctrl+C to stop")
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping mock server...")
        mock_gateway.stop()
        print("Mock server stopped.")
