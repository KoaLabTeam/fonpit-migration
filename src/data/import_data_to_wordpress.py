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


engine = create_engine(
    'mysql+pymysql://readonly:kfDjArlf@127.0.0.1:33066/fonpit')

wp_engine = create_engine(
    'mysql+pymysql://root:root@192.168.95.100:4002/local'
)


class WordpressAPI:

    def __init__(self, base_url=None, consumer_key=None, consumer_secret=None, token=None, token_secret=None):
        self.base_url = base_url
        self.auth = OAuth1(consumer_key, consumer_secret, token, token_secret)

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
        res.raise_for_status()
        return res


api = WordpressAPI(
    base_url="http://androidpit.local/wp-json/wp/v2",
    consumer_key="AtEiJn23g80n",
    consumer_secret="5iXOXtcCzKq8DdWQUzkwuLkPBC7k9InBiL7rMNG4iNgFfemX",
    token="m9yJAnnSmbzTGfLBOtapHf8C",
    token_secret="MFeLoqvveCdtvsXlEgeVKEtqu7Fu6Sx2rpy5Bu8bLPeDp9v2"
)


def getFeatureImage(article):
    featureImage_id = None
    if hasattr(article, 'heroImage_id') or hasattr(article, 'previewImage_id'):
        if article.previewImage_id:
            featureImage_id = article.previewImage_id
        else:
            featureImage_id = article.heroImage_id

    elif hasattr(article, 'previewImageLegacy_id'):
        featureImage_id = article.previewImageLegacy_id

    if featureImage_id is None:
        return None

    try:
        featureImage_query = f'''
        SELECT * FROM fonpit.UserFile s WHERE s.id={featureImage_id}
        '''
        featureImage = pd.read_sql(featureImage_query, engine, index_col=[
            'id']).to_records()[0]
    except Exception as e:
        featureImage = None
        pass

    return featureImage


def getUser(user_id):
    user_query = f'''
    SELECT * FROM fonpit.User u WHERE u.id={user_id}
    '''
    user = pd.read_sql(user_query, engine, index_col=['id']).to_records()[0]
    return user


def createMedia(userFile):
    # print('downloading', userFile.dtype.names)
    mediaSrc = requests.get(userFile.url)

    # print(mediaSrc.content)
    headers = {
        'cache-control': 'no-cache',
        "Content-Disposition": f'attachment; filename="{userFile.fileName}"',
        'content-type': 'image/jpeg'
    }
    # print('headers', headers)
    res = api.post('/media', headers=headers, data=mediaSrc.content)

    return res.json()['id']


def findOrCreateWpUser(apitUser):
    print(apitUser.dtype.names)
    # print(apitUser)
    users = api.get(
        '/users', params={"context": "edit", "search": f'{apitUser.emailAddress}'}).json()
    if len(users) < 1:
        print('processing....', apitUser)
        if apitUser.staffPageDescriptionJson is not None:
            description = json.loads(apitUser.staffPageDescriptionJson)
        else:
            description = json.loads('{"de": ""}')

        payload = {
            "username": slugify(apitUser.username, separator="_"),
            "name": apitUser.communityName,
            "first_name": "",
            "last_name": "",
            "roles": ["author"],
            "email": apitUser.emailAddress,
            "description": description['de'],
            "locale": "en_US",
            "nickname": "",
            "password": "password"
        }
        print('---------------------------------------------')
        print('creating.....', payload)
        res = api.post('/users', data=payload)

        return res.json()['id']

    return users[0]['id']
    # print(users)


def findOrCreateWpCategory(term):
    print('looking for', term)
    category = api.get('/categories', params={"search": term}).json()
    if len(category) < 1:
        # creating
        print('creating category')
        res = api.post('/categories', data={
            'name': term.capitalize()
        }).json()
        return res['id']
    return category[0]['id']


def findOrCreateTag(term):
    print('looking for', term)
    tag = api.get('/tags', params={"search": term}).json()
    if len(tag) < 1:
        # creating
        print('creating tag')
        res = api.post('/tags', data={
            'name': term
        }).json()
        return res['id']
    return tag[0]['id']


def getListOfTags(article):
    tags = []
    if article.relatedDeviceIds is not None:
        tags += article.relatedDeviceIds[1:-1].split('|')

    if article.relatedAppIds is not None:
        tags += article.relatedAppIds[1:-1].split('|')

    if article.relatedAndroidVersions is not None:
        tags += article.relatedAndroidVersions[1:-1].split('|')

    if article.relatedSystemUIs is not None:
        tags += article.relatedSystemUIs[1:-1].split('|')

    if article.relatedOSs is not None:
        tags += article.relatedOSs[1:-1].split('|')

    if article.relatedManufacturerIds is not None:
        tags += article.relatedManufacturerIds[1:-1].split('|')

    print(article.relatedDeviceIds)
    print(article.relatedAppIds)
    print(article.relatedAndroidVersions)
    print(article.relatedSystemUIs)
    print(article.relatedOSs)
    print(article.relatedManufacturerIds)

    print('tags?', tags)
    return tags

    # tags = article.relatedDeviceIds[1:-1].split('|') + article.relatedAppIds[1:-1].split('|') + article.relatedAndroidVersions[1:-1].split(
    #     '|') + article.relatedSystemUIs[1:-1].split('|') + article.relatedOSs[1:-1].split('|') + article.relatedManufacturerIds[1:-1].split('|')
    # print('tags?', tags)


def createCategories():
    articles_query = f'''
    SELECT
        a.id,
        a.otherTagIds
    FROM fonpit.Article a
    WHERE a.deleted=0
        AND a.published=1
        AND a.publishingDate < CURDATE()
    ORDER BY a.publishingDate DESC
    '''

    articleCategories = pd.read_sql(articles_query, engine, index_col=['id'])

    uniqueCategories = []
    for categoriesString in articleCategories['otherTagIds']:
        if categoriesString is not None:
            categories = categoriesString[1:-1].split('|')
            for category in categories:
                if category not in uniqueCategories:
                    uniqueCategories.append(category)

    print(uniqueCategories)

    def createIt(categoryName):
        category = categoryName.capitalize()
        categorySlug = slugify(categoryName, separator="-")
        try:
            print('creating tag', categorySlug)
            return api.post('/categories', data={
                'name': category,
                'slug': categorySlug
            }).json()
        except Exception as e:
            print('error on creating category', e)
            pass

    with PoolExecutor(max_workers=64) as executor:
        for _ in executor.map(createIt, uniqueCategories):
            pass


def extractArticleTags(article, devicesDf):
    tags = []
    deviceIds = []
    if article.relatedDeviceIds is not None:
        devices = article.relatedDeviceIds[1:-1].split('|')
        for device in devices:
            if device not in deviceIds:
                deviceIds.append(device)
                print('lookup ', int(device))
                dev = devicesDf.loc[int(device)]
                if dev['name'] != "@VARIANT":
                    tags.append(dev['name'])

    # if article.relatedAppIds is not None:
    #     tags += article.relatedAppIds[1:-1].split('|')

    # if article.relatedAndroidVersions is not None:
    #     tags += article.relatedAndroidVersions[1:-1].split('|')

    # if article.relatedSystemUIs is not None:
    #     tags += article.relatedSystemUIs[1:-1].split('|')

    # if article.relatedOSs is not None:
    #     tags += article.relatedOSs[1:-1].split('|')

    if article.relatedManufacturerIds is not None:
        tags += article.relatedManufacturerIds[1:-1].split('|')
    return tags


def createTags():
    articles_query = f'''
    SELECT
        a.id,
        a.relatedDeviceIds,
        a.relatedAppIds,
        a.relatedAndroidVersions,
        a.relatedSystemUIs,
        a.relatedOSs,
        a.relatedManufacturerIds
    FROM fonpit.Article a
    WHERE a.deleted=0
        AND a.published=1
        AND a.publishingDate < CURDATE()
    ORDER BY a.publishingDate DESC
    '''

    articles = pd.read_sql(articles_query, engine, index_col=['id'])

    devices_query = f'''
        SELECT d.id, d.name FROM fonpit.Device d
    '''
    devicesDf = pd.read_sql(devices_query, engine, index_col=['id'])

    uniqueTags = []
    deviceIds = []
    for index, article in articles.iterrows():
        tags = extractArticleTags(article, devicesDf)

        for tag in tags:
            if tag not in uniqueTags:
                uniqueTags.append(tag)

    print('uniqueTags', uniqueTags)

    # doing it in parallel

    def createIt(tagName):
        tag = tagName.capitalize()
        tagSlug = slugify(tag, separator="-")
        try:
            print('creating tag', tagSlug)
            return api.post('/tags', data={
                'name': tag,
                'slug': tagSlug
            }).json()
        except Exception as e:
            print('error on creating tag', e)
            pass

    with PoolExecutor(max_workers=64) as executor:
        for _ in executor.map(createIt, uniqueTags):
            pass


def createAuthors():
    articles_query = f'''
        SELECT
            DISTINCT(u.id),
            u.username,
            u.communityName,
            u.staffPageDescriptionJson,
            u.emailAddress,
            u.emailAddressNew
        FROM
            fonpit.Article a,
            fonpit.User u
        WHERE a.deleted=0
            AND a.published=1
            AND a.publishingDate < CURDATE()
            AND u.id=a.createdBy_id
        ORDER BY a.publishingDate DESC
    '''

    authors = pd.read_sql(articles_query, engine,
                          index_col=['id']).to_records()

    def createIt(author):
        if author.staffPageDescriptionJson is not None:
            description = json.loads(author.staffPageDescriptionJson)
        else:
            description = json.loads('{"de": ""}')

        if author.emailAddressNew is not None:
            email = author.emailAddressNew
        else:
            email = author.emailAddress

        email = re.sub(r"_DA_\d*$", "", email)
        # print('handle', email)

        name = author.communityName.split(' ')

        payload = {
            "username": slugify(author.username, separator="_"),
            "name": author.communityName,
            "first_name": name[0],
            "last_name": name[1] if len(name) > 1 else '',
            "roles": ["author"],
            "email": email,
            "description": description.get('de'),
            "locale": "en_US",
            "nickname": "",
            "password": "password"
        }
        try:
            print('creating.....', author.username)
            res = api.post('/users', data=payload)
            return res
        except Exception as e:
            print('------EERRRRRROROROORORORORORORO =====>')
            print('error on creating user', payload)
            print(e)
            print('<======================================')
            pass

    with PoolExecutor(max_workers=64) as executor:
        for _ in executor.map(createIt, authors):
            pass

    # print('created', authors)


def createFeatureImages(offset=0):
    chunksize = 50
    limit = 1000000
    index_col = 'id'

    articles_query = f'''
    SELECT
        a.*
    FROM
        fonpit.Article a
    WHERE
        a.deleted=0
        AND a.published=1
        AND a.publishingDate < CURDATE()
        AND a.language = 'de'
    ORDER BY a.publishingDate DESC
    '''

    count_query = 'SELECT count(*) count FROM (' + articles_query + ') as d'
    maxresults = engine.execute(count_query).fetchone()[0]
    maxresults = min(limit, maxresults)

    pbar = tqdm(total=maxresults-offset)

    def createIt(row):
        featureImage = getFeatureImage(row)
        if featureImage is not None:
            # print('create', featureImage)
            featureImageId = createMedia(featureImage)

    while True:
        curquery = articles_query + (' LIMIT %d, %d' % (offset, chunksize))
        chunk = pd.read_sql(curquery, engine, index_col=[index_col])

        pbar.update(len(chunk))

        records = chunk.to_records()

        with PoolExecutor(max_workers=4) as executor:
            for _ in executor.map(createIt, records):
                pass

        offset += chunksize
        if (offset+chunksize) > maxresults:
            chunksize = maxresults - offset

        if len(chunk) < chunksize or offset >= maxresults:
            break

        # for row in records:
        #     featureImage = getFeatureImage(row)
        #     if featureImage is not None:
        #         featureImageId = createMedia(featureImage)


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
    SELECT * FROM local.wp_users
    '''
    users = pd.read_sql(users_query, wp_engine, index_col=['user_email'])
    return users


def getWpMediaFiles():
    media_query = f'''
    SELECT * FROM local.wp_posts WHERE post_type='attachment';
    '''
    attachments = pd.read_sql(media_query, wp_engine, index_col=['post_title'])
    return attachments


def createArticles(offset=205, chunksize=50, limit=1000):
    index_col = 'id'

    devices_query = f'''
        SELECT d.id, d.name FROM fonpit.Device d
    '''
    devicesDf = pd.read_sql(devices_query, engine, index_col=['id'])

    wp_categories = getWpCategories()
    wp_postTags = getWpPostTags()
    wp_users = getWpUsers()
    wp_mediafiles = getWpMediaFiles()

    articles_query = f'''
    SELECT
        a.*
    FROM
        fonpit.Article a
    WHERE
        a.deleted=0
        AND a.published=1
        AND a.publishingDate < CURDATE()
        AND a.language = 'de'
    ORDER BY a.publishingDate DESC
    '''

    count_query = 'SELECT count(*) count FROM (' + articles_query + ') as d'
    maxresults = engine.execute(count_query).fetchone()[0]
    maxresults = min(limit, maxresults)

    pbar = tqdm(total=maxresults)

    def createIt(data):
        try:
            res = api.post('/posts', data=data)
            print('OK')
        except Exception as e:
            print(jsondata)
            print(e)

    while True:
        curquery = articles_query + (' LIMIT %d, %d' % (offset, chunksize))
        chunk = pd.read_sql(curquery, engine, index_col=[index_col])

        pbar.update(len(chunk))

        records = chunk.to_records()

        to_create = []

        for row in records:
            section_query = f'''
            SELECT * FROM fonpit.ArticleSection s WHERE s.article_id={row.id}
            '''

            sections = pd.read_sql(section_query, engine,
                                   index_col=['article_id'])
            sections = sections.to_records()
            text = '\n'.join([sec.text for sec in sections])

            user_query = f'''
            SELECT * FROM fonpit.User u WHERE u.id={row.createdBy_id}
            '''
            user = pd.read_sql(user_query, engine, index_col=[
                               'id']).to_records()[0]
            if user.emailAddressNew is not None:
                email = user.emailAddressNew
            else:
                email = user.emailAddress

            email = re.sub(r"_DA_\d*$", "", email)

            createdById = wp_users.loc[email].ID

            tags = extractArticleTags(row, devicesDf)
            tagIds = []
            for tag in tags:
                slugname = slugify(tag, separator="-")
                tagId = wp_postTags.loc[slugname].term_id
                tagIds.append(str(tagId))

            categories = []
            categoryIds = []
            if row.otherTagIds is not None:
                categories = row.otherTagIds[1:-1].split('|')
                for cat in categories:
                    slugname = slugify(cat, separator="-")
                    catId = wp_categories.loc[slugname].term_id
                    categoryIds.append(str(catId))

            featureImage = getFeatureImage(row)
            if featureImage is not None:
                try:
                    featureMedia = wp_mediafiles.loc[os.path.splitext(
                        featureImage.fileName)[0]]
                except:
                    featureMedia = None
            else:
                featureMedia = None

            # print('featureImage', featureMedia.ID)

            # return True

            # if featureImage is not None:
            #     featureImageId = createMedia(featureImage)
            # else:
            #     featureImageId = 0
            # print(sections)
            postPayload = {
                "title": row.title,
                "content": text,
                "featured_media": int(featureMedia.ID) if featureMedia is not None else 0,
                "author": int(createdById),
                "status": "publish",
                "categories": ",".join(categoryIds),
                "tags": ",".join(tagIds),  # something is wrong with this
                "date": pd.to_datetime(str(row.publishingDate)),
            }

            jsondata = json.loads(json.dumps(postPayload, default=str))
            to_create.append(jsondata)
            # print(jsondata)

            # try:
            #     res = api.post('/posts', data=jsondata)
            #     print('OK')
            # except Exception as e:
            #     print(jsondata)
            #     print(e)

        with PoolExecutor(max_workers=32) as executor:
            for _ in executor.map(createIt, to_create):
                pass

        offset += chunksize
        if (offset+chunksize) > maxresults:
            chunksize = maxresults - offset

        if len(chunk) < chunksize or offset >= maxresults:
            break


def writeImportCSV(offset=0, chunksize=50, limit=1000, outputfile='./data/processed/wp_import.csv'):
    index_col = 'id'

    devices_query = f'''
        SELECT d.id, d.name FROM fonpit.Device d
    '''
    devicesDf = pd.read_sql(devices_query, engine, index_col=['id'])

    articles_query = f'''
    SELECT
        a.*
    FROM
        fonpit.Article a
    WHERE
        a.deleted=0
        AND a.published=1
        AND a.publishingDate < CURDATE()
        AND a.language = 'de'
    ORDER BY a.publishingDate DESC
    '''

    count_query = 'SELECT count(*) count FROM (' + articles_query + ') as d'
    maxresults = engine.execute(count_query).fetchone()[0]
    maxresults = min(limit, maxresults)

    offset = 0
    pbar = tqdm(total=maxresults)

    print('maxresults', maxresults)

    while True:
        curquery = articles_query + (' LIMIT %d, %d' % (offset, chunksize))
        chunk = pd.read_sql(curquery, engine, index_col=[index_col])

        pbar.update(len(chunk))

        records = chunk.to_records()
        for row in records:
            print('row', row)
            section_query = f'''
                SELECT * FROM fonpit.ArticleSection s WHERE s.article_id={row.id}
                '''

            sections = pd.read_sql(section_query, engine,
                                   index_col=['article_id'])
            sections = sections.to_records()
            text = '\n'.join([sec.text for sec in sections])

            chunk.loc[row.id, 'text'] = text

            user_query = f'''
                SELECT * FROM fonpit.User u WHERE u.id={row.createdBy_id}
                '''
            user = pd.read_sql(user_query, engine, index_col=[
                'id']).to_records()[0]
            if user.emailAddressNew is not None:
                email = user.emailAddressNew
            else:
                email = user.emailAddress

            email = re.sub(r"_DA_\d*$", "", email)
            chunk.loc[row.id, 'authorEmail'] = email

            tags = extractArticleTags(row, devicesDf)
            tags = [slugify(tag, separator="-") for tag in tags]

            chunk.loc[row.id, 'tags'] = ','.join(tags)

            categories = []
            if row.otherTagIds is not None:
                cats = row.otherTagIds[1:-1].split('|')
                for cat in cats:
                    categories.append(slugify(cat, separator="-"))

            chunk.loc[row.id, 'categories'] = ','.join(categories)

            featureImage = getFeatureImage(row)

            chunk.loc[row.id, 'featureImage'] = featureImage.url

        if not os.path.isfile(outputfile):
            chunk.to_csv(outputfile)
        else:
            chunk.to_csv(outputfile, mode='a', header=False)

        offset += chunksize
        if (offset+chunksize) > maxresults:
            chunksize = maxresults - offset

        if len(chunk) < chunksize or offset >= maxresults:
            break


def getArticle(articleId: int):

    # get api ready
    articles_query = f'''
    SELECT * FROM fonpit.Article a WHERE a.id={articleId}
    '''
    article = pd.read_sql(articles_query, engine, index_col=['id'])
    article = article.to_records()[0]

    section_query = f'''
    SELECT * FROM fonpit.ArticleSection s WHERE s.article_id={articleId}
    '''

    sections = pd.read_sql(section_query, engine, index_col=['article_id'])
    sections = sections.to_records()

    tags = getListOfTags(article)
    tagIds = [findOrCreateTag(tag) for tag in tags]

    print(article.dtype.names)
    if article.otherTagIds is not None:
        categories = article.otherTagIds[1:-1].split('|')
        categoryIds = [findOrCreateWpCategory(cat) for cat in categories]
        print(categoryIds)
        print(article.otherTagIds[1:-1].split('|'))
    else:
        categoryIds = []

    featureImage = getFeatureImage(article)

    createdBy = getUser(article.createdBy_id)
    createdById = findOrCreateWpUser(createdBy)
    print('createdByID:', createdById)

    if featureImage is not None:
        featureImageId = createMedia(featureImage)
    else:
        featureImageId = 0
    # print(sections)
    postPayload = {
        "title": article.title,
        "content": sections[0].text,
        "featured_media": featureImageId,
        "author": createdById,
        "status": "publish",
        "categories": categoryIds,
        "date": pd.to_datetime(str(article.publishingDate))
        # "tags": tagIds # something is wrong with this
    }

    print('payload to create post', postPayload)
    res = api.post('/posts', data=postPayload)


def main():
    articleId = 610479
    articleId = 502290
    #

    # getArticle(articleId=articleId)
    # createCategories()
    # createTags()
    # createAuthors()
    createFeatureImages(offset=11050)

    # getWpCategories()
    # x = getWpUsers()

    # print(x.loc['lucia.lopez@androidpit.de'].ID)
    # createArticles(offset=0)
    # writeImportCSV(offset=0, chunksize=1, limit=20)

    # getWpUsers()

    # posts = api.get('/posts')
    # print(posts.text)


if __name__ == '__main__':
    log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_fmt)

    # not used in this stub but often useful for finding various files
    project_dir = Path(__file__).resolve().parents[2]

    # find .env automagically by walking up directories until it's found, then
    # load up the .env entries as environment variables
    load_dotenv(find_dotenv())

    main()
