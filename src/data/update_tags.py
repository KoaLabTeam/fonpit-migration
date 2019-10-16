import logging
from slugify import slugify

from concurrent.futures import ThreadPoolExecutor as PoolExecutor

from lib.wp import api, getWpPostTags
from lib.apit import getApitTags


def updateTags():
    uniqueTags = getApitTags()
    wp_tags = getWpPostTags()

    wp_tags = wp_tags.to_records()

    tags_to_create = []
    for tag in uniqueTags:
        found = next((x for x in wp_tags if x.slug ==
                      slugify(tag, separator="-")), None)
        if found is None:
            tags_to_create.append(tag)

    def createIt(tagName):
        tag = tagName.capitalize()
        tagSlug = slugify(tag, separator="-")
        try:
            logging.info('creating tag: %s', str(tagName))
            return api.post('/tags', data={
                'name': tag,
                'slug': tagSlug
            }).json()
        except Exception as e:
            logging.error('error on creating tag: %s', e)
            pass

    if len(tags_to_create) > 0:
        with PoolExecutor(max_workers=64) as executor:
            for _ in executor.map(createIt, tags_to_create):
                pass
    else:
        logging.info("All tags been up2date. no action required")


def main():
    updateTags()


if __name__ == '__main__':
    log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_fmt)
    main()
