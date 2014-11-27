#!/usr/bin/python
# run 'oauth_sample.py' to update twitter_oauth_keys.py
from twitter_keys import CONSUMER_KEY, CONSUMER_SECRET
from twitter_oauth_keys import OAUTH_TOKEN, OAUTH_TOKEN_SECRET
from oauth import oauth
from oauthtwitter import OAuthApi
import twitter

encoding = 'utf-8'
message = 'Test Message'

#otw = OAuthApi(CONSUMER_KEY, CONSUMER_SECRET, oauth_token, oauth_token_secret)
#otw.PostUpdate("Test Message")

api = twitter.Api(consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET,
                    access_token_key=OAUTH_TOKEN, access_token_secret=OAUTH_TOKEN_SECRET,
                    input_encoding=encoding)
try:
    status = api.PostUpdate(message)
except UnicodeDecodeError:
    print "Your message could not be encoded.  Perhaps it contains non-ASCII characters? "
    print "Try explicitly specifying the encoding with the --encoding flag"
    sys.exit(2)

print "%s just posted: %s" % (status.user.name, status.text)

