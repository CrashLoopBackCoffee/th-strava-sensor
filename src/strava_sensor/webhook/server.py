"""Strava webhook server implementation."""

import hashlib
import hmac
import http.server
import json
import logging
import socketserver
import threading

from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import pydantic

_logger = logging.getLogger(__name__)


class WebhookEvent(pydantic.BaseModel):
    """Model for Strava webhook events."""
    
    object_type: str
    object_id: int
    aspect_type: str
    owner_id: int
    subscription_id: int
    event_time: int
    updates: dict[str, Any] = pydantic.Field(default_factory=dict)


class WebhookChallenge(pydantic.BaseModel):
    """Model for webhook challenge verification."""
    
    hub_mode: str = pydantic.Field(alias='hub.mode')
    hub_challenge: str = pydantic.Field(alias='hub.challenge') 
    hub_verify_token: str = pydantic.Field(alias='hub.verify_token')


class WebhookHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for Strava webhooks."""
    
    def __init__(self, verify_token: str, client_secret: str, event_callback: Callable[[WebhookEvent], None], *args, **kwargs):
        self.verify_token = verify_token
        self.client_secret = client_secret
        self.event_callback = event_callback
        super().__init__(*args, **kwargs)
        
    def log_message(self, fmt: str, *args) -> None:
        """Override to use our logger instead of stderr."""
        _logger.debug(fmt, *args)
    
    def do_GET(self) -> None:
        """Handle GET requests for webhook verification."""
        try:
            # Parse query parameters
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            # Flatten single-value lists
            flat_params = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}
            
            # Validate challenge request
            challenge = WebhookChallenge.model_validate(flat_params)
            
            if challenge.hub_mode != 'subscribe':
                self.send_error(400, 'Invalid hub.mode')
                return
                
            if challenge.hub_verify_token != self.verify_token:
                self.send_error(403, 'Invalid verification token')
                return
            
            # Send challenge response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {'hub.challenge': challenge.hub_challenge}
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
            _logger.info('Webhook verification successful')
            
        except pydantic.ValidationError as e:
            _logger.error('Invalid webhook challenge: %s', e)
            self.send_error(400, 'Invalid webhook challenge')
        except Exception as e:
            _logger.error('Error processing webhook challenge: %s', e)
            self.send_error(500, 'Internal server error')
    
    def do_POST(self) -> None:
        """Handle POST requests for webhook events."""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            # Verify signature
            signature = self.headers.get('X-Hub-Signature')
            if not self._verify_signature(body, signature):
                self.send_error(403, 'Invalid signature')
                return
            
            # Parse and validate event
            event_data = json.loads(body.decode('utf-8'))
            event = WebhookEvent.model_validate(event_data)
            
            _logger.info('Received webhook event: %s', event.model_dump())
            
            # Process event
            self.event_callback(event)
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            
        except json.JSONDecodeError as e:
            _logger.error('Invalid JSON in webhook event: %s', e)
            self.send_error(400, 'Invalid JSON')
        except pydantic.ValidationError as e:
            _logger.error('Invalid webhook event: %s', e)
            self.send_error(400, 'Invalid webhook event')
        except Exception as e:
            _logger.error('Error processing webhook event: %s', e)
            self.send_error(500, 'Internal server error')
    
    def _verify_signature(self, body: bytes, signature: str | None) -> bool:
        """Verify webhook signature using client secret."""
        if not signature:
            _logger.warning('No signature provided')
            return False
        
        expected_signature = hmac.new(
            self.client_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)


class WebhookServer:
    """Webhook server for handling Strava events."""
    
    def __init__(self, port: int, verify_token: str, client_secret: str, event_callback: Callable[[WebhookEvent], None]):
        self.port = port
        self.verify_token = verify_token
        self.client_secret = client_secret
        self.event_callback = event_callback
        self.server: socketserver.TCPServer | None = None
        self.thread: threading.Thread | None = None
    
    def start(self) -> None:
        """Start the webhook server."""
        if self.server is not None:
            raise RuntimeError('Server is already running')
        
        # Create handler class with our configuration
        def handler_factory(*args, **kwargs):
            return WebhookHandler(
                self.verify_token,
                self.client_secret,
                self.event_callback,
                *args,
                **kwargs
            )
        
        # Create and start server
        self.server = socketserver.TCPServer(('', self.port), handler_factory)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        
        _logger.info('Webhook server started on port %d', self.port)
    
    def stop(self) -> None:
        """Stop the webhook server."""
        if self.server is None:
            return
        
        self.server.shutdown()
        self.server.server_close()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        self.server = None
        self.thread = None
        
        _logger.info('Webhook server stopped')
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()