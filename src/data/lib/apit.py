import pandas as pd
import time
from datetime import datetime
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


def getApitCategories():
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
                # category = slugify(category, separator="-")
                if category not in uniqueCategories:
                    uniqueCategories.append(category)
    return uniqueCategories


def extractArticleTags(article, devicesDf):
    tags = []
    deviceIds = []
    if article.relatedDeviceIds is not None:
        devices = article.relatedDeviceIds[1:-1].split('|')
        for device in devices:
            if device not in deviceIds:
                deviceIds.append(device)
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

    # tags = [slugify(tag, separator="-") for tag in tags]

    return tags


def getDevices():
    devices_query = f'''
        SELECT d.id, d.name FROM fonpit.Device d
    '''
    devicesDf = pd.read_sql(devices_query, engine, index_col=['id'])
    return devicesDf


def getApitTags():
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

    return uniqueTags


def getApitAuthors():
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
    return authors


def getApitFeatureImages(limit=1000000):
    featureImage_query = f'''
  SELECT
    DISTINCT(b.id),
      b.userFile_id,
      b.uri_uri,
      b.publishingDate,
      u.url,
      u.folder_path,
      u.version,
      u.fileName,
      u.size,
      u.md5Hash,
      u.mimeType,
      u.width,
      u.height,
      u.altText,
      u.createdBy_id,
      u.creationDate,
      u.modifiedBy_id,
      u.modificationDate,
      u.copyright,
      u.tags
  FROM
    (
      SELECT a.id, a.heroImage_id as userFile_id, a.uri_uri, a.publishingDate FROM fonpit.Article a WHERE a.heroImage_id IS NOT NULL AND a.previewImage_id IS NULL AND a.deleted=0 AND a.published=1 AND a.language = 'de' AND a.publishingDate < CURDATE()
      UNION
      SELECT a.id, a.previewImage_id as userFile_id, a.uri_uri, a.publishingDate FROM fonpit.Article a WHERE a.previewImage_id IS NOT NULL AND a.deleted=0 AND a.published=1 AND a.language = 'de' AND a.publishingDate < CURDATE()
      UNION
      SELECT a.id, a.previewImageLegacy_id as userFile_id, a.uri_uri, a.publishingDate FROM fonpit.Article a WHERE a.heroImage_id IS NULL AND a.previewImage_id IS NULL AND a.deleted=0 AND a.published=1 AND a.language = 'de' AND a.publishingDate < CURDATE()
    ) as b,
      fonpit.UserFile u
  WHERE
    u.id = b.userFile_id
      AND u.deleted = 0
  ORDER BY b.publishingDate DESC
  LIMIT 0,{limit}
  '''

    featureImages = pd.read_sql(featureImage_query, engine,
                                index_col=['id']).to_records()
    return featureImages


def getArticles(language='de', sinceModificationTimestamp=0, offset=0, limit=1, lastPublishingDate=None):
    if lastPublishingDate == None:
        lastPublishingDate = time.strftime('%Y-%m-%d %H:%M:%S')

    sinceModificationDate = datetime.fromtimestamp(
        sinceModificationTimestamp).strftime('%Y-%m-%d %H:%M:%S')

    articles_query = f'''
    SELECT
        a.*
    FROM
        fonpit.Article a
    WHERE
        a.deleted=0
        AND a.published=1
        AND a.publishingDate < '{lastPublishingDate}'
        AND a.modificationDate > '{sinceModificationDate}'
        AND a.language = '{language}'
    ORDER BY a.publishingDate DESC
    LIMIT {offset}, {limit}
    '''
    logging.info(articles_query)
    articles = pd.read_sql(articles_query, engine,
                           index_col=['id'])  # .to_records()
    return articles


def getArticleById(articleId):

    articles_query = f'''
    SELECT
        a.*
    FROM
        fonpit.Article a
    WHERE
        a.id={articleId}
    '''
    logging.info(articles_query)
    articles = pd.read_sql(articles_query, engine,
                           index_col=['id'])  # .to_records()
    return articles


def getComments(language='de', sinceModificationTimestamp=0, offset=0, limit=1):
    sinceModificationDate = datetime.fromtimestamp(
        sinceModificationTimestamp).strftime('%Y-%m-%d %H:%M:%S')

    comments_query = f'''
        SELECT 
            ac.*
        FROM 
            fonpit.ArticleComment ac, 
            fonpit.Article a 
        WHERE 
            ac.article_id=a.id 
            AND a.language='{language}' 
            AND ac.deleted=0 
            AND ac.modificationDate > '{sinceModificationDate}'
        ORDER BY a.modificationDate DESC
        LIMIT {offset}, {limit}
        '''

    logging.info(comments_query)
    comments = pd.read_sql(comments_query, engine,
                           index_col=['id'])  # .to_records()

    comments = comments.fillna(0)
    comments['parentComment_id'] = comments['parentComment_id'].astype('int')
    # print(comments.info())
    return comments


def getCommentsByArticleId(articleId):
    comments_query = f'''
        SELECT 
            ac.*
        FROM 
            fonpit.ArticleComment ac, 
            fonpit.Article a 
        WHERE 
            ac.article_id=a.id 
            AND ac.deleted=0 
            AND a.id={articleId}
        ORDER BY a.modificationDate DESC
        '''

    logging.info(comments_query)
    comments = pd.read_sql(comments_query, engine,
                           index_col=['id'])  # .to_records()

    comments = comments.fillna(0)
    comments['parentComment_id'] = comments['parentComment_id'].astype('int')
    # print(comments.info())
    return comments


def getApitDevices():
    devices_query = f'''
        SELECT d.id, d.name FROM fonpit.Device d
    '''
    devicesDf = pd.read_sql(devices_query, engine, index_col=['id'])
    return devicesDf


def getTextForArticleId(articleId):
    section_query = f'''
      SELECT * FROM fonpit.ArticleSection s WHERE s.article_id={articleId}
    '''
    sections = pd.read_sql(section_query, engine,
                           index_col=['article_id'])
    sections = sections.to_records()
    text = '\n'.join([sec.text for sec in sections])
    return text


def getUser(userId):
    user_query = f'''
        SELECT 
            u.id,
            u.username,
            u.communityName,
            u.passwordSHA,
            u.staffPageDescriptionJson,
            u.emailAddress,
            u.emailAddressNew,
            u.roleAssignmentsJson,
            u.deactivationDate,
            u.deactivationReason,
            ui.id as profilePictureId,
            ui.url as profilePictureUrl,
            ui.mimeType as profilePictureMimeType
        FROM 
            User u
        LEFT JOIN (SELECT * FROM UserImage WHERE deleted=0 GROUP BY user_id ORDER BY creationDate DESC) as ui ON u.id=ui.user_id
        WHERE u.id={userId} 
    '''
    users = pd.read_sql(user_query, engine,
                        index_col=['id']).to_records()
    if len(users) > 0:
        return users[0]
    else:
        return None


def getFeatureImageByArticleId(articleId):
    featureImageQuery = f'''
    SELECT
        DISTINCT(b.id),
        b.userFile_id,
        b.uri_uri,
        b.publishingDate,
        u.url,
        u.folder_path,
        u.version,
        u.fileName,
        u.size,
        u.md5Hash,
        u.mimeType,
        u.width,
        u.height,
        u.altText,
        u.createdBy_id,
        u.creationDate,
        u.modifiedBy_id,
        u.modificationDate,
        u.copyright,
        u.tags
    FROM
        (
        SELECT a.id, a.heroImage_id as userFile_id, a.uri_uri, a.publishingDate FROM fonpit.Article a WHERE a.heroImage_id IS NOT NULL AND a.previewImage_id IS NULL AND a.id={articleId}
        UNION
        SELECT a.id, a.previewImage_id as userFile_id, a.uri_uri, a.publishingDate FROM fonpit.Article a WHERE a.previewImage_id IS NOT NULL AND a.id={articleId}
        UNION
        SELECT a.id, a.previewImageLegacy_id as userFile_id, a.uri_uri, a.publishingDate FROM fonpit.Article a WHERE a.heroImage_id IS NULL AND a.previewImage_id IS NULL AND a.id={articleId}
        ) as b,
        fonpit.UserFile u
    WHERE
        u.id = b.userFile_id
        AND u.deleted = 0
    ORDER BY b.publishingDate DESC
    '''
    featureImages = pd.read_sql(featureImageQuery, engine,
                                index_col=['id']).to_records()
    if len(featureImages) > 0:
        return featureImages[0]
    else:
        return None
