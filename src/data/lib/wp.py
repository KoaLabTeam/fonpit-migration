import pandas as pd
from urllib.parse import urlparse
from dotenv import find_dotenv, load_dotenv
from pathlib import Path
import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.sql.expression import text
from tqdm import tqdm
import phpserialize

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


def getWpPostByLegacyArticleId(legacyArticleId):
    post_query = f'''
    SELECT
        wp.*,
        wpm.meta_value as legacy_article_id
    FROM wp_posts wp, wp_postmeta wpm
    WHERE
        wp.ID=wpm.post_id
        AND wpm.meta_key='legacy_article_id'
        AND wpm.meta_value='{legacyArticleId}';
    '''
    posts = pd.read_sql(post_query, wp_engine, index_col=[
                        "legacy_article_id"]).to_records()

    if len(posts) > 0:
        return posts[0]
    else:
        return None


def getTermIdByTaxonomyAndSlugname(taxonomy='category', slug=None):
    taxonomy_query = f'''
    SELECT t.*
    FROM
        local.wp_terms t,
        local.wp_term_taxonomy tx
    WHERE
        t.term_id = tx.term_id
    AND tx.taxonomy = '{taxonomy}'
    AND t.slug = '{slug}'
    '''
    terms = pd.read_sql(taxonomy_query, wp_engine).to_records()

    if len(terms) > 0:
        return terms[0]
    else:
        return None


def getUserByLegacyUserId(legacy_user_id):
    logging.info(
        f'looking for wordpress user by legacy_user_id: {legacy_user_id}')
    users_query = f'''
    SELECT wu.*, wum.meta_value as legacy_user_id FROM wp_users wu, wp_usermeta wum WHERE wu.ID=wum.user_id AND wum.meta_key='legacy_user_id' AND wum.meta_value='{legacy_user_id}'
    '''

    users = pd.read_sql(users_query, wp_engine, index_col=[
                        'legacy_user_id']).to_records()
    if len(users) > 0:
        logging.info('found')
        return users[0]
    else:
        logging.info('not found')
        return None


def createMediaFromUrl(url, mimeType='image/jpeg', props={}):
    if url == None:
        return None

    filename = os.path.basename(urlparse(url).path)
    mediaSrc = requests.get(url)
    headers = {
        'cache-control': 'no-cache',
        "Content-Disposition": f'attachment; filename="{filename}"',
        'content-type': mimeType
    }
    # print('headers', headers)
    res = api.post('/media', headers=headers, data=mediaSrc.content)
    mediaResponse = json.loads(res.text)
    mediaId = mediaResponse['id']

    updateres = api.put(f'/media/{mediaId}', data=json.dumps(props),
                        headers={'content-type': 'application/json'})

    return mediaId


def getMediaFromLegacy(id='', key='legacy_userfile_id'):
    mediaQuery = f'''
    SELECT wp.*, wpm.meta_value as {key} FROM wp_posts wp, wp_postmeta wpm WHERE wp.post_type='attachment' AND wp.ID=wpm.post_id AND wpm.meta_key='{key}' AND wpm.meta_value='{id}' LIMIT 1
    '''

    medias = pd.read_sql(mediaQuery, wp_engine, index_col=[
        key]).to_records()

    if len(medias) > 0:
        return medias[0]
    else:
        return None


def getCommentFromLegacy(id='', key='legacy_comment_id'):
    commentQuery = f'''
    SELECT
        c.*,
        cm.meta_value as {key}
    FROM
        wp_comments c,
        wp_commentmeta cm
    WHERE
        c.comment_ID = cm.comment_id
        AND cm.meta_key='{key}'
        AND cm.meta_value='{id}'
    '''

    comments = pd.read_sql(commentQuery, wp_engine,
                           index_col=[key]).to_records()
    if len(comments) > 0:
        return comments[0]
    else:
        return None


def getCommentsWithLegacyParentByPostId(postId):
    commentQuery = f'''
    SELECT
        c.*,
        cm.meta_value as legacy_comment_parentid
    FROM
        wp_comments c,
        wp_commentmeta cm
    WHERE
        c.comment_post_ID={postId}
        AND c.comment_ID = cm.comment_id
        AND cm.meta_key='legacy_comment_parentid'
        AND cm.meta_value!=0
    '''

    comments = pd.read_sql(commentQuery, wp_engine).to_records()
    if len(comments) > 0:
        return comments
    else:
        return None


def createWpUserViaSQL(payload):
    logging.info(f'create using sql {payload}')
    userslug = slugify(payload['username'])

    rs = wp_engine.execute(text("INSERT INTO `wp_users` (`user_login`, `user_pass`, `user_nicename`, `user_email`, `user_registered`, `user_status`, `display_name`) VALUES (:username, :name, :userslug, :email, :registerdate, :status, :displayname)"),
                           username=payload['username'], name=payload['name'], userslug=userslug, email=payload['email'], registerdate='2019-10-17 12:00:00', status=0, displayname=payload['name'])

    user_id = rs.lastrowid
    logging.info(f'user_id {user_id}')

    if len(payload['roles']) > 0:
        # [{x: True}   for x in payload['roles']]
        capabilities = {payload['roles'][0]: True}
        capabilities = phpserialize.dumps(capabilities)
    else:
        capabilities = ''

    insertUserMetaField(user_id, 'nickname', payload['email'])
    insertUserMetaField(user_id, 'first_name', payload['first_name'])
    insertUserMetaField(user_id, 'last_name', payload['last_name'])
    insertUserMetaField(user_id, 'locale', payload['locale'])
    insertUserMetaField(user_id, 'description', payload['description'])
    insertUserMetaField(user_id, 'wp_capabilities', capabilities)
    insertUserMetaField(user_id, 'wp_user_avatar',
                        payload['meta']['wp_user_avatar'])
    insertUserMetaField(user_id, 'legacy_user_id',
                        payload['meta']['legacy_user_id'])

    logging.info(f'inserted meta data')
    # meta_rs = wp_engine.execute(meta_q)
    return user_id


def insertUserMetaField(user_id, meta_key, meta_value):
    wp_engine.execute(text("INSERT INTO `wp_usermeta` (`user_id`, `meta_key`, `meta_value`) VALUES (:user_id, :meta_key, :meta_value)"),
                      user_id=user_id, meta_key=meta_key, meta_value=meta_value)
