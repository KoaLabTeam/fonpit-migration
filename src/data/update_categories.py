import logging
from slugify import slugify

from concurrent.futures import ThreadPoolExecutor as PoolExecutor

from lib.wp import api, getWpCategories
from lib.apit import getApitCategories


def updateCategories():
    uniqueCategories = getApitCategories()
    wp_categories = getWpCategories()

    wp_categories = wp_categories.to_records()

    categories_to_create = []
    for cat in uniqueCategories:
        found = next((x for x in wp_categories if x.slug ==
                      slugify(cat, separator="-")), None)
        if found is None:
            categories_to_create.append(cat)

    def createIt(categoryName):
        category = categoryName.capitalize()
        categorySlug = slugify(categoryName, separator="-")
        try:
            logging.info('creating category: %s', category)
            return api.post('/categories', data={
                'name': category,
                'slug': categorySlug
            }).json()
        except Exception as e:
            logging.error('error on creating category: %s', e)
            pass

    if len(categories_to_create) > 0:

        with PoolExecutor(max_workers=64) as executor:
            for _ in executor.map(createIt, categories_to_create):
                pass
    else:
        logging.info("All categories been up2date. no action required")


def main():
    updateCategories()


if __name__ == '__main__':
    log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_fmt)
    main()
