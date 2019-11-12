from datetime import datetime

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy import Table, Column, Integer, String, BigInteger, DateTime, Sequence, ForeignKey, Text, UniqueConstraint, join, SmallInteger
from sqlalchemy.orm import scoped_session, sessionmaker, relationship, backref, column_property

from urllib.parse import urlparse
from pathlib import Path
import os
import requests
import json
from slugify import slugify
import re
from requests.auth import HTTPBasicAuth
from requests.packages.urllib3.exceptions import InsecureRequestWarning

import logging
import config
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS + ":ECDHE-RSA-AES256-GCM-SHA384"

engine = create_engine(
    config.wpMysqlConnection, pool_size=50, max_overflow=0, echo=False)

session = scoped_session(sessionmaker(autocommit=False,
                                      autoflush=False,
                                      bind=engine))

Model = declarative_base(name='Model')
Model.q = session.query_property()


class WordpressAPI:

    def __init__(self, base_url=None, username=None, password=None):
        self.base_url = base_url
        self.auth = HTTPBasicAuth(username, password)

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
        res = s.send(prepared, verify=False)
        # print('//////////')
        # print(res.text)
        res.raise_for_status()
        return res

    def put(self, *args, **kwargs):
        res = requests.put(
            f'{self.base_url}{args[0]}', auth=self.auth, verify=False, **kwargs)
        res.raise_for_status()
        return res


api = WordpressAPI(
    base_url="https://androidpit.local/wp-json/wp/v2",
    username="marsch",
    password="itsch2san"
)


def createMediaFromUrl(url, mimeType='image/jpeg', props={}):
    if url == None:
        return None

    filename = os.path.basename(urlparse(url).path)
    logging.info(f'createMediaFromUrl downloading: {url}')
    mediaSrc = requests.get(url)

    headers = {
        'cache-control': 'no-cache',
        "Content-Disposition": f'attachment; filename="{filename}"',
        'content-type': mimeType
    }
    # print('headers', headers)
    logging.info(f'creating media from downloaded file for: {url}')
    res = api.post('/media', headers=headers, data=mediaSrc.content)
    mediaResponse = json.loads(res.text)
    mediaId = mediaResponse['id']

    logging.info(f'updating media from downloaded file with: {props}')
    updateres = api.put(f'/media/{mediaId}', data=json.dumps(props),
                        headers={'content-type': 'application/json'})

    return mediaId


class User(Model):
    __tablename__ = 'wp_users'

    ID = Column(BigInteger, Sequence('user_id_seq'), primary_key=True)
    user_login = Column(String(length=60), nullable=False)
    user_pass = Column(String(length=255), nullable=False)
    user_nicename = Column(String(length=50), nullable=False)
    user_email = Column(String(length=100), nullable=False)
    user_url = Column(String(length=100))
    user_registered = Column(DateTime)
    user_activation_key = Column(String(length=255))
    user_status = Column(Integer)
    display_name = Column(String(length=250))

    meta = relationship("UserMeta", collection_class=attribute_mapped_collection('meta_key'), back_populates='user',
                        cascade='all, delete, delete-orphan')
    posts = relationship('Post', back_populates='author')

    comments = relationship('Comment', back_populates='user')
    links = relationship('Link', back_populates='owner')

    def __repr__(self):
        return "<WpUser(login='%s', email='%s', display_name='%s')>\n" % (self.user_login, self.user_email, self.display_name)

    def addMeta(self, key, value):
        if self.meta.get(key) == None:
            m = UserMeta(key, value)
            m.user = self
        else:
            self.meta[key].meta_value = value
# get by legacy
# y = session.query(User).join(UserMeta).filter(UserMeta.meta_value=='1225228').all()


class UserMeta(Model):
    __tablename__ = 'wp_usermeta'
    umeta_id = Column(BigInteger, Sequence(
        'usermeta_id_seq'), primary_key=True)
    user_id = Column(BigInteger, ForeignKey('wp_users.ID'))
    meta_key = Column(String(length=255))
    meta_value = Column(Text(length=None))
    user = relationship('User', back_populates='meta')

    def __repr__(self):
        return f"<WpUserMeta(umeta_id={self.umeta_id} meta_key='{self.meta_key}' meta_value='{self.meta_value}')>\n"

    def __init__(self, key, value):
        self.meta_key = key
        self.meta_value = value


class PostMeta(Model):
    # Table fields
    __tablename__ = 'wp_postmeta'
    meta_id = Column(Integer, primary_key=True, nullable=False)
    post_id = Column(Integer, ForeignKey('wp_posts.ID'), nullable=False)
    meta_key = Column(String(length=255), primary_key=False, nullable=True)
    meta_value = Column(Text(length=None), primary_key=False, nullable=True)

    # ORM layer relationships
    post = relationship('Post', back_populates='meta')

    def __repr__(self):
        return f"<WpPostMeta(meta_id={self.meta_id} meta_key='{self.meta_key}' meta_value='{self.meta_value}')>\n"

    def __init__(self, key, value):
        self.meta_key = key
        self.meta_value = value


TERM_TABLE = Table(
    "wp_terms", Model.metadata,
    Column('term_id', Integer, primary_key=True, nullable=False),
    Column('name', String(length=55), nullable=False),
    Column('slug', String(length=200), nullable=False),
    Column('term_group', Integer, nullable=False, default=0),
    UniqueConstraint('slug'),
)

TERM_TAXONOMY_TABLE = Table(
    "wp_term_taxonomy", Model.metadata,
    Column('term_taxonomy_id', Integer, primary_key=True, nullable=False),
    Column('term_id', Integer, ForeignKey('wp_terms.term_id'), nullable=False),
    Column('taxonomy', String(length=32), nullable=False),
    Column('description', Text(length=None), nullable=False, default=''),
    Column('parent', Integer, ForeignKey(
        'wp_term_taxonomy.term_taxonomy_id'), nullable=False, default=0),
    Column('count', Integer, nullable=False, default=0),
    UniqueConstraint('term_id', 'taxonomy'),
)

TERM_TAXONOMY_JOIN = join(TERM_TABLE, TERM_TAXONOMY_TABLE)

TERM_RELATIONSHIP_TABLE = Table(
    'wp_term_relationships', Model.metadata,
    Column('object_id', Integer, ForeignKey(
        'wp_posts.ID'), primary_key=True, nullable=False),
    Column('term_taxonomy_id', Integer, ForeignKey(
        TERM_TAXONOMY_TABLE.c.term_taxonomy_id), primary_key=True, nullable=False)
)


class Post(Model):
    # Table fields
    __tablename__ = 'wp_posts'
    ID = Column(Integer, primary_key=True, nullable=False)
    post_author = Column(Integer, ForeignKey(
        'wp_users.ID'), nullable=False, default=0)
    post_date = Column(DateTime(timezone=False),
                       nullable=False, default=datetime.utcnow)
    post_date_gmt = Column(DateTime(timezone=False),
                           nullable=False, default=datetime.utcnow)
    post_content = Column(Text(length=None), nullable=False)
    post_title = Column(Text(length=None), nullable=False)
    post_excerpt = Column(Text(length=None), nullable=False, default='')
    post_status = Column(String(length=10), nullable=False, default='publish')
    comment_status = Column(String(length=15), nullable=False, default='open')
    ping_status = Column(String(length=6), nullable=False, default='open')
    post_password = Column(String(length=20), nullable=False, default='')
    post_name = Column(String(length=200), nullable=False)
    to_ping = Column(Text(length=None), nullable=False, default='')
    pinged = Column(Text(length=None), nullable=False, default='')
    post_modified = Column(DateTime(timezone=False),
                           nullable=False, default=datetime.utcnow)
    post_modified_gmt = Column(
        DateTime(timezone=False), nullable=False, default=datetime.utcnow)
    post_content_filtered = Column(
        Text(length=None), nullable=False, default='')
    post_parent = Column(Integer, ForeignKey(
        'wp_posts.ID'), nullable=False, default=0)
    guid = Column(String(length=255), nullable=False, default='')
    menu_order = Column(Integer, nullable=False, default=0)
    post_type = Column(String(length=20), nullable=False, default='post')
    post_mime_type = Column(String(length=100), nullable=False, default='')
    comment_count = Column(Integer, nullable=False, default=0)

    # ORM layer relationships
    author = relationship('User', back_populates='posts')
    children = relationship(
        'Post',
        backref=backref('parent', remote_side=[ID]))
    comments = relationship('Comment', back_populates="post")
    meta = relationship('PostMeta', collection_class=attribute_mapped_collection(
        'meta_key'), back_populates="post")
    terms = relationship(
        "Term",
        secondary=TERM_RELATIONSHIP_TABLE,
        back_populates='posts')

    def __repr__(self):
        return f"<WpPost(ID={self.ID} post_type='{self.post_type}' post_title='{self.post_title}')>\n"

    def addMeta(self, key, value):
        if self.meta.get(key) == None:
            m = PostMeta(key, value)
            m.post = self
        else:
            self.meta[key].meta_value = value

# for just create a #%%
# k = Term(slug='kakkakakaakakak', name='MEGAKKKKK', taxonomy='category')


class Term(Model):
    # Table fields
    __table__ = TERM_TAXONOMY_JOIN
    id = column_property(
        TERM_TABLE.c.term_id,
        TERM_TAXONOMY_TABLE.c.term_id)

    # ORM layer relationships
    posts = relationship(
        "Post",
        secondary=TERM_RELATIONSHIP_TABLE,
        back_populates='terms')

    meta = relationship("TermMeta", collection_class=attribute_mapped_collection(
        'meta_key'), back_populates='term')

    def __repr__(self):
        return f"<WpTerm(ID={self.id} name='{self.name}' slug='{self.slug}') taxonomy='{self.taxonomy}')>\n"


class TermMeta(Model):
    __tablename__ = 'wp_termmeta'
    meta_id = Column(BigInteger, primary_key=True)
    term_id = Column(BigInteger, ForeignKey('wp_terms.term_id'))
    meta_key = Column(String(length=255))
    meta_value = Column(Text(length=None))
    term = relationship('Term', back_populates='meta')

    def __repr__(self):
        return f"<WpTermMeta(meta_id={self.meta_id} meta_key='{self.meta_key}' meta_value='{self.meta_value}')"


class Comment(Model):
    # Table fields
    __tablename__ = 'wp_comments'
    comment_ID = Column(Integer, primary_key=True, nullable=False)
    comment_post_ID = Column(
        Integer, ForeignKey('wp_posts.ID'), nullable=False)
    comment_author = Column(Text(length=None), nullable=False, default='')
    comment_author_email = Column(
        String(length=100), nullable=False, default='')
    comment_author_url = Column(String(length=200), nullable=False, default='')
    comment_author_IP = Column(String(length=100), nullable=False, default='')
    comment_date = Column(DateTime(timezone=False),
                          nullable=False, default=datetime.utcnow)
    comment_date_gmt = Column(DateTime(timezone=False),
                              nullable=False, default=datetime.utcnow)

    comment_content = Column(Text(length=None), nullable=False)
    comment_karma = Column(Integer, nullable=False, default=0)
    comment_approved = Column(String(length=4), nullable=False)
    comment_agent = Column(String(length=255), nullable=False, default='')
    comment_type = Column(String(length=20), nullable=False, default='')
    comment_parent = Column(Integer, ForeignKey(
        'wp_comments.comment_ID'), nullable=False, default=0)
    user_id = Column(Integer, ForeignKey('wp_users.ID'), nullable=False)

    # ORM layer relationships
    post = relationship('Post', back_populates="comments")
    children = relationship(
        'Comment',
        backref=backref('parent', remote_side=[comment_ID])
    )
    user = relationship('User', back_populates="comments")
    meta = relationship('CommentMeta', collection_class=attribute_mapped_collection(
        'meta_key'), back_populates='comment')

    likes = relationship('ULikeComments', collection_class=attribute_mapped_collection(
        'user_id'), back_populates='comment')

    def __repr__(self):
        return f"<WpComment(meta_id={self.comment_ID} comment_content='{self.comment_content}' comment_type='{self.comment_type}')"

    def addMeta(self, key, value):
        if self.meta.get(key) == None:
            m = CommentMeta(key, value)
            m.comment = self
        else:
            self.meta[key].meta_value = value

    def addLike(self, user_id, status, date_time):
        key = f'{user_id}'
        if self.likes.get(key) == None:
            l = ULikeComments(user_id, status, date_time)
            l.comment = self
        else:
            existing = self.likes.get(key)
            existing.status = status
            existing.date_time = date_time


class CommentMeta(Model):
    __tablename__ = 'wp_commentmeta'
    meta_id = Column(BigInteger, primary_key=True)
    comment_id = Column(BigInteger, ForeignKey('wp_comments.comment_ID'))
    meta_key = Column(String(length=255))
    meta_value = Column(Text(length=None))
    comment = relationship('Comment', back_populates='meta')

    def __repr__(self):
        return f"<WpCommentMeta(meta_id={self.meta_id} meta_key='{self.meta_key}' meta_value='{self.meta_value}')"

    def __init__(self, key, value):
        self.meta_key = key
        self.meta_value = value


class Link(Model):
    # Table fields
    __tablename__ = 'wp_links'
    link_id = Column(Integer, primary_key=True, nullable=False)
    link_url = Column(String(length=255), nullable=False)
    link_name = Column(String(length=255), nullable=False)
    link_image = Column(String(length=255), nullable=False)
    link_target = Column(String(length=25), nullable=False)
    link_description = Column(String(length=255), nullable=False)
    link_visible = Column(String(length=1), nullable=False)
    link_owner = Column(Integer, ForeignKey('wp_users.ID'), nullable=False)
    link_rating = Column(Integer, nullable=False)
    link_updated = Column(DateTime(timezone=False), nullable=False)
    link_rel = Column(String(length=255), nullable=False)
    link_notes = Column(Text(length=None), nullable=False)
    link_rss = Column(String(length=255), nullable=False)

    # ORM layer relationships
    owner = relationship('User', back_populates="links")

    def __repr__(self):
        return f"<WpLink(link_id={self.link_id} link_url='{self.link_url}' link_name='{self.link_name}')"


class Option(Model):
    # Table fields
    __tablename__ = 'wp_options'
    option_id = Column(Integer, primary_key=True, nullable=False)
    blog_id = Column(Integer, primary_key=True, nullable=False)
    option_name = Column(String(length=64), primary_key=True, nullable=False)
    option_value = Column(Text(length=None), nullable=False)
    autoload = Column(String(length=3), nullable=False)

    def __repr__(self):
        return f"<WpOption(option_id={self.option_id} option_name='{self.option_name}' option_value='{self.option_value}')"


class ULikeComments(Model):
    __tablename__ = 'wp_ulike_comments'
    id = Column(BigInteger, primary_key=True, nullable=False)
    comment_id = Column(BigInteger, ForeignKey('wp_comments.comment_ID'))
    date_time = Column(DateTime(timezone=False),
                       nullable=False, default=datetime.utcnow)
    ip = Column(String(length=100), default='')
    user_id = Column(BigInteger, ForeignKey('wp_users.ID'))
    status = Column(String(length=30))

    comment = relationship('Comment', back_populates='likes')

    def __repr__(self):
        return f"<WpULikeComments(id={self.id} comment_id='{self.comment_id}' user_id='{self.user_id}' status='{self.status}')"

    def __init__(self, user_id, status, date_time):
        self.user_id = user_id
        self.status = status
        self.date_time = date_time

# wp_foro


class ForoAccess(Model):
    __tablename__ = 'wp_wpforo_accesses'
    accessid = Column(Integer, primary_key=True)
    access = Column(String(length=255))
    title = Column(String(length=255))
    cans = Column(Text)


class ForoActivity(Model):
    __tablename__ = 'wp_wpforo_activity'
    id = Column(BigInteger, primary_key=True)
    type = Column(String(length=60))
    itemid = Column(BigInteger)
    itemtype = Column(String(length=60))
    itemid_second = Column(BigInteger)
    userid = Column(BigInteger, ForeignKey('wp_users.ID'))
    name = Column(String(length=60))
    email = Column(String(length=70))
    date = Column(Integer)
    content = Column(Text)
    permalink = Column(String(length=255))

    user = relationship('User', foreign_keys=[userid])


class ForoForum(Model):
    __tablename__ = 'wp_wpforo_forums'
    forumid = Column(Integer, primary_key=True)
    title = Column(String(length=255))
    slug = Column(String(length=255))
    description = Column(Text)
    parentid = Column(Integer, ForeignKey('wp_wpforo_forums.forumid'))
    icon = Column(String(length=255))
    last_topicid = Column(Integer, ForeignKey('wp_wpforo_topics.topicid'))
    last_postid = Column(Integer, ForeignKey('wp_wpforo_posts.postid'))
    last_userid = Column(Integer, ForeignKey('wp_users.ID'))
    last_post_date = Column(DateTime, default=datetime.utcnow)
    topics = Column(Integer, default=0)
    posts = Column(Integer, default=0)
    permissions = Column(Text)
    meta_key = Column(Text)
    meta_desc = Column(Text)
    status = Column(Integer)
    is_cat = Column(Integer)
    cat_layout = Column(Integer, default=1)
    order = Column(Integer, default=0)
    color = Column(String(length=7), default='#666666')

    parent = relationship('ForoForum', foreign_keys=[
                          parentid], back_populates='children', uselist=False)
    children = relationship(
        'ForoForum', back_populates='parent', remote_side=[forumid])

    last_topic = relationship('ForoTopic', foreign_keys=[last_topicid])
    last_post = relationship('ForoPost', foreign_keys=[last_postid])
    last_user = relationship('User', foreign_keys=[last_userid])


class ForoLanguage(Model):
    __tablename__ = 'wp_wpforo_languages'
    langid = Column(Integer, primary_key=True)
    name = Column(String(length=255))


class ForoLikes(Model):
    __tablename__ = 'wp_wpforo_likes'
    likeid = Column(Integer, primary_key=True)
    userid = Column(Integer)
    postid = Column(Integer)
    post_userid = Column(Integer)


class ForoPhrase(Model):
    __tablename__ = 'wp_wpforo_phrases'
    phraseid = Column(Integer, primary_key=True)
    langid = Column(Integer, ForeignKey('wp_wpforo_languages.langid'))
    phrase_key = Column(Text)
    phrase_value = Column(Text)
    package = Column(String(length=255))

    lang = relationship('ForoLanguage', foreign_keys=[langid], uselist=False)


class ForoPost(Model):
    __tablename__ = 'wp_wpforo_posts'
    postid = Column(BigInteger, primary_key=True)
    parentid = Column(BigInteger, ForeignKey('wp_wpforo_posts.postid'))
    forumid = Column(Integer, ForeignKey('wp_wpforo_forums.forumid'))
    topicid = Column(BigInteger, ForeignKey('wp_wpforo_topics.topicid'))
    userid = Column(Integer, ForeignKey('wp_users.ID'))
    title = Column(String(length=255))
    body = Column(Text)
    created = Column(DateTime, default=datetime.utcnow)
    modified = Column(DateTime, default=datetime.utcnow)
    likes = Column(Integer, default=0)
    votes = Column(Integer, default=0)
    is_answer = Column(Integer, default=0)
    is_first_post = Column(Integer, default=0)
    status = Column(Integer, default="0")
    name = Column(String(length=50), default='')
    email = Column(String(length=50), default='')
    private = Column(Integer, default=0)
    root = Column(Integer, default=-1)

    parent = relationship('ForoPost', foreign_keys=[
                          parentid], back_populates='children')
    children = relationship('ForoPost', remote_side=[
                            postid], back_populates='parent')
    forum = relationship('ForoForum', foreign_keys=[
                         forumid])
    topic = relationship('ForoTopic', foreign_keys=[topicid])
    user = relationship('User', foreign_keys=[userid])


class ForoProfile(Model):
    __tablename__ = 'wp_wpforo_profiles'
    userid = Column(Integer, primary_key=True)
    title = Column(String(length=255))
    username = Column(String(length=255))
    groupid = Column(Integer, ForeignKey('wp_wpforo_usergroups.groupid'))
    posts = Column(Integer)
    questions = Column(Integer)
    answers = Column(Integer)
    comments = Column(Integer)
    site = Column(String(length=255))
    icq = Column(String(length=50))
    aim = Column(String(length=50))
    yahoo = Column(String(length=50))
    msn = Column(String(length=50))
    facebook = Column(String(length=255))
    twitter = Column(String(length=255))
    gtalk = Column(String(length=50))
    skype = Column(String(length=50))
    avatar = Column(String(length=255))
    signature = Column(Text)
    about = Column(Text)
    occupation = Column(Text)
    location = Column(String(length=255))
    last_login = Column(DateTime)
    online_time = Column(Integer)
    rank = Column(Integer)
    like = Column(Integer)
    status = Column(String(length=8))
    timezone = Column(String(length=255))
    is_email_confirmed = Column(Integer)
    secondary_groups = Column(String(length=255))
    fields = Column(Text)

    group = relationship('ForoUserGroup', foreign_keys=[groupid])


class ForoSubscribe(Model):
    __tablename__ = 'wp_wpforo_subscribes'
    subid = Column(BigInteger, primary_key=True)
    itemid = Column(BigInteger)
    type = Column(String(length=50))
    confirmkey = Column(String(length=32))
    userid = Column(BigInteger, ForeignKey('wp_users.ID'))
    active = Column(SmallInteger)
    user_name = Column(String(length=60))
    user_email = Column(String(length=60))

    user = relationship('User', foreign_keys=[userid])


class ForoTag(Model):
    __tablename__ = 'wp_wpforo_tags'
    tagid = Column(BigInteger, primary_key=True)
    tag = Column(String(length=255))
    prefix = Column(SmallInteger)
    count = Column(Integer)


class ForoTopic(Model):
    __tablename__ = 'wp_wpforo_topics'
    topicid = Column(BigInteger, primary_key=True)
    forumid = Column(Integer, ForeignKey('wp_wpforo_forums.forumid'))
    first_postid = Column(BigInteger, ForeignKey(
        'wp_wpforo_posts.postid'), default=0)
    userid = Column(Integer, ForeignKey('wp_users.ID'))
    title = Column(String(length=255))
    slug = Column(String(length=255))
    created = Column(DateTime)
    modified = Column(DateTime)
    last_post = Column(BigInteger, ForeignKey(
        'wp_wpforo_posts.postid'), default=0)
    posts = Column(Integer, default=0)
    votes = Column(Integer, default=0)
    answers = Column(Integer, default=0)
    meta_key = Column(Text, default="")
    meta_desc = Column(Text, default="")
    type = Column(SmallInteger, default=0)
    solved = Column(SmallInteger, default=0)
    closed = Column(SmallInteger, default=0)
    has_attach = Column(SmallInteger, default=0)
    private = Column(SmallInteger, default=0)
    status = Column(SmallInteger, default=1)
    name = Column(String(length=50), default='')
    email = Column(String(length=50), default='')
    prefix = Column(String(length=100), default='')
    tags = Column(Text, default='')

    forum = relationship('ForoForum', foreign_keys=[forumid])
    user = relationship('User', foreign_keys=[userid])
    last_post_item = relationship('ForoPost', foreign_keys=[last_post])
    first_post_item = relationship('ForoPost', foreign_keys=[first_postid])


class ForoUserGroup(Model):
    __tablename__ = 'wp_wpforo_usergroups'
    groupid = Column(Integer, primary_key=True)
    name = Column(String(length=255))
    cans = Column(Text)
    description = Column(Text)
    utitle = Column(String(length=100))
    role = Column(String(length=50))
    access = Column(String(length=50))
    color = Column(String(length=7))
    visible = Column(SmallInteger)
    secondary = Column(SmallInteger)


class ForoViews(Model):
    __tablename__ = 'wp_wpforo_views'
    vid = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey('wp_users.ID'))
    topicid = Column(Integer, ForeignKey('wp_wpforo_topics.topicid'))
    created = Column(DateTime)

    user = relationship('User', foreign_keys=[userid])
    topic = relationship('ForoTopic', foreign_keys=[topicid])


class ForoVisit(Model):
    __tablename__ = 'wp_wpforo_visits'
    id = Column(BigInteger, primary_key=True)
    userid = Column(BigInteger, ForeignKey('wp_users.ID'))
    name = Column(String(length=60))
    ip = Column(String(length=60))
    time = Column(Integer)
    forumid = Column(Integer, ForeignKey('wp_wpforo_forums.forumid'))
    topicid = Column(BigInteger, ForeignKey('wp_wpforo_topics.topicid'))

    user = relationship('User', foreign_keys=[userid])
    forum = relationship('ForoForum', foreign_keys=[forumid])
    topic = relationship('ForoTopic', foreign_keys=[topicid])


class ForoVote(Model):
    __tablename__ = 'wp_wpforo_votes'
    voteid = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey('wp_users.ID'))
    postid = Column(Integer, ForeignKey('wp_wpforo_posts.postid'))
    reaction = Column(SmallInteger)
    post_userid = Column(Integer, ForeignKey('wp_users.ID'))

    user = relationship('User', foreign_keys=[userid])
    post = relationship('ForoPost', foreign_keys=[postid])
    post_user = relationship('User', foreign_keys=[post_userid])
