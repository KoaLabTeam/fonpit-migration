import logging
import lib.androidpit.models as a
import lib.wordpress.models as w

from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor as PoolExecutor
import json
import re
from slugify import slugify
import phpserialize
from sqlalchemy import desc
from bs4 import BeautifulSoup
from urllib.parse import urlparse

log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_fmt,
                    filename='migration.log', filemode='w')
# log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# logging.basicConfig(level=logging.INFO, format=log_fmt)

# utlity


def extractStringList(catString):
    if catString is not None:
        stringList = catString[1:-1].split('|')
    else:
        stringList = []

    return stringList

###


def importMatchingArticleComments():
    wp_postmetas = w.PostMeta.q.filter(
        w.PostMeta.meta_key == 'legacy_article_id').all()
    commentIds = []
    for postmeta in wp_postmetas:
        comments = a.ArticleComment.q.filter(
            a.ArticleComment.article_id == postmeta.meta_value).all()
        commentIds += [comment.id for comment in comments]

    maxresults = len(commentIds)
    pbar = tqdm(total=maxresults)

    if len(commentIds) > 0:
        with PoolExecutor(max_workers=10) as executor:
            for _ in executor.map(handleArticleCommentThreaded, commentIds):
                pbar.update(1)
                pass
    else:
        logging.info('no comments to import')

    fixCommentsCounter()
    logging.info('import of matching comments done.')


def triggerAutoImports(limit=100, chunksize=10):

    articleCount = w.session.query(w.Post.ID).filter(
        w.Post.post_type == 'post').count()
    maxresults = min(articleCount, limit)
    offset = 0
    chunksize = min(chunksize, limit)

    pbar = tqdm(total=maxresults)

    while True:
        chunk = w.session.query(w.Post.ID).filter(w.Post.post_type == 'post').limit(
            chunksize).offset(offset).all()
        postIds = [id[0] for id in chunk]
        if len(chunk) > 0:
            with PoolExecutor(max_workers=10) as executor:
                for _ in executor.map(triggerAutoImport, postIds):
                    pbar.update(1)
                    pass
        else:
            logging.info('no articles to trigger')

        offset += chunksize
        if (offset+chunksize) > maxresults:
            chunksize = maxresults - offset

        if len(chunk) < chunksize or offset >= maxresults:
            break


def triggerAutoImport(postId):
    logging.info(f'triggering id: {postId}')
    result = w.api.put(f'/posts/{postId}', data=json.dumps({}),
                       headers={'content-type': 'application/json'})


def fixInternalLinks(text):
    soup = BeautifulSoup(text)
    for link in soup.findAll('a', attrs={'href': re.compile("^http[s]://.*androidpit.de.*")}):
        href = link.attrs.get('href')
        if href != None:
            parsed = urlparse(href)
            post_slug = slugify(parsed.path, separator="-")
            wp_post = w.Post.q.filter(
                w.Post.post_name == post_slug).first()
            if wp_post == None:
                apit_article = a.Article.q.filter(
                    a.Article.uri_uri == parsed.path).first()
                if apit_article == None:
                    logging.error(f'no article found with path: {parsed.path}')
                    continue
                else:
                    wp_post = handleArticle(apit_article.id)

            logging.info(f'replacing links with links to internal:{wp_post}')
            link['href'] = f'https://androidpit.local/{post_slug}'

    return str(soup)


def importArticleComments(limit=100, chunksize=10, lastModificationDate='1970-01-01 0:00'):
    logging.info('start importing comments')
    commentsCount = a.session.query(a.ArticleComment.id).filter(
        a.ArticleComment.modificationDate >= lastModificationDate, a.ArticleComment.language == 'de', a.ArticleComment.deleted == 0).count()
    maxresults = min(commentsCount, limit)
    offset = 0
    chunksize = min(chunksize, limit)

    pbar = tqdm(total=maxresults)

    while True:
        chunk = a.session.query(a.ArticleComment.id).order_by(desc(a.ArticleComment.modificationDate)).filter(a.ArticleComment.modificationDate >=
                                                                                                              lastModificationDate, a.ArticleComment.language == 'de', a.ArticleComment.deleted == 0).offset(offset).limit(chunksize).all()
        commentIds = [id[0] for id in chunk]

        if len(chunk) > 0:
            with PoolExecutor(max_workers=10) as executor:
                for _ in executor.map(handleArticleCommentThreaded, commentIds):
                    pass
        else:
            logging.info('no comments to import')

        pbar.update(len(chunk))

        offset += chunksize
        if (offset+chunksize) > maxresults:
            chunksize = maxresults - offset

        if len(chunk) < chunksize or offset >= maxresults:
            break

    fixCommentsCounter()


def fixCommentsCounter():
    posts = w.Post.q.all()
    for post in posts:
        numComments = len(post.comments)
        post.comment_count = numComments
        w.session.commit()


def handleArticleCommentThreaded(commentId):
    w.session()
    a.session()
    comment = handleArticleComment(commentId)
    w.session.remove()
    a.session.remove()
    return comment


def handleArticleComment(commentId):
    comment = a.ArticleComment.q.filter(
        a.ArticleComment.id == commentId).first()

    if comment == None:
        logging.error(f'comment with id: {commentId} not found')
        return

    wp_user = handleUser(comment.createdBy.id)
    wp_post = w.Post.q.join(w.PostMeta).filter(
        w.PostMeta.meta_key == 'legacy_article_id', w.PostMeta.meta_value == f'{comment.article.id}').first()

    if wp_post is None:
        logging.error(
            f'skipping comment, since article: {comment.article.id} not present in wordpress')
        return

    parent = None
    if comment.parent:
        parent = handleArticleComment(comment.parent.id)

    wp_comment = w.Comment.q.join(w.CommentMeta).filter(
        w.CommentMeta.meta_key == 'legacy_comment_id', w.CommentMeta.meta_value == f'{comment.id}').first()

    if wp_comment == None:
        wp_comment = w.Comment()
        wp_comment.user = wp_user
        wp_comment.post = wp_post

    wp_comment.comment_content = comment.comment
    wp_comment.comment_date = comment.modificationDate
    wp_comment.comment_approved = 1
    wp_comment.comment_author_email = wp_user.user_email
    wp_comment.comment_author = wp_user.user_nicename

    wp_comment.addMeta('legacy_comment_id', comment.id)

    if parent != None:
        wp_comment.parent = parent

    w.session.add(wp_comment)
    w.session.commit()

    for like in comment.likes:
        awardingUser = handleUser(like.awardedBy.id)
        status = 'like'
        if like.revokedEvent_id != None:
            status = 'unlike'
        wp_comment.addLike(awardingUser.ID, status, like.creationDate)

    w.session.add(wp_comment)
    w.session.commit()

    numLikes = len(
        [x for x in wp_comment.likes if wp_comment.likes.get(x).status == 'like'])

    wp_comment.addMeta('_commentliked', numLikes)

    w.session.add(wp_comment)
    w.session.commit()

    return wp_comment


def syncForums():
    apitCategories = a.ForumCategory.q.filter(
        a.ForumCategory.deleted == 0, a.ForumCategory.language == 'de').limit(1000).all()
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
        forum.status = 1
        forum.order = 0  # category.pos
        forum.last_topicid = 0
        forum.last_postid = 0
        forum.last_userid = 0
        forum.last_post_date = 0
        forum.permissions = permissions
        forum.is_cat = is_cat

        w.session.add(forum)
        w.session.commit()
        pbar.update(1)

    logging.info('starting syncin forums')


def syncThreads():
    threads = a.ForumThread.q.filter(
        a.ForumThread.language == 'de').limit(1000).all()
    maxresults = len(threads)
    pbar = tqdm(total=maxresults)
    for thread in threads:
        topic = w.ForoTopic.q.filter(w.ForoTopic.topicid == thread.id).first()
        wp_user = handleUser(thread.createdBy_id)

        if topic == None:
            topic = w.ForoTopic()

        topic.topicid = thread.id
        topic.forumid = thread.category_id
        topic.user = wp_user
        topic.created = thread.creationDate
        topic.modified = thread.modificationDate
        topic.title = thread.firstPost.title
        topic.slug = thread.transcription

        w.session.add(topic)
        w.session.commit()

        pbar.update(1)


def syncForumPosts(limit=1000, chunksize=100):
    postCount = a.session.query(a.ForumPost.id).order_by(desc(a.ForumPost.modificationDate)).filter(
        a.ForumPost.language == 'de', a.ForumPost.deleted == 0).count()
    maxresults = min(postCount, limit)
    offset = 0
    chunksize = min(chunksize, limit)

    pbar = tqdm(total=maxresults)

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


def handleForumPostThreaded(postId):
    w.session()
    a.session()
    wpost = handleForumPost(postId)

    w.session.remove()
    a.session.remove()
    return wpost


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
