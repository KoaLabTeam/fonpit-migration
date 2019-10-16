from tqdm import tqdm
import pandas as pd
import os
import re
import bleach
import logging
from dotenv import find_dotenv, load_dotenv
from pathlib import Path
tqdm.pandas()


def cleanText(text):
    # remove new line and digits with regular expression
    # text = BeautifulSoup(text, 'html.parser').get_text()
    # print('text?', text)
    text = re.sub(r'\&ldquo;', '"', text)
    text = re.sub(r'\&rdquo;', '"', text)
    text = re.sub(r'\&quot;', '"', text)
    text = re.sub(r'\&nbsp;', ' ', text)
    text = bleach.clean(text, tags=[], strip=True)
    # print('text?', text)
    text = re.sub(r'\n', '', text)
    text = re.sub(r'\d', '', text)
    # remove patterns matching url format
    url_pattern = r'((http|ftp|https):\/\/)?[\w\-_]+(\.[\w\-_]+)+([\w\-\.,@?^=%&amp;:/~\+#]*[\w\-\@?^=%&amp;/~\+#])?'  # noqa: E501
    text = re.sub(url_pattern, ' ', text)

    # standardize white space
    text = re.sub(r'\s+', ' ', text)
    # drop capitalization
    # text = text.lower()
    # remove white space
    text = text.strip()

    text = text.encode().decode()
    return text


def get_total_rows(filename):
    with open(filename) as f:
        return sum(1 for line in f)


def group_sections():
    outputfile = './data/processed/Article_with_section_clean.csv'
    if os.path.isfile(outputfile):
        print('%s already exists, remove to refresh.' %
              (outputfile))
        return

    article_section_file = './data/raw/ArticleSection.csv'
    article_file = './data/raw/Article.csv'

    sections = pd.read_csv(article_section_file)
    sections = sections[sections['text'] == sections['text']]
    # print('sections', sections)

    # print('sections', sections)
    # sections_grouped = pd.DataFrame(
    #     columns=['article_id', 'text'])

    max_articles = 100000
    total_articles = get_total_rows(article_file)
    total_articles = min(max_articles, total_articles)
    chunksize = 10
    ctotal = int(total_articles/chunksize)
    for chunk in tqdm(pd.read_csv(article_file,
                                  nrows=total_articles, chunksize=chunksize),
                      total=ctotal):

        chunk["text"] = ""
        # print('chunk?', chunk)
        for idx, article in chunk.iterrows():

            secs = sections.loc[sections['article_id'] == article.id]
            secs = secs.groupby(['article_id'])['text'].apply(
                lambda x: cleanText(','.join(x))
            ).reset_index()

            if len(secs) > 0:
                chunk.loc[idx, 'text'] = secs.loc[0].text

        if not os.path.isfile(outputfile):
            chunk.to_csv(outputfile)
        else:
            chunk.to_csv(outputfile, mode='a', header=False)
        # articles.to_csv(outputfile)


def main():
    group_sections()
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
