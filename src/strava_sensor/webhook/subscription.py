"""Strava webhook subscription management."""

import logging

import pydantic
import requests

_logger = logging.getLogger(__name__)


class SubscriptionResponse(pydantic.BaseModel):
    """Model for webhook subscription response."""
    
    id: int
    resource_state: int
    application_id: int
    callback_url: str
    created_at: str
    updated_at: str


class WebhookSubscriptionManager:
    """Manager for Strava webhook subscriptions."""
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = 'https://www.strava.com/api/v3'
    
    def create_subscription(self, callback_url: str, verify_token: str) -> SubscriptionResponse:
        """Create a new webhook subscription.
        
        Args:
            callback_url: URL where Strava will send webhook events
            verify_token: Token used for webhook verification
            
        Returns:
            Subscription details
            
        Raises:
            requests.HTTPError: If subscription creation fails
        """
        url = f'{self.base_url}/push_subscriptions'
        
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'callback_url': callback_url,
            'verify_token': verify_token
        }
        
        _logger.info('Creating webhook subscription for %s', callback_url)
        
        response = requests.post(url, data=data)
        response.raise_for_status()
        
        subscription = SubscriptionResponse.model_validate(response.json())
        _logger.info('Created subscription with ID %d', subscription.id)
        
        return subscription
    
    def list_subscriptions(self) -> list[SubscriptionResponse]:
        """List existing webhook subscriptions.
        
        Returns:
            List of subscription details
            
        Raises:
            requests.HTTPError: If listing fails
        """
        url = f'{self.base_url}/push_subscriptions'
        
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        _logger.info('Listing webhook subscriptions')
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        subscriptions = [SubscriptionResponse.model_validate(sub) for sub in response.json()]
        _logger.info('Found %d subscriptions', len(subscriptions))
        
        return subscriptions
    
    def delete_subscription(self, subscription_id: int) -> None:
        """Delete a webhook subscription.
        
        Args:
            subscription_id: ID of subscription to delete
            
        Raises:
            requests.HTTPError: If deletion fails
        """
        url = f'{self.base_url}/push_subscriptions/{subscription_id}'
        
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        _logger.info('Deleting webhook subscription %d', subscription_id)
        
        response = requests.delete(url, params=params)
        response.raise_for_status()
        
        _logger.info('Deleted subscription %d', subscription_id)
    
    def delete_all_subscriptions(self) -> None:
        """Delete all webhook subscriptions."""
        subscriptions = self.list_subscriptions()
        
        for subscription in subscriptions:
            self.delete_subscription(subscription.id)
        
        _logger.info('Deleted all %d subscriptions', len(subscriptions))