"""
Health and readiness check endpoints for observability.
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
import structlog
import httpx
from typing import Optional

logger = structlog.get_logger()


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health and readiness checks."""
    
    def __init__(self, *args, llm_config=None, **kwargs):
        self.llm_config = llm_config
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests for health/readiness."""
        if self.path == '/healthz':
            self.send_health_response()
        elif self.path == '/readyz':
            self.send_readiness_response()
        else:
            self.send_error(404, "Not Found")
    
    def send_health_response(self):
        """Send health check response."""
        # Health check: is the service running?
        response = {
            "status": "healthy",
            "service": "digest-core"
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def send_readiness_response(self):
        """Send readiness check response."""
        # Readiness check: is the service ready to accept requests?
        checks = {
            "service": "digest-core",
            "checks": {}
        }
        
        # Check LLM Gateway connectivity if config is available
        if self.llm_config:
            llm_status = self._check_llm_gateway()
            checks["checks"]["llm_gateway"] = llm_status
        else:
            checks["checks"]["llm_gateway"] = {"status": "unknown", "reason": "no_config"}
        
        # Determine overall readiness
        all_healthy = all(
            check.get("status") == "healthy" 
            for check in checks["checks"].values()
        )
        
        checks["status"] = "ready" if all_healthy else "not_ready"
        
        status_code = 200 if all_healthy else 503
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(checks).encode('utf-8'))
    
    def _check_llm_gateway(self) -> dict:
        """Check LLM Gateway connectivity."""
        try:
            # Simple connectivity check
            with httpx.Client(timeout=5.0) as client:
                # Try to make a simple request to check connectivity
                # This is a basic check - in production you might want a dedicated health endpoint
                response = client.get(
                    self.llm_config.endpoint.replace('/chat', '/health'),
                    headers={"Authorization": f"Bearer {self.llm_config.get_token()}"}
                )
                
                if response.status_code == 200:
                    return {"status": "healthy", "endpoint": self.llm_config.endpoint}
                else:
                    return {
                        "status": "unhealthy", 
                        "endpoint": self.llm_config.endpoint,
                        "status_code": response.status_code
                    }
                    
        except httpx.ConnectError:
            return {
                "status": "unhealthy",
                "endpoint": self.llm_config.endpoint,
                "reason": "connection_failed"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "endpoint": self.llm_config.endpoint,
                "reason": str(e)
            }
    
    def log_message(self, format, *args):
        """Override to suppress default logging."""
        pass


def start_health_server(port: int = 9109, llm_config=None):
    """Start health check HTTP server in background thread."""
    
    def handler_factory(*args, **kwargs):
        return HealthCheckHandler(*args, llm_config=llm_config, **kwargs)
    
    server = HTTPServer(('0.0.0.0', port), handler_factory)
    
    def serve():
        logger.info("Health check server started", port=port)
        server.serve_forever()
    
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    
    return server

