"""
Health and readiness check endpoints for observability.
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
import structlog

logger = structlog.get_logger()


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health and readiness checks."""
    
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
        response = {
            "status": "ready",
            "service": "digest-core"
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to suppress default logging."""
        pass


def start_health_server(port: int = 9109):
    """Start health check HTTP server in background thread."""
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    
    def serve():
        logger.info("Health check server started", port=port)
        server.serve_forever()
    
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    
    return server

