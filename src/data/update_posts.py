# skip if prerequisites not not givin
import logging
from slugify import slugify

from concurrent.futures import ThreadPoolExecutor as PoolExecutor

from lib.wp import api, getWpMediaFiles, getWpPosts, getWpCategories, getWpPostTags, getWpUsers
from lib.apit import getApitArticles, getApitAuthors, getApitFeatureImages, extractArticleTags, getApitDevices, getTextForArticleId

from slugify import slugify
import os
import re
import pandas as pd
from tqdm import tqdm
import json


def extractAuthorEmail(author):
    if author.emailAddressNew is not None:
        email = author.emailAddressNew
    else:
        email = author.emailAddress

    email = re.sub(r"_DA_\d*$", "", email)
    return email


def extractCategories(article):
    catString = article.otherTagIds
    if catString is not None:
        categories = catString[1:-1].split('|')
    else:
        categories = []

    categories = [slugify(category, separator="-") for category in categories]
    return categories


def updatePosts():
    logging.info('reading post data ...')
    articles = getApitArticles()
    wp_posts = getWpPosts()
    logging.info('reading author data ...')
    authors = getApitAuthors()
    wp_users = getWpUsers()
    logging.info('reading categories data ...')
    wp_categories = getWpCategories()
    logging.info('reading tag data ...')
    wp_tags = getWpPostTags()
    devices = getApitDevices()
    logging.info('reading featureImage data ...')
    featureImages = getApitFeatureImages()
    wp_mediafiles = getWpMediaFiles()

    # filter all posts that are not in wp
    logging.info('matching posts')
    articles_not_matched = []
    for article in articles:
        if wp_posts.index.contains(f'{article.id}') == False:
            articles_not_matched.append(article)

    logging.info('%d articles to import', len(articles_not_matched))
    # filter all posts where the author is not there

    logging.info('matching authors...')
    # it would be quicker to just look up the authors in both systems
    # by this it could be much faster
    authors_existing = wp_users.index.tolist()
    articles_with_authors = [
        article for article in articles_not_matched if f'{article.createdBy_id}' in authors_existing]

    logging.info('%d articles with authors to import',
                 len(articles_with_authors))
    # filter all posts where categories are missing

    logging.info('matching categories')
    article_with_cats_checked = []
    for article in articles_with_authors:
        catString = article.otherTagIds
        if catString is not None:
            categories = extractCategories(article)
            checkedCats = []
            for category in categories:
                if wp_categories.index.contains(category) == True:
                    checkedCats.append(1)
            if len(categories) == len(checkedCats):
                article_with_cats_checked.append(article)
        else:
            article_with_cats_checked.append(article)

    logging.info('%d articles with categories checked to import',
                 len(article_with_cats_checked))

    # filter all posts where tags are missing

    logging.info('matching tag data')
    article_with_tags_checked = []
    for article in article_with_cats_checked:
        tags = extractArticleTags(article, devices)
        if len(tags) > 0:
            checked_tags = []
            for tag in tags:
                if wp_tags.index.contains(tag) == True:
                    checked_tags.append(1)
            if len(checked_tags) == len(tags):
                article_with_tags_checked.append(article)
        else:
            article_with_tags_checked.append(article)

    logging.info('%d articles with tags checked to import',
                 len(article_with_tags_checked))

    # filter all posts where featureImages are missing

    logging.info('matching media files')
    existing_media = wp_mediafiles.index.tolist()

    articles_with_media = [
        article for article in article_with_tags_checked if f'{article.id}' in existing_media]

    articles_without_media = [article for article in article_with_tags_checked if article.heroImage_id ==
                              None and article.previewImage_id == None and article.previewImageLegacy_id == None]

    logging.info('existing media %d', len(existing_media))
    logging.info('%d articles with media to import',
                 len(articles_with_media))
    logging.info('%d articles without media to import',
                 len(articles_without_media))

    # create posts
    logging.info('about to import posts')

    pbar = tqdm(total=len(articles_with_media))

    def createIt(article):
        text = getTextForArticleId(article.id)
        author = next((author for author in authors if author.id ==
                       article.createdBy_id), None)
        createdById = wp_users.loc[f'{author.id}'].ID

        categoryIds = [
            str(wp_categories.loc[category].term_id) for category in extractCategories(article)]
        tagIds = [str(wp_tags.loc[tag].term_id) for tag in extractArticleTags(
            article, devices)]

        featureImage = next(
            (img for img in featureImages if img.id == article.id), None)

        if featureImage is not None:
            try:
                featureMedia = wp_mediafiles.loc[f'{featureImage.id}']
                featureMediaId = int(featureMedia.ID)
            except:
                featureMedia = None
                featureMediaId = 0
        else:
            featureMedia = None
            featureMediaId = 0

        postPayload = {
            "title": article.title,
            "slug": article.uri_uri[1:-1],
            "content": text,
            "featured_media": featureMediaId,
            "author": int(createdById),
            "status": "publish",
            "categories": ",".join(categoryIds),
            "tags": ",".join(tagIds),  # something is wrong with this
            "date": pd.to_datetime(str(article.publishingDate)),
            "meta": {
                "legacy_article_id": f'{article.id}'
            }
        }

        jsonstr = json.dumps(postPayload, default=str)

        try:

            res = api.post('/posts', data=jsonstr,
                           headers={'content-type': 'application/json'})
            # print(res)
            pbar.update(1)
            return res
            # print('OK')
        except Exception as e:
            # print(jsondata)
            print(e)

    if len(articles_with_media) > 0:
        with PoolExecutor(max_workers=24) as executor:
            for _ in executor.map(createIt, articles_with_media):
                pass
    else:
        logging.info("All articles been up2date. no action required")


def main():
    # articles = getApitArticles()

    # print(articles[0].id)
    # featureImages = getApitFeatureImages()
    # img = next(img for img in featureImages if img.id == articles[0].id)
    # print(img)
    updatePosts()


if __name__ == '__main__':
    log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_fmt)
    main()
