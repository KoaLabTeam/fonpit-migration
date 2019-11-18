from migration.taxonomy import handleTags, handleCategories
from migration.users import handleUser

import logging
import models.apit as a
import models.wordpress as w
import json
import re
import phpserialize

from bs4 import BeautifulSoup
from urllib.parse import urlparse
from tqdm import tqdm
from sqlalchemy import desc
from concurrent.futures import ThreadPoolExecutor as PoolExecutor
from slugify import slugify

log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_fmt,
                    filename='migration.log', filemode='w')


def syncArticles(limit=100, chunksize=10, lastModificationDate='1970-01-01 0:00'):
    logging.info('start importing articles')
    articleCount = a.session.query(a.Article.id).filter(
        a.Article.modificationDate >= lastModificationDate, a.Article.language == 'de', a.Article.published == True, a.Article.deleted == 0).count()

    maxresults = min(articleCount, limit)
    offset = 0
    chunksize = min(chunksize, limit)

    pbar = tqdm(total=maxresults)

    def handleArticleThreaded(articleId):
        w.session()
        a.session()
        article = handleArticle(articleId)
        w.session.remove()
        a.session.remove()
        return article

    while True:
        chunk = a.session.query(a.Article.id).order_by(desc(a.Article.modificationDate)).filter(
            a.Article.modificationDate >= lastModificationDate, a.Article.language == 'de', a.Article.published == True, a.Article.deleted == 0).offset(offset).limit(chunksize).all()

        articleIds = [id[0] for id in chunk]

        if len(chunk) > 0:
            with PoolExecutor(max_workers=10) as executor:
                for _ in executor.map(handleArticleThreaded, articleIds):
                    pass
        else:
            logging.info('no articles to migrate')

        pbar.update(len(chunk))

        offset += chunksize
        if (offset+chunksize) > maxresults:
            chunksize = maxresults - offset

        if len(chunk) < chunksize or offset >= maxresults:
            break

    # auto import images that where linked
    triggerAutoImageImports()


def handleArticle(articleId):
    try:
        logging.info(f'looking for article: {articleId}')
        article = a.Article.q.filter(a.Article.id == articleId).first()
        if article == None:
            logging.error(f'article with id:{articleId} not found')
            return

        logging.info(f'handling article:{article.title}')

        text = ' '.join([section.text for section in article.sections])

        categories = handleCategories(article)
        tags = handleTags(article)
        wp_author = handleUser(article.author.id)
        wp_post = w.Post.q.join(w.PostMeta).filter(
            w.PostMeta.meta_key == 'legacy_article_id', w.PostMeta.meta_value == f'{article.id}').first()

        if wp_post == None:
            wp_post = w.Post()
            wp_post.addMeta('legacy_article_id', article.id)

        wp_post.post_type = 'post'
        wp_post.post_title = article.title
        wp_post.post_name = slugify(article.title, separator='-')
        wp_post.post_slug = article.uri_uri.replace('/', '')
        wp_post.post_content = text
        wp_post.post_date = article.publishingDate
        wp_post.post_modified = article.modificationDate

        wp_post.terms = categories + tags

        wp_post.author = wp_author
        wp_post.post_status = 'publish'

        previewImage = image = article.previewImageLegacy or article.heroImage or article.previewImage
        if previewImage != None:

            featureMedia = w.Post.q.join(w.PostMeta).filter(w.Post.post_type == 'attachment',
                                                            w.PostMeta.meta_key == 'legacy_userfile_id', w.PostMeta.meta_value == f'{previewImage.id}').first()
            imageCreator = handleUser(previewImage.user.id)
            if featureMedia == None:
                props = {
                    "meta": {"legacy_userfile_id": f'{previewImage.id}'},
                    "author": imageCreator.ID
                }
                featureMediaId = w.createMediaFromUrl(
                    previewImage.url, previewImage.mimeType, props=props)
            else:
                featureMediaId = featureMedia.ID
            wp_post.addMeta('_thumbnail_id', f'{featureMediaId}')

        w.session.add(wp_post)
        w.session.commit()
        return wp_post
    except Exception as e:
        logging.error(e)
        return None


def triggerAutoImageImports(limit=100, chunksize=10):

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
                for _ in executor.map(triggerAutoImageImport, postIds):
                    pbar.update(1)
                    pass
        else:
            logging.info('no articles to trigger')

        offset += chunksize
        if (offset+chunksize) > maxresults:
            chunksize = maxresults - offset

        if len(chunk) < chunksize or offset >= maxresults:
            break


def triggerAutoImageImport(postId):
    try:
        logging.info(f'triggering id: {postId}')
        result = w.api.put(f'/posts/{postId}', data=json.dumps({}),
                           headers={'content-type': 'application/json'})
    except Exception as e:
        logging.error(e)


def fixInternalLinks(limit=100000, chunksize=100):
    articleCount = w.session.query(w.Post.ID).filter(
        w.Post.post_type == 'post').count()
    maxresults = min(articleCount, limit)
    offset = 0
    chunksize = min(chunksize, limit)

    pbar = tqdm(total=maxresults, desc='fixing internal links')

    # FIXME: shared state is stupid?!? so goin linear here
    while True:
        chunk = w.Post.q.limit(
            chunksize).offset(offset).all()

        if len(chunk) > 0:
            for post in chunk:
                post.post_content = fixInternalLinksByText(post.post_content)
                w.session.add(post)

            w.session.commit()
        else:
            logging.info('no articles to fix')

        pbar.update(1)

        offset += chunksize
        if (offset+chunksize) > maxresults:
            chunksize = maxresults - offset

        if len(chunk) < chunksize or offset >= maxresults:
            break


# TODO: make it respect the permalink settings
def fixInternalLinksByText(text):
    try:
        soup = BeautifulSoup(text)
        # TODO: improve re for multidomain migration
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
                        logging.error(
                            f'no article found with path: {parsed.path}')
                        continue
                    else:
                        wp_post = handleArticle(apit_article.id)

                logging.info(
                    f'replacing links with links to internal:{wp_post}')
                link['href'] = f'https://androidpit.local/{post_slug}'

        return str(soup)
    except Exception as e:
        logging.error(e)
        return text
