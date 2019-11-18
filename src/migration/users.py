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


def synctUsers(limit=100, chunksize=10, lastLoggedInDate='1970-01-01 0:00'):
    logging.info('start importing users')

    userCount = a.session.query(a.User.id).filter(
        a.User.lastLoginDate >= lastLoggedInDate).count()
    maxresults = min(userCount, limit)
    offset = 0
    chunksize = min(chunksize, limit)

    pbar = tqdm(total=maxresults, desc='Users')

    def handleUserThreaded(userId):
        w.session()
        a.session()
        user = handleUser(userId)
        w.session.remove()
        a.session.remove()
        return user

    while True:
        chunk = a.session.query(a.User.id).order_by(desc(a.User.lastLoginDate)).filter(a.User.lastLoginDate >= lastLoggedInDate).offset(
            offset).limit(chunksize).all()

        userIds = [id[0] for id in chunk]

        if len(chunk) > 0:
            with PoolExecutor(max_workers=10) as executor:
                for _ in executor.map(handleUserThreaded, userIds):
                    pass
        else:
            logging.info('no users to migrate')

        pbar.update(len(chunk))

        offset += chunksize
        if (offset+chunksize) > maxresults:
            chunksize = maxresults - offset

        if len(chunk) < chunksize or offset >= maxresults:
            break


def handleUser(userId):
    logging.info(f'handle user {userId}')
    try:
        user = a.User.q.filter(a.User.id == userId).first()
        if user == None:
            logging.error(f'user with user.id:{userId} not found')
            return

        if user.staffPageDescriptionJson is not None:
            description = json.loads(
                user.staffPageDescriptionJson)
        else:
            description = json.loads('{"de": ""}')

        if user.emailAddressNew is not None:
            email = user.emailAddressNew
        else:
            email = user.emailAddress

        roles = ['author']

        if user.roleAssignmentsJson == None:
            roles = ["subscriber"]
        else:
            # TODO: use better capability mapping at this point
            roles = ["author"]

        # de-activated user get a cryptic email and empty roles
        if user.deactivationDate != None or re.match(r"_DA_\d*$", email):
            email = re.sub(r"_DA_\d*$", "", email)
            email = f'DA___{email}'
            logging.info(f'usering mail: {email}')
            roles = []

        if len(roles) > 0:
            # [{x: True}   for x in payload['roles']]
            capabilities = {roles[0]: True}
            capabilities = phpserialize.dumps(capabilities)
        else:
            capabilities = ''

        # email = re.sub(r"_DA_\d*$", "", email)
        name = user.communityName.split(' ')
        if len(name) > 1:
            firstName = name[0]
            lastName = name[1]
        else:
            firstName = name[0]
            lastName = ''

        userslug = slugify(email)

        wp_user = w.User.q.join(w.UserMeta).filter(
            w.UserMeta.meta_key == 'legacy_user_id', w.UserMeta.meta_value == f'{user.id}').first()
        if wp_user == None:
            wp_user = w.User(user_login=email, user_pass=user.passwordSHA, user_nicename=user.communityName, user_email=email,
                             user_url=userslug, user_registered=user.creationDate, user_status=0, display_name=user.communityName, user_activation_key='')

        wp_user.addMeta('legacy_user_id', user.id)
        wp_user.addMeta('nickname', email)
        wp_user.addMeta('first_name', firstName)
        wp_user.addMeta('last_name', lastName)
        wp_user.addMeta('locale', user.locale)
        wp_user.addMeta('description', description.get('de'))
        wp_user.addMeta('wp_capabilities', capabilities)

        w.session.add(wp_user)
        w.session.commit()

        if user.image == None:
            logging.info(f'user.image is NONE {user.id}')
            return wp_user

        if user.image.url != None:
            props = {
                "meta": {"legacy_userimage_id": f'{user.image.id}'},
                "author": wp_user.ID
            }

            existingImage = w.UserMeta.q.filter(
                w.UserMeta.meta_key == 'legacy_userimage_id', w.UserMeta.meta_value == f'user.image.id').first()

            logging.info(f'existing image? {existingImage}')
            if existingImage == True:
                logging.info(
                    'userimage already existed, returning without upload')
                return nuser

            mediaId = w.createMediaFromUrl(
                user.image.url, user.image.mimeType, props=props)

            wp_user.addMeta('wp_user_avatar', mediaId)
            w.session.commit()

        return wp_user
    except Exception as e:
        logging.error(e)
        return None
