# -*- coding: utf-8 -*-
import os
import click
import pandas as pd
import logging
# import pymysql
from sqlalchemy import create_engine
from tqdm import tqdm
from dotenv import find_dotenv, load_dotenv
from pathlib import Path


engine = create_engine(
    'mysql+pymysql://readonly:kfDjArlf@127.0.0.1:33066/fonpit')

# engine = create_engine(
#     'mysql+pymysql://root:itsch2san@127.0.0.1:3306/fonpit'
# )


def download_query(csvFilePath, query,
                   index_col='id', chunksize=30, limit=3000):

    print('processing %s' % (csvFilePath))

    if os.path.isfile(csvFilePath):
        print('%s already downloaded, remove to refresh.' %
              (csvFilePath))
        return

    count_query = 'SELECT count(*) count FROM (' + query + ') as d'
    maxresults = engine.execute(count_query).fetchone()[0]
    maxresults = min(limit, maxresults)

    offset = 0
    pbar = tqdm(total=maxresults)
    while True:
        curquery = query + (' LIMIT %d, %d' % (offset, chunksize))
        chunk = pd.read_sql(curquery, engine, index_col=[index_col])

        if not os.path.isfile(csvFilePath):
            chunk.to_csv(csvFilePath)
        else:
            chunk.to_csv(csvFilePath, mode='a', header=False)

        pbar.update(len(chunk))

        offset += chunksize
        if (offset+chunksize) > maxresults:
            chunksize = maxresults - offset

        if len(chunk) < chunksize or offset >= maxresults:
            break


def download_articles():
    article_file = './data/raw/Article.csv'
    article_section_file = './data/raw/ArticleSection.csv'
    userfile_file = './data/raw/UserFile.csv'
    device_file = './data/raw/Device.csv'
    author_file = './data/raw/Author.csv'

    articles_query = '''
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

    download_query(article_file, articles_query,
                   index_col='id', chunksize=10000, limit=1000000)

    sections_query = '''
    SELECT * FROM fonpit.ArticleSection s
    '''

    download_query(article_section_file, sections_query,
                   index_col='article_id', chunksize=10000, limit=1000000)

    author_query = '''
     SELECT 
            u.*
        FROM 
            fonpit.Article a,
            fonpit.User u 
        WHERE a.deleted=0
            AND a.published=1
            AND a.publishingDate < CURDATE()
            AND u.id=a.createdBy_id
        ORDER BY a.publishingDate DESC
    '''
    download_query(author_file, author_query,
                   index_col='id', chunksize=10000, limit=1000000)

    userfile_query = '''
    SELECT * FROM fonpit.UserFile u
    '''
    download_query(userfile_file, userfile_query,
                   index_col='id', chunksize=10000, limit=1000000)

    device_query = '''
    SELECT d.* FROM fonpit.Device d
    '''

    download_query(device_file, device_query,
                   index_col='id', chunksize=10000, limit=1000000)


@click.command()
def main():
    download_articles()
    print('done')


if __name__ == '__main__':
    log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_fmt)

    # not used in this stub but often useful for finding various files
    project_dir = Path(__file__).resolve().parents[2]

    # find .env automagically by walking up directories until it's found, then
    # load up the .env entries as environment variables
    load_dotenv(find_dotenv())

    main()
