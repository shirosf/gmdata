#!/usr/bin/python
from twitter_keys import CONSUMER_KEY, CONSUMER_SECRET
from oauth import oauth
from oauthtwitter import OAuthApi
import pprint

consumer_key = CONSUMER_KEY
consumer_secret = CONSUMER_SECRET

twitter = OAuthApi(consumer_key, consumer_secret)

# Get the temporary credentials for our next few calls
temp_credentials = twitter.getRequestToken()

# User pastes this into their browser to bring back a pin number
print(twitter.getAuthorizationURL(temp_credentials))

# Get the pin # from the user and get our permanent credentials
oauth_verifier = raw_input('What is the PIN? ')
access_token = twitter.getAccessToken(temp_credentials, oauth_verifier)

print("oauth_token: " + access_token['oauth_token'])
print("oauth_token_secret: " + access_token['oauth_token_secret'])

# Do a test API call using our new credentials
twitter = OAuthApi(consumer_key, consumer_secret, access_token['oauth_token'], access_token['oauth_token_secret'])
user_timeline = twitter.GetUserTimeline()

pp = pprint.PrettyPrinter(indent=4)
pp.pprint(user_timeline)
