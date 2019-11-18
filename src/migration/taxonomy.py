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


def extractStringList(catString):
    if catString is not None:
        stringList = catString[1:-1].split('|')
    else:
        stringList = []

    return stringList

###


def handleCategories(article):
    categories = extractStringList(article.otherTagIds)
    try:
        if len(categories) > 0:
            logging.info(f'ensuring categories {categories}')
            wp_categories = []
            for category in categories:
                category_slug = slugify(category, separator='-')
                wp_category = w.Term.q.filter(
                    w.Term.taxonomy == 'category', w.Term.slug == category_slug).first()
                if wp_category != None:
                    wp_categories.append(wp_category)
                else:
                    new_wp_cat = w.Term(
                        taxonomy='category', name=category.capitalize(), slug=category_slug)
                    w.session.add(new_wp_cat)
                    w.session.commit()
                    wp_categories.append(new_wp_cat)
            return wp_categories
        return []
    except Exception as e:
        logging.error(e)
        return []


def handleTags(article):
    tags = []
    cachedDeviceIds = []

    try:
        if article.relatedDeviceIds is not None:
            deviceIds = article.relatedDeviceIds[1:-1].split('|')
            for deviceId in deviceIds:
                if deviceId not in cachedDeviceIds:
                    cachedDeviceIds.append(deviceId)
                    device = a.Device.q.filter(a.Device.id == deviceId).first()
                    if device != None and device.name != '@VARIANT':
                        tags.append(device.name)

        if article.relatedManufacturerIds is not None:
            tags += article.relatedManufacturerIds[1:-1].split('|')

        if len(tags) > 0:
            wp_tags = []
            for tag in tags:
                tag_slug = slugify(tag, separator='-')
                wp_tag = w.Term.q.filter(
                    w.Term.taxonomy == 'post_tag', w.Term.slug == tag_slug).first()
                if wp_tag != None:
                    if wp_tag not in wp_tags:
                        wp_tags.append(wp_tag)
                else:
                    new_wp_tag = w.Term(taxonomy='post_tag',
                                        slug=tag_slug, name=tag)
                    w.session.add(new_wp_tag)
                    w.session.commit()
                    if new_wp_tag not in wp_tags:
                        wp_tags.append(new_wp_tag)

            return wp_tags
        return []
    except Exception as e:
        logging.error(e)
        return []
