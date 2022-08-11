#! /bin/env python3

import email
import re
import time

import tweepy
import yaml

from datetime import datetime, timedelta

from documentcloud import DocumentCloud
from imapclient import IMAPClient


with open('config.yaml') as f:
    config = yaml.safe_load(f)

def check_documentcloud():
    client = DocumentCloud()

    uploaded_docs = client.projects.get_by_id('208859').document_ids

    with open('seen_docs.yaml') as f:
        already_seen = yaml.safe_load(f)

    tweets = []
    for doc_id in uploaded_docs:
        if doc_id not in already_seen:
            doc = client.documents.get(doc_id)
            title = doc.title.replace(' (Twitter v. Musk)', '')
            reply = doc.data.get('tweetid',[''])[0]
            tweet = f'New document upload: {title} {doc.canonical_url}'
            tweets.append({'reply':reply,
                           'text':tweet})
            already_seen.append(doc_id)

    with open('seen_docs.yaml', 'w') as f:
        yaml.dump(already_seen, f)

    return tweets

def check_mail():
    mailserver = IMAPClient(config['imap_server'])

    mailserver.login(config['email_address'], config['email_password'])
    mailserver.select_folder('INBOX')

    search_start = datetime.today() - timedelta(days=2)

    msg_ids = mailserver.search(['FROM', 
            'AlertNotification@secure-mail.fileandservexpress.com',
            'SINCE',
            search_start,
            'UNSEEN'])

    tweets = []

    for msg_id, data in mailserver.fetch(msg_ids, 'RFC822').items():
        msg = email.message_from_bytes(data[b'RFC822']).as_string()

        senders = msg.split('Sending Parties:')[1].split('Document Title')[0].strip().replace('=\n','').split('\n\t')

        if 'Musk, Elon R.' in senders:
            trimmed_sender = 'Elon Musk'
        elif 'Twitter, Inc.' in senders:
            trimmed_sender = 'Twitter'
        else:
            trimmed_sender = senders[0]

        intro = f'New filing from {trimmed_sender}:'

        docs = msg.split('Document Title(s):')[1].split('Link to transaction')[0].strip().replace('=\n','').replace('=E2=80=99', "'").split('\n\t')
        match = re.search(r'(.*?)(\(\d+ pages\))', docs[0])
        doc_title, page_count = match.group(1).strip(), match.group(2)

        appendix = '(plus attachments)' if len(docs) > 1 else ''

        char_max = 280 - len(intro) - len(page_count) - len(appendix) - 5
        trunc_title = (doc_title[:char_max] + '…' if len(doc_title) > char_max
                        else doc_title)

        tweets.append({'reply':'',
                       'text':' '.join([intro, trunc_title,
                                        page_count, appendix])})

    mailserver.logout()

    return tweets

def main():
    dc_tweets = check_documentcloud()
    mail_tweets = check_mail()

    tweets = dc_tweets + mail_tweets

    if tweets:
        client = tweepy.Client(
                    consumer_key=config['twitter-api-key'],
                    consumer_secret=config['twitter-api-secret'],
                    access_token=config['twitter-token'],
                    access_token_secret=config['twitter-token-secret'])

        for tweet in tweets:
            print(tweet.get('text','hmmm no tweet text'))
            if tweet.get('reply'):
                client.create_tweet(text=tweet.get('text'),
                                in_repy_to_tweet_id=tweet.get('reply'))
            else:
                client.create_tweet(text=tweet.get('text'))

            time.sleep(10)

if __name__ == '__main__':
    main()
