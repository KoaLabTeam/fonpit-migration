from migration.users import handleUser

import logging
import models.apit as a
import models.wordpress as w
import json
import re
import phpserialize
from datetime import datetime

from tqdm import tqdm
from sqlalchemy import desc
from concurrent.futures import ThreadPoolExecutor as PoolExecutor
from slugify import slugify

log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_fmt,
                    filename='migration.log', filemode='w')


def syncForums(limit=1000):
    apitCategories = a.ForumCategory.q.filter(
        a.ForumCategory.deleted == 0, a.ForumCategory.language == 'de').limit(limit).all()
    maxresults = len(apitCategories)

    pbar = tqdm(total=maxresults)
    for category in apitCategories:
        forum = w.ForoForum.q.filter(
            w.ForoForum.forumid == category.id).first()
        if forum == None:
            forum = w.ForoForum()

        parentid = category.parentCategory_id
        if parentid == None:
            parentid = 0

        permissions = phpserialize.dumps([
            'full', 'moderator', 'standard', 'read_only', 'standard'
        ])

        permissions = 'a:5:{i:0;s:4:"full";i:1;s:9:"moderator";i:2;s:8:"standard";i:3;s:9:"read_only";i:4;s:8:"standard";}'

        is_cat = 0

        if category.parentCategory_id == None:
            is_cat = 1

        forum.forumid = category.id
        forum.title = category.name
        # slugify(category.name, separator="-")
        forum.slug = category.transcription_transcription
        forum.description = category.description
        forum.parentid = parentid
        forum.status = 0
        forum.order = 0  # category.pos
        forum.last_topicid = 0
        forum.last_postid = 0
        forum.last_userid = 0
        forum.last_post_date = datetime.now
        forum.permissions = permissions
        forum.is_cat = is_cat

        w.session.add(forum)
        w.session.commit()
        pbar.update(1)

    logging.info('starting syncin forums')


def syncThreads(limit=1000, chunksize=100):
    threadCount = a.session.query(a.ForumThread.id).filter(
        a.ForumThread.language == 'de').count()

    maxresults = min(threadCount, limit)
    offset = 0
    chunksize = min(chunksize, limit)
    pbar = tqdm(total=maxresults)

    def handleForumThreadsThreaded(threadId):
        w.session()
        a.session()
        wthread = handleForumThread(threadId)

        w.session.remove()
        a.session.remove()
        return wthread

    while True:
        chunk = a.session.query(a.ForumThread.id).order_by(desc(a.ForumThread.modificationDate)).filter(
            a.ForumThread.language == 'de').offset(offset).limit(chunksize).all()

        threadIds = [id[0] for id in chunk]

        if len(threadIds) > 0:
            with PoolExecutor(max_workers=10) as executor:
                for _ in executor.map(handleForumThreadsThreaded, threadIds):
                    pbar.update(1)
                    pass
        else:
            logging.info('no threads to import')

        offset += chunksize
        if (offset+chunksize) > maxresults:
            chunksize = maxresults - offset

        if len(chunk) < chunksize or offset >= maxresults:
            break


def handleForumThread(threadId):
    thread = a.ForumThread.q.filter(a.ForumThread.id == threadId).first()

    topic = w.ForoTopic.q.filter(w.ForoTopic.topicid == thread.id).first()
    wp_user = handleUser(thread.createdBy_id)

    if topic == None:
        topic = w.ForoTopic()

    topicExistingSlug = w.ForoTopic.q.filter(
        w.ForoTopic.slug == thread.transcription).first()
    slug = thread.transcription
    if topicExistingSlug != None:
        slug = f'{thread.transcription}-{thread.id}'

    topic.topicid = thread.id
    topic.forumid = thread.category_id
    topic.user = wp_user
    topic.created = thread.creationDate
    topic.modified = thread.modificationDate
    topic.title = thread.firstPost.title
    topic.slug = slug
    topic.status = 0

    w.session.add(topic)
    w.session.commit()


def syncForumPosts(limit=1000, chunksize=100):
    postCount = a.session.query(a.ForumPost.id).order_by(desc(a.ForumPost.modificationDate)).filter(
        a.ForumPost.language == 'de', a.ForumPost.deleted == 0).count()
    maxresults = min(postCount, limit)
    offset = 0
    chunksize = min(chunksize, limit)

    pbar = tqdm(total=maxresults)

    def handleForumPostThreaded(postId):
        w.session()
        a.session()
        wpost = handleForumPost(postId)

        w.session.remove()
        a.session.remove()
        return wpost

    while True:
        chunk = a.session.query(a.ForumPost.id).order_by(desc(a.ForumPost.modificationDate)).filter(
            a.ForumPost.language == 'de', a.ForumPost.deleted == 0).offset(offset).limit(chunksize).all()

        postIds = [id[0] for id in chunk]

        if len(postIds) > 0:
            with PoolExecutor(max_workers=10) as executor:
                for _ in executor.map(handleForumPostThreaded, postIds):
                    pbar.update(1)
                    pass
        else:
            logging.info('no posts to import')

        offset += chunksize
        if (offset+chunksize) > maxresults:
            chunksize = maxresults - offset

        if len(chunk) < chunksize or offset >= maxresults:
            break


def handleForumPost(postId):
    post = a.ForumPost.q.filter(a.ForumPost.id == postId).first()
    if post != None:
        wpost = w.ForoPost.q.filter(w.ForoPost.postid == post.id).first()
        if wpost == None:
            wpost = w.ForoPost()

        parentid = post.parentPost_id
        if parentid == None:
            parentid = 0

        wp_user = handleUser(post.createdBy_id)

        wpost.postid = post.id
        wpost.forumid = post.category_id
        wpost.topicid = post.thread_id
        wpost.user = wp_user
        wpost.title = post.title
        wpost.body = post.contentAsHtml
        wpost.created = post.creationDate
        wpost.modified = post.modificationDate
        wpost.parentid = parentid
        wpost.status = "0"

        w.session.add(wpost)
        w.session.commit()

        w.session.remove()
        a.session.remove()
        return wpost
    else:
        return None
