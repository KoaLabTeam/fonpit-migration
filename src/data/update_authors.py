import logging
from slugify import slugify

from concurrent.futures import ThreadPoolExecutor as PoolExecutor

from lib.wp import api, getWpUsers
from lib.apit import getApitAuthors
import re
import json


def updateAuthors():
    authors = getApitAuthors()
    wp_users = getWpUsers()

    authors_to_create = []
    for author in authors:
        if wp_users.index.contains(f'{author.id}') != True:
            authors_to_create.append(author)

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
            "password": "password",
            "meta": {
                "legacy_user_id": f'{author.id}'
            }
        }
        try:
            logging.info('creating author: %s', email)
            res = api.post('/users', data=json.dumps(payload),
                           headers={'content-type': 'application/json'})
            return res
        except Exception as e:
            logging.error('error on creating author: %s (%s)',
                          email, e)
            pass

    if len(authors_to_create) > 0:
        with PoolExecutor(max_workers=64) as executor:
            for _ in executor.map(createIt, authors_to_create):
                pass
    else:
        logging.info("All authors been up2date. no action required")


def main():
    updateAuthors()


if __name__ == '__main__':
    log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_fmt)
    main()
