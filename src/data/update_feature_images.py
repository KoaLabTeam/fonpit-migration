import logging
from slugify import slugify

from concurrent.futures import ThreadPoolExecutor as PoolExecutor

from lib.wp import api, getWpMediaFiles
from lib.apit import getApitFeatureImages
import requests
from tqdm import tqdm

import os
import json


def updateFeatureImages():
    logging.info('reading data ...')
    featureImages = getApitFeatureImages(limit=1000)
    # featureImages = [featureImages[0]]
    wp_mediafiles = getWpMediaFiles()

    media_to_create = []

    logging.info('matching ...')
    for img in featureImages:
        print('checking', img.id)
        if wp_mediafiles.index.contains(f'{img.id}') == False:
            media_to_create.append(img)

    logging.info('about to import %d files', len(media_to_create))
    # media_to_create = media_to_create[:1]
    maxfiles = len(media_to_create)

    def createIt(userFile):
        try:
            # logging.info('creating mediafile: %s', userFile.fileName)
            mediaSrc = requests.get(userFile.url)

            # print(mediaSrc.content)
            headers = {
                'cache-control': 'no-cache',
                "Content-Disposition": f'attachment; filename="{userFile.fileName}"',
                'content-type': 'image/jpeg'
            }
            # print('headers', headers)
            res = api.post('/media', headers=headers, data=mediaSrc.content)
            mediaResponse = json.loads(res.text)
            mediaId = mediaResponse['id']

            mediaPayload = {
                "meta": {
                    "legacy_userfile_id": f'{userFile.id}'
                }
            }

            updateres = api.put(f'/media/{mediaId}', data=json.dumps(mediaPayload),
                                headers={'content-type': 'application/json'})

            # print(updateres)
            # print(mediaId)
            pbar.update(1)  # one file created
            return mediaId

        except Exception as e:
            logging.error('error on creating media: %s', e)
            pass

    if len(media_to_create) > 0:
        pbar = tqdm(total=maxfiles)
        with PoolExecutor(max_workers=8) as executor:
            for _ in executor.map(createIt, media_to_create):
                pass
    else:
        logging.info("All featureImages been up2date. no action required")


def main():
    updateFeatureImages()


if __name__ == '__main__':
    log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_fmt)
    main()
