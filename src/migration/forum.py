from migration.users import handleUser

import logging
import models.apit as a
import models.wordpress as w
import json
import re
import phpserialize
from datetime import datetime

from tqdm import tqdm
from sqlalchemy import desc, and_
from concurrent.futures import ThreadPoolExecutor as PoolExecutor
from slugify import slugify
import string
import random

log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.ERROR, format=log_fmt,
                    filename='migration.log', filemode='w')

forum_log = tqdm(total=0, bar_format='{desc}', position=1, leave=True)
thread_log = tqdm(total=0, bar_format='{desc}', position=3, leave=True)
post_log = tqdm(total=0, bar_format='{desc}', position=5, leave=True)


def syncForums(limit=1000, query=and_(a.ForumCategory.deleted == 0, a.ForumCategory.language == 'de')):

    apitCategories = a.ForumCategory.q.filter(query).limit(limit).all()
    maxresults = len(apitCategories)

    pbar = tqdm(total=maxresults, desc='Forums', position=0, leave=True)

    for category in apitCategories:

        forum_log.set_description_str(f'📚  Forum: {category.name[:40]}...')
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
        forum.slug = category.transcription_transcription
        forum.description = category.description
        forum.parentid = parentid
        forum.status = 0
        forum.order = 0  # category.pos
        forum.last_topicid = 0
        forum.last_postid = 0
        forum.last_userid = 0
        # forum.last_post_date = datetime.utcnow
        forum.permissions = permissions
        forum.is_cat = is_cat

        w.session.add(forum)
        w.session.commit()

        # handle subscriptions
        for subscription in category.subscriptions:
            logging.info(f'handle forum subscription  {subscription.user_id}')
            wp_subscription_user = handleUser(subscription.user_id)
            wp_subscription = w.ForoSubscribe.q.filter(
                w.ForoSubscribe.userid == wp_subscription_user.ID, w.ForoSubscribe.itemid == forum.forumid, w.ForoSubscribe.type == 'forum').first()
            if wp_subscription == None:
                wp_subscription = w.ForoSubscribe()

            wp_subscription.itemid = forum.forumid
            wp_subscription.userid = wp_subscription_user.ID
            wp_subscription.active = 0
            wp_subscription.confirmkey = ''.join(random.choices(
                string.ascii_lowercase + string.digits, k=32))
            wp_subscription.type = 'forum'

            w.session.add(wp_subscription)

        w.session.commit()

        for progress in category.progresses:
            logging.info(f'handle visits')
            wp_progress_user = handleUser(progress.user_id)
            wp_progress = w.ForoVisit.q.filter(w.ForoVisit.userid == wp_progress_user.ID, w.ForoVisit.forumid ==
                                               progress.category_id, w.ForoVisit.topicid == progress.lastPost.id).first()
            if wp_progress == None:
                wp_progress = w.ForoVisit()

            wp_progress.userid = wp_progress_user.ID
            wp_progress.forumid = progress.category_id
            wp_progress.topicid = progress.lastPost.id
            wp_progress.time = int(progress.lastCategoryReadDate.timestamp())
            wp_progress.name = wp_progress_user.display_name
            w.session.add(wp_progress)

        w.session.commit()

        syncThreads(limit=10000, chunksize=500, query=and_(
            a.ForumThread.language == 'de', a.ForumThread.category_id == category.id))

        pbar.update(1)

    logging.info('starting syncin forums')


def syncThreads(limit=1000, chunksize=100, query=and_(a.ForumThread.language == 'de')):
    threadCount = a.session.query(a.ForumThread.id).filter(query).count()
    maxresults = min(threadCount, limit)
    offset = 0
    chunksize = min(chunksize, limit)
    pbar = tqdm(total=maxresults, desc='Threads', position=2, leave=True)

    def handleForumThreadsThreaded(threadId):
        w.session()
        a.session()
        wthread = handleForumThread(threadId)

        w.session.remove()
        a.session.remove()
        return wthread

    while True:
        chunk = a.session.query(a.ForumThread.id).order_by(desc(
            a.ForumThread.modificationDate)).filter(query).offset(offset).limit(chunksize).all()

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
    try:
        thread = a.ForumThread.q.filter(a.ForumThread.id == threadId).first()

        thread_log.set_description_str(
            f'📕  Thread: {thread.firstPost.title[:40]}...')

        if thread != None:
            topic = w.ForoTopic.q.filter(
                w.ForoTopic.topicid == thread.id).first()
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

            # handle subscriptions
            for subscription in thread.subscriptions:
                logging.info(f'handle subscription {subscription.user_id}')
                wp_subscription_user = handleUser(subscription.user_id)
                wp_subscription = w.ForoSubscribe.q.filter(
                    w.ForoSubscribe.userid == wp_subscription_user.ID, w.ForoSubscribe.itemid == topic.topicid, w.ForoSubscribe.type == 'topic').first()
                if wp_subscription == None:
                    wp_subscription = w.ForoSubscribe()

                active = 0
                if subscription.noFurtherMails == True:
                    active = 1  # not sure but this seems to be correct TODO: verify
                wp_subscription.itemid = topic.topicid
                wp_subscription.userid = wp_subscription_user.ID
                wp_subscription.active = active
                wp_subscription.confirmkey = ''.join(random.choices(
                    string.ascii_lowercase + string.digits, k=32))
                wp_subscription.type = 'topic'

                w.session.add(wp_subscription)

            w.session.commit()

            # handleposts
            syncForumPosts(limit=10000, chunksize=500, query=and_(
                a.ForumPost.language == 'de', a.ForumPost.deleted == 0, a.ForumPost.thread_id == thread.id))
        else:
            return None
    except Exception as e:
        logging.error(e)
        return None


def syncForumPosts(limit=1000, chunksize=100, query=and_(a.ForumPost.language == 'de', a.ForumPost.deleted == 0)):
    postCount = a.session.query(a.ForumPost.id).order_by(
        desc(a.ForumPost.modificationDate)).filter(query).count()
    maxresults = min(postCount, limit)
    offset = 0
    chunksize = min(chunksize, limit)

    pbar = tqdm(total=maxresults, desc='ForumPosts', position=4, leave=True)

    def handleForumPostThreaded(postId):
        w.session()
        a.session()
        wpost = handleForumPost(postId)

        w.session.remove()
        a.session.remove()
        return wpost

    while True:
        chunk = a.session.query(a.ForumPost.id).order_by(desc(
            a.ForumPost.modificationDate)).filter(query).offset(offset).limit(chunksize).all()

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
    try:
        post = a.ForumPost.q.filter(a.ForumPost.id == postId).first()

        post_log.set_description_str(f'🧾  Post: {post.title[:40]}...')
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

            for rating in post.ratings:
                logging.info(f'handle rating {rating}')
                wp_rating_user = handleUser(rating.ratingUser_id)
                wp_foro_like = w.ForoLike.q.filter(
                    w.ForoLike.userid == wp_rating_user.ID, w.ForoLike.postid == wpost.postid, w.ForoLike.post_userid == wpost.userid).first()
                if wp_foro_like == None:
                    wp_foro_like = w.ForoLike()

                wp_foro_like.userid = wp_rating_user.ID
                wp_foro_like.postid = wpost.postid
                wp_foro_like.post_userid = wpost.userid

                w.session.add(wp_foro_like)
            w.session.commit()

            return wpost
        else:
            return None
    except Exception as e:
        logging.error(e)
