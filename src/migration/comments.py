from migration.users import handleUser

import logging
import models.apit as a
import models.wordpress as w
import json
import re
import phpserialize

from tqdm import tqdm
from sqlalchemy import desc
from concurrent.futures import ThreadPoolExecutor as PoolExecutor
from slugify import slugify

log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_fmt,
                    filename='migration.log', filemode='w')


def syncMatchingArticleComments():
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


def syncArticleComments(limit=100, chunksize=10, lastModificationDate='1970-01-01 0:00'):
    logging.info('start importing comments')
    commentsCount = a.session.query(a.ArticleComment.id).filter(
        a.ArticleComment.modificationDate >= lastModificationDate, a.ArticleComment.language == 'de', a.ArticleComment.deleted == 0).count()
    maxresults = min(commentsCount, limit)
    offset = 0
    chunksize = min(chunksize, limit)

    pbar = tqdm(total=maxresults)

    def handleArticleCommentThreaded(commentId):
        w.session()
        a.session()
        comment = handleArticleComment(commentId)
        w.session.remove()
        a.session.remove()
        return comment

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


def handleArticleComment(commentId):
    try:
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
    except Exception as e:
        logging.error(e)
        return None
