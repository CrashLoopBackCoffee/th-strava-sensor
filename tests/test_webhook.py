"""Tests for webhook functionality."""

import json
import socket
import threading
import time
from unittest.mock import Mock, patch
from urllib.parse import urlencode

import pytest
import requests

from strava_sensor.webhook.processor import ActivityProcessor
from strava_sensor.webhook.server import WebhookEvent, WebhookServer
from strava_sensor.webhook.subscription import WebhookSubscriptionManager


def get_free_port():
    """Get a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


class TestWebhookEvent:
    """Test webhook event model."""
    
    def test_webhook_event_validation(self):
        """Test webhook event model validation."""
        event_data = {
            'object_type': 'activity',
            'object_id': 123456,
            'aspect_type': 'create',
            'owner_id': 789,
            'subscription_id': 1,
            'event_time': 1609459200,
            'updates': {'title': 'New Activity'}
        }
        
        event = WebhookEvent.model_validate(event_data)
        
        assert event.object_type == 'activity'
        assert event.object_id == 123456
        assert event.aspect_type == 'create'
        assert event.owner_id == 789
        assert event.subscription_id == 1
        assert event.event_time == 1609459200
        assert event.updates == {'title': 'New Activity'}
    
    def test_webhook_event_minimal(self):
        """Test webhook event with minimal data."""
        event_data = {
            'object_type': 'activity',
            'object_id': 123456,
            'aspect_type': 'create',
            'owner_id': 789,
            'subscription_id': 1,
            'event_time': 1609459200
        }
        
        event = WebhookEvent.model_validate(event_data)
        
        assert event.updates == {}


class TestWebhookServer:
    """Test webhook server functionality."""
    
    def test_webhook_server_context_manager(self):
        """Test webhook server as context manager."""
        verify_token = 'test_token'
        client_secret = 'test_secret'
        callback = Mock()
        port = get_free_port()
        
        with WebhookServer(port, verify_token, client_secret, callback) as server:
            assert server.server is not None
            assert server.thread is not None
        
        # Server should be stopped after context
        assert server.server is None
    
    def test_webhook_verification(self):
        """Test webhook verification endpoint."""
        verify_token = 'test_token'
        client_secret = 'test_secret'
        callback = Mock()
        port = get_free_port()
        
        with WebhookServer(port, verify_token, client_secret, callback):
            # Wait for server to start
            time.sleep(0.2)
            
            # Test verification request
            params = {
                'hub.mode': 'subscribe',
                'hub.challenge': 'test_challenge',
                'hub.verify_token': verify_token
            }
            
            response = requests.get(f'http://localhost:{port}?{urlencode(params)}', timeout=5)
            
            assert response.status_code == 200
            assert response.json() == {'hub.challenge': 'test_challenge'}
    
    def test_webhook_verification_invalid_token(self):
        """Test webhook verification with invalid token."""
        verify_token = 'test_token'
        client_secret = 'test_secret'
        callback = Mock()
        port = get_free_port()
        
        with WebhookServer(port, verify_token, client_secret, callback):
            # Wait for server to start
            time.sleep(0.2)
            
            # Test verification request with wrong token
            params = {
                'hub.mode': 'subscribe',
                'hub.challenge': 'test_challenge',
                'hub.verify_token': 'wrong_token'
            }
            
            response = requests.get(f'http://localhost:{port}?{urlencode(params)}', timeout=5)
            
            assert response.status_code == 403
    
    @patch('strava_sensor.webhook.server.WebhookHandler._verify_signature')
    def test_webhook_event_processing(self, mock_verify):
        """Test webhook event processing."""
        verify_token = 'test_token'
        client_secret = 'test_secret'
        callback = Mock()
        mock_verify.return_value = True
        port = get_free_port()
        
        with WebhookServer(port, verify_token, client_secret, callback):
            # Wait for server to start
            time.sleep(0.2)
            
            # Test webhook event
            event_data = {
                'object_type': 'activity',
                'object_id': 123456,
                'aspect_type': 'create',
                'owner_id': 789,
                'subscription_id': 1,
                'event_time': 1609459200
            }
            
            response = requests.post(
                f'http://localhost:{port}',
                json=event_data,
                headers={'X-Hub-Signature': 'test_signature'},
                timeout=5
            )
            
            assert response.status_code == 200
            assert response.json() == {'status': 'ok'}
            
            # Verify callback was called
            callback.assert_called_once()
            called_event = callback.call_args[0][0]
            assert called_event.object_type == 'activity'
            assert called_event.object_id == 123456


class TestActivityProcessor:
    """Test activity processor functionality."""
    
    def test_process_activity_event(self):
        """Test processing of activity creation event."""
        mock_source = Mock()
        mock_source.matches_uri.return_value = True
        mock_source.read_activity.return_value = b'mock_fit_data'
        
        sources = [mock_source]
        processor = ActivityProcessor(sources)
        
        # Mock FitFile
        with patch('strava_sensor.webhook.processor.FitFile') as mock_fitfile:
            mock_fit = mock_fitfile.return_value
            mock_fit.activity_id = 'test_serial'
            mock_fit.start_time = '2024-01-01T00:00:00Z'
            mock_fit.get_devices_status.return_value = []
            
            event = WebhookEvent(
                object_type='activity',
                object_id=123456,
                aspect_type='create',
                owner_id=789,
                subscription_id=1,
                event_time=1609459200
            )
            
            processor.process_webhook_event(event)
            
            # Verify the source was called
            mock_source.read_activity.assert_called_once_with('strava://123456')
            mock_fitfile.assert_called_once_with(b'mock_fit_data')
    
    def test_ignore_non_activity_events(self):
        """Test that non-activity events are ignored."""
        sources = []
        processor = ActivityProcessor(sources)
        
        event = WebhookEvent(
            object_type='athlete',
            object_id=789,
            aspect_type='update',
            owner_id=789,
            subscription_id=1,
            event_time=1609459200
        )
        
        # Should not raise any exceptions
        processor.process_webhook_event(event)
    
    def test_ignore_non_create_events(self):
        """Test that non-create events are ignored."""
        sources = []
        processor = ActivityProcessor(sources)
        
        event = WebhookEvent(
            object_type='activity',
            object_id=123456,
            aspect_type='update',
            owner_id=789,
            subscription_id=1,
            event_time=1609459200
        )
        
        # Should not raise any exceptions
        processor.process_webhook_event(event)


class TestWebhookSubscriptionManager:
    """Test webhook subscription management."""
    
    @patch('strava_sensor.webhook.subscription.requests.post')
    def test_create_subscription(self, mock_post):
        """Test creating a webhook subscription."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'id': 12345,
            'resource_state': 3,
            'application_id': 5678,
            'callback_url': 'https://example.com/webhook',
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z'
        }
        mock_post.return_value = mock_response
        
        manager = WebhookSubscriptionManager('client_id', 'client_secret')
        
        subscription = manager.create_subscription(
            'https://example.com/webhook',
            'verify_token'
        )
        
        assert subscription.id == 12345
        assert subscription.callback_url == 'https://example.com/webhook'
        
        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == 'https://www.strava.com/api/v3/push_subscriptions'
        assert call_args[1]['data']['callback_url'] == 'https://example.com/webhook'
        assert call_args[1]['data']['verify_token'] == 'verify_token'
    
    @patch('strava_sensor.webhook.subscription.requests.get')
    def test_list_subscriptions(self, mock_get):
        """Test listing webhook subscriptions."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                'id': 12345,
                'resource_state': 3,
                'application_id': 5678,
                'callback_url': 'https://example.com/webhook',
                'created_at': '2024-01-01T00:00:00Z',
                'updated_at': '2024-01-01T00:00:00Z'
            }
        ]
        mock_get.return_value = mock_response
        
        manager = WebhookSubscriptionManager('client_id', 'client_secret')
        
        subscriptions = manager.list_subscriptions()
        
        assert len(subscriptions) == 1
        assert subscriptions[0].id == 12345
        assert subscriptions[0].callback_url == 'https://example.com/webhook'
    
    @patch('strava_sensor.webhook.subscription.requests.delete')
    def test_delete_subscription(self, mock_delete):
        """Test deleting a webhook subscription."""
        mock_response = Mock()
        mock_delete.return_value = mock_response
        
        manager = WebhookSubscriptionManager('client_id', 'client_secret')
        
        manager.delete_subscription(12345)
        
        # Verify API call
        mock_delete.assert_called_once()
        call_args = mock_delete.call_args
        assert call_args[0][0] == 'https://www.strava.com/api/v3/push_subscriptions/12345'