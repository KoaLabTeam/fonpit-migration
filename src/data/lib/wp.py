import pandas as pd
from dotenv import find_dotenv, load_dotenv
from pathlib import Path
import logging
import os
from sqlalchemy import create_engine
from tqdm import tqdm

import requests
from requests_oauthlib import OAuth1
import json
from slugify import slugify
import re

from concurrent.futures import ThreadPoolExecutor as PoolExecutor

from requests.auth import HTTPBasicAuth


# delete all media
# DELETE FROM `wp_posts` WHERE `post_type` = "attachment";
# DELETE FROM `wp_postmeta` WHERE `meta_key` = "_wp_attached_file";
# DELETE FROM `wp_postmeta` WHERE `meta_key` = "_wp_attachment_metadata";
##


class WordpressAPI:

    def __init__(self, base_url=None, username=None, password=None):
        self.base_url = base_url
        self.auth = HTTPBasicAuth(username, password)
        # self.auth = OAuth1(consumer_key, consumer_secret, token, token_secret)

    def pretty_print_POST(self, req):
        print('{}\n{}\r\n{}\r\n\r\n{}'.format(
            '-----------START-----------',
            req.method + ' ' + req.url,
            '\r\n'.join('{}: {}'.format(k, v) for k, v in req.headers.items()),
            req.body,
        ))

    def get(self, *args, **kwargs):
        res = requests.get(
            f'{self.base_url}{args[0]}', auth=self.auth, **kwargs)
        res.raise_for_status()
        return res

    def post(self, *args, **kwargs):
        req = requests.Request('POST',
                               f'{self.base_url}{args[0]}', auth=self.auth, **kwargs)
        prepared = req.prepare()

        # debugg it? just uncommend
        # self.pretty_print_POST(prepared)
        s = requests.Session()
        res = s.send(prepared)
        # print('//////////')
        # print(res.text)
        res.raise_for_status()
        return res

    def put(self, *args, **kwargs):
        res = requests.put(
            f'{self.base_url}{args[0]}', auth=self.auth, **kwargs)
        res.raise_for_status()
        return res


api = WordpressAPI(
    base_url="http://androidpit.local/wp-json/wp/v2",
    username="marsch",
    password="itsch2san"
)

wp_engine = create_engine(
    'mysql+pymysql://root:root@192.168.95.100:4022/local'
)


def getWpCategories():

    categories_query = f'''
    SELECT t.*
    FROM
        local.wp_terms t,
        local.wp_term_taxonomy tx
    WHERE
        t.term_id = tx.term_id
    AND tx.taxonomy = 'category'
    '''

    categories = pd.read_sql(categories_query, wp_engine, index_col='slug')
    return categories
    # print(categories)
    # print('ifa?', categories.loc['ifa'].term_id)


def getWpPostTags():
    posttag_query = f'''
    SELECT t.*
    FROM
        local.wp_terms t,
        local.wp_term_taxonomy tx
    WHERE
        t.term_id = tx.term_id
    AND tx.taxonomy = 'post_tag'
    '''

    posttags = pd.read_sql(posttag_query, wp_engine, index_col='slug')
    return posttags


def getWpUsers():
    users_query = f'''
    SELECT wu.*, wum.meta_value as legacy_user_id FROM wp_users wu, wp_usermeta wum WHERE wu.ID=wum.user_id AND wum.meta_key='legacy_user_id'
    '''
    users = pd.read_sql(users_query, wp_engine, index_col=['legacy_user_id'])
    return users


def getWpMediaFiles():
    media_query = f'''
    SELECT wp.*, wpm.meta_value as legacy_userfile_id FROM wp_posts wp, wp_postmeta wpm WHERE wp.post_type='attachment' AND wpm.post_id=wp.id AND wpm.meta_key='legacy_userfile_id'
    '''
    # media_query = f'''
    # SELECT * FROM local.wp_posts WHERE post_type='attachment';
    # '''
    attachments = pd.read_sql(media_query, wp_engine,
                              index_col=['legacy_userfile_id'])
    return attachments


def getWpPosts():
    post_query = f'''
      SELECT 
        wp.ID,
        wp.post_author,
        wp.post_date,
        wp.post_date_gmt,
        wp.post_content,
        wp.post_title,
        wp.post_excerpt,
        wp.post_status,
        wp.comment_status,
        wp.ping_status,
        wp.post_name,
        wpm.meta_value as legacy_article_id
      FROM local.wp_posts wp, wp_postmeta wpm WHERE wp.post_type = 'post' AND wp.ID = wpm.post_id AND meta_key='legacy_article_id'
    '''
    posts = pd.read_sql(post_query, wp_engine, index_col=["legacy_article_id"])
    return posts
