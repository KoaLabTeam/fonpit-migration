import apit
import wp
from slugify import slugify
import re
import json
import logging
from concurrent.futures import ThreadPoolExecutor as PoolExecutor
import pandas as pd
from tqdm import tqdm
import click
import dateparser
from requests.exceptions import HTTPError

log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_fmt,
                    filename='migration.log', filemode='w')
# log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# logging.basicConfig(level=logging.INFO, format=log_fmt)

lastRunTs = 1571213249
lastRunTs = 0


def extractStringList(catString):
    if catString is not None:
        categories = catString[1:-1].split('|')
    else:
        categories = []

    # categories = [slugify(category, separator="-") for category in categories]
    return categories


class SyncRunner:

    def __init__(self, syncSince=0, skipExisting=True, articleId=None):
        self.syncSince = syncSince
        self.devicesDF = apit.getDevices()
        self.skipExisting = skipExisting
        self.specificArticleId = articleId

    def run(self, limit=10, ):
        try:

            # self.handleUsers()
            logging.info(f'start syncing articles since {self.syncSince}')

            if self.specificArticleId != None:
                articles = apit.getArticleById(
                    self.specificArticleId).to_records()
            else:
                articles = apit.getArticles(
                    language='de', sinceModificationTimestamp=self.syncSince, limit=limit).to_records()

            if len(articles) > 0:
                with PoolExecutor(max_workers=1) as executor:
                    for _ in executor.map(self.handleArticle, articles):
                        pass
            else:
                logging.info(
                    "All articles been up2date. no action required")

            # logging.info(f'start syncing comments since {self.syncSince}')
            # comments = apit.getComments(
            #     language='de', sinceModificationTimestamp=self.syncSince, limit=limit).to_records()

            # if len(comments) > 0:
            #     with PoolExecutor(max_workers=1) as executor:
            #         for _ in executor.map(self.handleComment, comments):
            #             pass
            # else:
            #     logging.info(
            #         "No new comments found, seems to be up2date. no action required")

        except Exception as e:
            logging.exception(e)

    def handleUsers(self, limit=10000):
        maxresults = min(apit.getUsersCount(), limit)
        logging.info(f'start syncing {maxresults} users')
        offset = 0
        chunksize = min(500, limit)

        pbar = tqdm(total=maxresults)
        while True:
            chunk = apit.getUsers(offset=offset, limit=chunksize)
            if len(chunk) > 0:
                with PoolExecutor(max_workers=10) as executor:
                    for _ in executor.map(self.handleUser, chunk):
                        pass
            else:
                logging.info('no users to migrate')
            pbar.update(len(chunk))

            offset += chunksize
            if (offset+chunksize) > maxresults:
                chunksize = maxresults - offset

            if len(chunk) < chunksize or offset >= maxresults:
                break
        # users = apit.getUsersId()
        # userIds = [user.id for user in users]
        # if len(users) > 0:
        #     with PoolExecutor(max_workers=24) as executor:
        #         for _ in executor.map(self.handleUser, userIds):
        #             pass
        # else:
        #     logging.info('no users to migrate')

    def handleArticle(self, article):
        logging.info(f'handling article {article.id} - "{article.title}"')

        try:
            existingPost = wp.getWpPostByLegacyArticleId(article.id)
            # skipping existing
            if existingPost != None and self.skipExisting == True:
                logging.info('skipping article since it already exists')
                self.handleArticleComments(existingPost.ID, article.id)
                return

            categoryIds = self.handleCategories(article)
            tagIds = self.handleTags(article)
            author = apit.getUser(article.createdBy_id)
            authorId = self.handleUser(author)
            featureImageId = self.handleFeatureImage(
                article, authorId=authorId)
            text = apit.getTextForArticleId(article.id)

            logging.info('========================================')
            # logging.info(f'existing article? {existingPost}')
            logging.info(f'category ids {categoryIds}')
            logging.info(f'tag ids {tagIds}')
            logging.info(f'author id {authorId}')

            postPayload = {
                "title": article.title,
                "slug": article.uri_uri[1:-1],
                "content": text,
                "featured_media": featureImageId,
                "author": int(authorId),
                "status": "publish",
                "categories": ",".join(categoryIds),
                "tags": ",".join(tagIds),  # something is wrong with this
                "date": pd.to_datetime(str(article.publishingDate)),
                "meta": {
                    "legacy_article_id": f'{article.id}'
                }
            }

            payloadStr = json.dumps(postPayload, default=str)

            if existingPost is None:
                res = wp.api.post('/posts', data=payloadStr,
                                  headers={'content-type': 'application/json'}).json()
            else:
                res = wp.api.put(f'/posts/{existingPost.ID}', data=payloadStr,
                                 headers={'content-type': 'application/json'}).json()

            # create flat comments first
            self.handleArticleComments(res['id'], article.id)

        except Exception as e:
            logging.exception(e)
            pass

    def handleArticleComments(self, postId, articleId):
        logging.info(
            f'handling article comments for api({articleId}) and post({postId})')
        article_comments = apit.getCommentsByArticleId(
            articleId).to_records()

        for comment in article_comments:
            self.handleComment(comment)

        self.handleCommentTree(postId)

    def handleCategories(self, article):
        logging.info(f'handling categories {article.otherTagIds}')
        categories = extractStringList(article.otherTagIds)
        if len(categories) > 0:
            logging.info(f'ensuring categories {categories}')
            wp_categories = []
            for category in categories:
                category_slug = slugify(category, separator="-")
                wp_category = wp.getTermIdByTaxonomyAndSlugname(
                    taxonomy='category', slug=category_slug)
                if wp_category != None:
                    wp_categories.append(str(wp_category.term_id))
                else:
                    new_wp_cat = wp.api.post('/categories', data={
                        'name': category.capitalize(),
                        'slug': category_slug
                    }).json()
                    wp_categories.append(str(new_wp_cat['id']))
                    # now we need to create the category
            return wp_categories
        else:
            return []

    def handleTags(self, article):
        tags = apit.extractArticleTags(article, self.devicesDF)
        logging.info(f'handle tags? {tags}')
        if len(tags) > 0:
            logging.debug(f'ensuring tags {tags}')
            wp_tags = []
            for tag in tags:
                tag_slug = slugify(tag, separator='-')
                wp_tag = wp.getTermIdByTaxonomyAndSlugname(
                    taxonomy='post_tag', slug=tag_slug)
                if wp_tag != None:
                    wp_tags.append(str(wp_tag.term_id))
                else:
                    new_wp_tag = wp.api.post('/tags', data={
                        'name': tag,
                        'slug': tag_slug
                    }).json()
                    wp_tags.append(str(new_wp_tag['id']))
            return wp_tags
        else:
            return []

    def handleFeatureImage(self, article, authorId):
        feature_image = apit.getFeatureImageByArticleId(article.id)
        wp_media = wp.getMediaFromLegacy(
            id=feature_image.id)

        if wp_media is None:
            logging.info('creating media')
            feature_image_id = wp.createMediaFromUrl(feature_image.url, mimeType=feature_image.mimeType, props={
                "author": str(authorId),
                "meta": {
                    "legacy_userfile_id": f'{feature_image.id}'
                }
            })
            return feature_image_id
        else:
            return wp_media.ID

    def handleComment(self, comment):
        logging.info(f'handling comment {comment}')

        try:
            existingComment = wp.getCommentFromLegacy(id=comment.id)
            self.handleCommentLikes(self, comment.id)
            if existingComment != None:
                logging.info(
                    f'skipping comment {comment.id} since its already there')
                return existingComment.comment_ID

            user = apit.getUser(comment.createdBy_id)
            userId = self.handleUser(user)
            wp_post = wp.getWpPostByLegacyArticleId(comment.article_id)

            if wp_post is None:
                logging.info(
                    f'skipping {comment.article_id} since it does not exist within wp')
                return

            if comment.parentComment_id != None:
                parentId = comment.parentComment_id
            else:
                parentId = ''

            payload = {
                "post": wp_post.ID,
                "content": comment.comment,
                "author": userId,
                "date": pd.to_datetime(str(comment.creationDate)),
                "status": "approved",
                "meta": {
                    "legacy_comment_id": comment.id,
                    "legacy_comment_parentid": parentId,
                }
            }

            new_comment = wp.api.post('/comments', data=json.dumps(payload, default=str),
                                      headers={'content-type': 'application/json'}).json()

            return new_comment['id']
        except Exception as e:
            logging.exception(e)
            pass

    def handleCommentLikes(self, commentId):
        likes = apit.getCommentLikes(commentId)
        if likes != None:
            print(likes)

    def handleUser(self, apit_user):
        try:
            logging.info(f'handleUser: looking for apit user: {apit_user.id}')
            wp_user = wp.getUserByLegacyUserId(apit_user.id)
            if wp_user == None:
                logging.info(f'user not found {apit_user.id}')
                # apit_user = apit.getUser(apitUserId)
                apit_user_pic = apit.getUserPicture(apit_user.id)

                if apit_user_pic != None:
                    profile_picture_id = self.handleProfilePicture(
                        apit_user_pic)
                else:
                    profile_picture_id = 0

                if apit_user.staffPageDescriptionJson is not None:
                    description = json.loads(
                        apit_user.staffPageDescriptionJson)
                else:
                    description = json.loads('{"de": ""}')

                if apit_user.emailAddressNew is not None:
                    email = apit_user.emailAddressNew
                else:
                    email = apit_user.emailAddress

                roles = []

                if apit_user.roleAssignmentsJson == None:
                    roles = ["subscriber"]
                else:
                    # print(apit_user.roleAssignmentsJson)
                    roles = ["author"]  # TODO: refine later

                # de-activated user get a cryptic email and empty roles
                if apit_user.deactivationDate != None or re.match(r"_DA_\d*$", email):
                    email = re.sub(r"_DA_\d*$", "", email)
                    email = f'DA___{email}'
                    logging.info(f'usering mail: {email}')
                    roles = []

                # email = re.sub(r"_DA_\d*$", "", email)
                name = apit_user.communityName.split(' ')

                payload = {
                    "username": email,
                    "name": apit_user.communityName,
                    "first_name": name[0],
                    "last_name": name[1] if len(name) > 1 else '',
                    "roles": ["subscriber"],
                    "email": email,
                    "description": description.get('de'),
                    "locale": "en_US",
                    "nickname": "",
                    "password": apit_user.passwordSHA,
                    "meta": {
                        "legacy_user_id": f'{apit_user.id}',
                        "wp_user_avatar": f'{profile_picture_id}'
                    }
                }

                new_user_id = wp.createWpUserViaSQL(payload)

                # new_user = wp.api.post('/users', data=json.dumps(payload),
                #                        headers={'content-type': 'application/json'}).json()
                logging.info(f'user created: {email}')
                return new_user_id
                # return new_user['id']
            else:
                return wp_user.ID
        except HTTPError as e:
            wp_user = wp.getUserByLegacyUserId(apit_user.id)
            if wp_user != None:
                logging.error('user already existed, race condition')
                return wp_user.ID
            else:
                logging.error(e)
            pass

    def handleProfilePicture(self, apit_user_pic):
        profile_picture = wp.getMediaFromLegacy(
            id=apit_user_pic.profilePictureId, key='legacy_userimage_id')

        if profile_picture is None:
            logging.info('handleProfilePicture: creating profile picture')
            profile_picture_id = wp.createMediaFromUrl(
                apit_user_pic.profilePictureUrl, mimeType=apit_user_pic.profilePictureMimeType, props={"meta": {"legacy_userimage_id": f'{apit_user_pic.profilePictureId}'}})
            return profile_picture_id
        else:
            return profile_picture.ID

    def handleCommentTree(self, postId):
        logging.info(
            f'handleCommentTree: handle comment tree for article: {postId}')
        comments_with_parents = wp.getCommentsWithLegacyParentByPostId(postId)
        if comments_with_parents != None:
            for comment in comments_with_parents:
                if comment.comment_parent != 0:
                    logging.info(
                        f'handleCommentTree: skipping {comment.comment_ID} parent already sat')
                    continue

                parent_comment = wp.getCommentFromLegacy(
                    id=comment.legacy_comment_parentid, key='legacy_comment_id')
                if parent_comment != None:
                    payload = {
                        "parent": parent_comment.comment_ID
                    }
                    res = wp.api.put(f'/comments/{comment.comment_ID}', data=json.dumps(payload, default=str),
                                     headers={'content-type': 'application/json'}).json()

                else:
                    logging.error(
                        f'handleCommentTree: parent comment for {comment.legacy_comment_parentid} not found')
        else:
            logging.info(
                'handleCommentTree: no comments left with unhandled legacy parents')


@click.command()
@click.option('-s', '--since', default='1.January 1970', help='sync changes since.')
@click.option('--limit', default=1, help='Number of articles to sync.')
@click.option('--skip', default=True, help='Skip existing entities?')
@click.option('--articleid', default=None, help='syncing specific articleId')
def main(since, limit, skip, articleid):
    parsedSince = dateparser.parse(since)
    since = parsedSince.timestamp()

    logging.info(f'since {parsedSince}')
    logging.info(f'limit {limit}')

    runner = SyncRunner(syncSince=since, skipExisting=skip,
                        articleId=articleid)
    runner.run(limit=limit)


if __name__ == '__main__':
    main()
