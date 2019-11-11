from datetime import datetime
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy import Table, Column, Integer, String, BigInteger, DateTime, Sequence, ForeignKey, Text, UniqueConstraint, join, Enum, SmallInteger, Boolean
from sqlalchemy.dialects.mysql import BIT
from sqlalchemy.orm import scoped_session, sessionmaker, relationship, backref, column_property


engine = create_engine(
    'mysql+pymysql://readonly:kfDjArlf@127.0.0.1:33066/fonpit', pool_size=20, max_overflow=0, echo=False)

session = scoped_session(sessionmaker(autocommit=False,
                                      autoflush=True,
                                      bind=engine))

Model = declarative_base(name='Model')
Model.q = session.query_property()


class User(Model):
    __tablename__ = 'User'
    id = Column(Integer, primary_key=True)
    version = Column(Integer)
    status = Column(Enum('NO_USER', 'REGISTERING',
                         'REGISTERING_ACTIVE', 'OK', 'DEACTIVATED'))

    emailAddress = Column(String(length=255))
    passwordSHA = Column(String(length=255))
    passwordGenerated = Column(String(length=255))
    accountActivationCode = Column(String(length=255))
    accountActivationLink = Column(String(length=255))
    emailAddressNew = Column(String(length=255))
    emailValidationCode = Column(String(length=255))
    emailValidationLink = Column(String(length=255))
    fbUserId = Column(BigInteger)
    googleUserId = Column(String(length=255))
    publicName = Column(String(length=255))
    username = Column(String(length=255))
    communityName = Column(String(length=255))
    birthdayDate = Column(Integer)
    birthdayMonth = Column(Integer)
    birthdayYear = Column(Integer)
    birthdayMailSentYear = Column(Integer)

    city = Column(String(length=255))
    country_id = Column(String(length=2))
    locale = Column(String(length=255))

    roleAssignmentsJson = Column(Text)
    staffPageDescriptionJson = Column(Text)
    deactivationDate = Column(DateTime)
    lastLoginDate = Column(DateTime)

    nextPitTransferAgreed = Column(BIT)
    nextPitTransferAgrementDate = Column(DateTime)
    nextPitTransferDisagrementDate = Column(DateTime)
    creationDate = Column(DateTime)

    level = Column(Integer)
    pointsInLevel = Column(Integer)
    pointsTotalRecalculated = Column(Integer)

    partner_id = Column(String(length=255))

    userImage_id = Column(Integer)  # FOREIGNKEY HERE

    image = relationship('UserImage', back_populates='user', uselist=False,
                         primaryjoin="and_(User.id==UserImage.user_id, UserImage.deleted==0)")
    files = relationship('UserFile', back_populates='user',
                         foreign_keys='UserFile.createdBy_id')

    def __repr__(self):
        return "<ApitUser(id='%s', emailAddress='%s', publicName='%s')>" % (self.id, self.emailAddress, self.publicName)


class UserEvent(Model):
    __tablename__ = 'UserEvent'
    id = Column(Integer, primary_key=True)
    version = Column(Integer)
    user_id = Column(Integer, ForeignKey('User.id'))
    event = Column(Enum('NEWSLETTER_REGISTRATION', 'DAILY_LOGIN', 'CREATE_POST', 'CREATE_APP_TALK', 'CREATE_COMMENT', 'RECEIVE_LIKE',
                        'RECEIVE_BEST_ANSWER', 'CUSTOM_MODERATOR', 'LEVEL_UP', 'LEVEL_DOWN', 'LEVEL_UP_MODERATOR', 'LEVEL_DOWN_MODERATOR'))
    forumPost_id = Column(Integer)  # TODO: relation
    articleComment_id = Column(Integer, ForeignKey('ArticleComment.id'))
    description = Column(String(length=255))
    awardedBy_id = Column(Integer, ForeignKey('User.id'))
    creationDate = Column(DateTime)
    revocation_id = Column(Integer)
    revokedEvent_id = Column(Integer)
    revokedBy_id = Column(Integer, ForeignKey('User.id'))

    comment = relationship(
        'ArticleComment',  back_populates='likes')

    user = relationship('User', foreign_keys=[user_id])
    awardedBy = relationship('User', foreign_keys=[awardedBy_id])


class UserImage(Model):
    __tablename__ = 'UserImage'
    id = Column(Integer, primary_key=True)
    version = Column(Integer)
    user_id = Column(Integer, ForeignKey('User.id'))
    url = Column(String(length=255))
    mimeType = Column(String(length=255))
    creationDate = Column(DateTime)
    deleted = Column(BIT)
    deletionDate = Column(DateTime)
    user = relationship('User', back_populates='image')

    def __repr__(self):
        return "<ApitUserImage(id='%s', url='%s', mimeType='%s')>" % (self.id, self.url, self.mimeType)


class UserFile(Model):
    __tablename__ = 'UserFile'
    id = Column(Integer, primary_key=True)
    version = Column(Integer)
    url = Column(String(length=255))
    folder_path = Column(String(length=255))
    fileName = Column(String(length=255))
    mimeType = Column(String(length=255))
    altText = Column(String(length=255))
    uploadSource = Column(
        Enum('FINDER', 'ARTICLE_UPLOAD_DIALOG', 'FORUM_UPLOAD_DIALOG'))
    createdBy_id = Column(Integer, ForeignKey('User.id'))
    creationDate = Column(DateTime)
    modifiedBy_id = Column(Integer, ForeignKey('User.id'))
    modificationDate = Column(DateTime)
    deleted = Column(BIT)
    deletedBy_id = Column(Integer, ForeignKey('User.id'))
    deletionDate = Column(DateTime)
    copyright = Column(String(length=255))
    tags = Column(String(length=255))
    ignoreInMigration = Column(BIT)

    user = relationship('User', back_populates='files',
                        foreign_keys=[createdBy_id])

    def __repr__(self):
        return "<ApitUserFile(id='%s', url='%s', mimeType='%s')>" % (self.id, self.url, self.mimeType)


class Article(Model):
    __tablename__ = 'Article'
    id = Column(Integer, primary_key=True)
    DTYPE = Column(String(length=31))
    version = Column(Integer)
    format = Column(Enum('NEWS', 'BEST_PRODUCTS', 'HOW_TO', 'OPINION', 'INTERVIEW', 'POLL',
                         'LIVE_STREAM', 'DEALS', 'HANDS_ON', 'FULL_REVIEW', 'LONG_TERM_REVIEW', 'COMPARISON'))
    language = Column(String(length=2))
    uri_language = Column(String(length=2))
    uri_uri = Column(String(length=255))
    title = Column(String(length=255))
    advertorial = Column(BIT)
    metaDescription = Column(Text)
    metaKeywords = Column(Text)
    metaNewsKeywords = Column(Text)
    categoryIds = Column(Text)
    relatedManufacturerIds = Column(Text)
    mainDevice_id = Column(Integer)
    relatedDeviceIds = Column(Text)
    relatedAppIds = Column(Text)
    relatedAndroidVersions = Column(Text)
    relatedSystemUIs = Column(Text)
    relatedOSs = Column(Text)
    relatedOperatorBrands = Column(Text)
    otherTags = Column(Text)
    otherTagIds = Column(Text)
    relatedForumThreadIds = Column(String(length=255))
    relatedArticleIds = Column(String(length=255))
    referencedGalleryIds = Column(Text)
    commentsAllowed = Column(Boolean)
    author_id = Column(Integer, ForeignKey('User.id'))
    published = Column(Boolean)
    publishingDate = Column(DateTime)
    republishingDate = Column(DateTime)
    storyLabel = Column(String(length=255))
    sourceName = Column(String(length=255))
    sourceURL = Column(String(length=255))
    source2Name = Column(String(length=255))
    source2URL = Column(String(length=255))
    source3Name = Column(String(length=255))
    source3URL = Column(String(length=255))

    heroImage_id = Column(Integer, ForeignKey(
        'UserFile.id'))  # foregin keys here/
    heroImageAuto = Column(Boolean)
    previewImage_id = Column(Integer, ForeignKey('UserFile.id'))
    previewImageLegacy_id = Column(Integer, ForeignKey('UserFile.id'))
    pros = Column(Text)
    cons = Column(Text)

    createdBy_id = Column(Integer, ForeignKey('User.id'))
    creationDate = Column(DateTime)

    modifiedBy_id = Column(Integer, ForeignKey('User.id'))
    modificationDate = Column(DateTime)

    deleted = Column(Boolean)
    deletionDate = Column(DateTime)
    deletionReason = Column(String(length=255))

    author = relationship('User', foreign_keys=[author_id])
    createdBy = relationship('User', foreign_keys=[createdBy_id])
    modifiedBy = relationship('User', foreign_keys=[modifiedBy_id])

    heroImage = relationship('UserFile', foreign_keys=[heroImage_id])
    previewImage = relationship('UserFile', foreign_keys=[previewImage_id])
    previewImageLegacy = relationship(
        'UserFile', foreign_keys=[previewImageLegacy_id])

    sections = relationship('ArticleSection', back_populates='article')
    comments = relationship('ArticleComment', back_populates='article')

    def __repr__(self):
        return "<ApitArticle(id='%s', title='%s', publishingDate='%s')>" % (self.id, self.title, self.publishingDate)


class ArticleSection(Model):
    __tablename__ = 'ArticleSection'
    article_id = Column(Integer, ForeignKey('Article.id'), primary_key=True)
    sectionKey = Column(String(length=255), primary_key=True)
    version = Column(Integer, primary_key=True)
    title = Column(String(length=255), primary_key=True)
    text = Column(Text)
    textBackup = Column(Text)
    rating = Column(Integer)

    article = relationship('Article', back_populates='sections')

    def __repr__(self):
        return "<ApitArticleSection(article_id='%s', title='%s', text='%s')>" % (self.article_id, self.title, self.text)


class ArticleComment(Model):
    __tablename__ = 'ArticleComment'
    id = Column(Integer, primary_key=True)
    version = Column(Integer)
    article_id = Column(Integer, ForeignKey('Article.id'))
    # TODO: fix the parent relation ship
    parentComment_id = Column(Integer, ForeignKey('ArticleComment.id'))
    nestedLevel = Column(Integer)
    language = Column(String(length=2))
    comment = Column(Text)
    createdBy_id = Column(Integer, ForeignKey('User.id'))
    creationDate = Column(DateTime)
    creatorIp = Column(String(length=255))
    modifiedBy_id = Column(Integer, ForeignKey('User.id'))
    modificationDate = Column(DateTime)
    deleted = Column(Boolean)
    deletedBy_id = Column(Integer, ForeignKey('User.id'))
    deletionDate = Column(DateTime)

    createdBy = relationship('User', foreign_keys=[createdBy_id])
    modifiedBy = relationship('User', foreign_keys=[modifiedBy_id])
    deletedBy = relationship('User', foreign_keys=[deletedBy_id])
    article = relationship('Article', foreign_keys=[article_id])

    parent = relationship('ArticleComment', remote_side=[id])
    likes = relationship(
        'UserEvent', primaryjoin="and_(ArticleComment.id==UserEvent.articleComment_id, UserEvent.event == 'RECEIVE_LIKE')")

    def __repr__(self):
        return "<ApitArticleComment(article_id='%s', creationDate='%s', parentComment_id='%s')>\n" % (self.article_id, self.creationDate, self.parentComment_id)


class Device(Model):
    __tablename__ = 'Device'
    id = Column(Integer, primary_key=True)
    version = Column(Integer)
    manufacturer_id = Column(String(length=255))
    deviceType = Column(Enum('PHONE', 'PHABLET', 'TABLET', 'TV', 'CAMERA', 'GAME_CONSOLE', 'WATCH', 'SMART_HOME',
                             'FITNESS_TRACKER', 'WEARABLE', 'SPEAKER', 'HEADPHONE', 'E_READER', 'NOTEBOOK', 'VR_HEADSET', 'OTHER'))
    releaseDate = Column(DateTime)
    bestseller = Column(Boolean)
    thirdPartyPixel = Column(Text)
    name = Column(String(length=255))
    modelId = Column(String(length=255))
    alsoKnownAs = Column(String(length=255))
    creationDate = Column(DateTime)
    createdBy_id = Column(Integer, ForeignKey('User.id'))
    modifiedBy_id = Column(Integer, ForeignKey('User.id'))
    modificationDate = Column(DateTime)
    deleted = Column(Boolean)
    deletedBy_id = Column(Integer, ForeignKey('User.id'))
    deletionDate = Column(DateTime)
    metaKeywords = Column(String(length=255))
    metaDescription = Column(String(length=255))

    createdBy = relationship('User', foreign_keys=[createdBy_id])
    modifiedBy = relationship('User', foreign_keys=[modifiedBy_id])
    deletedBy = relationship('User', foreign_keys=[deletedBy_id])
    images = relationship('DeviceImage', back_populates='device')

    def __repr__(self):
        return "<ApitDevice(id='%s', name='%s', releaseDate='%s')>" % (self.id, self.name, self.releaseDate)


class DeviceImage(Model):
    __tablename__ = 'DeviceImage'
    id = Column(Integer, primary_key=True)
    version = Column(Integer)
    device_id = Column(Integer, ForeignKey('Device.id'))
    orderInSlideshow = Column(Integer)
    url = Column(String(length=255))
    mimeType = Column(String(length=255))

    device = relationship('Device', back_populates='images')

    def __repr__(self):
        return "<DeviceImage(id='%s', mimeType='%s', url='%s')>" % (self.id, self.mimeType, self.url)


class ForumCategory(Model):
    __tablename__ = 'ForumCategory'
    id = Column(Integer, primary_key=True)
    version = Column(Integer)
    language = Column(String(length=2))
    pos = Column(Integer)
    transcription_language = Column(String(length=2))
    transcription_transcription = Column(String(length=255))
    parentCategory_id = Column(Integer, ForeignKey('ForumCategory.id'))
    name = Column(String(length=255))
    nameForNavigation = Column(String(length=255))
    description = Column(Text)
    creationDate = Column(DateTime)
    modificationDate = Column(DateTime)
    deletionDate = Column(DateTime)
    deleted = Column(Boolean)

    createdBy_id = Column(Integer, ForeignKey('User.id'))
    modifiedBy_id = Column(Integer, ForeignKey('User.id'))
    deletedBy_id = Column(Integer, ForeignKey('User.id'))
    image_id = Column(Integer, ForeignKey('ForumCategoryImage.id'))

    createdBy = relationship('User', foreign_keys=[createdBy_id])
    modifiedBy = relationship('User', foreign_keys=[modifiedBy_id])
    deletedBy = relationship('User', foreign_keys=[deletedBy_id])
    transcription = relationship(
        'ForumCategoryTranscription', back_populates='forumCategory')

    image = relationship('ForumCategoryImage', foreign_keys=[image_id])

    posts = relationship('ForumPost', back_populates='category')
    threads = relationship('ForumThread', back_populates='category')
    children = relationship('ForumCategory', foreign_keys=[
        parentCategory_id], back_populates='parent')
    parent = relationship('ForumCategory', remote_side=[
        id], back_populates='children', uselist=False)

    def __repr__(self):
        return "<ForumCategory(id='%s', name='%s', nameForNavigation='%s')>" % (self.id, self.name, self.nameForNavigation)


class ForumCategoryImage(Model):
    __tablename__ = 'ForumCategoryImage'
    id = Column(Integer, primary_key=True)
    version = Column(Integer)
    url = Column(String(length=255))
    mimeType = Column(String(length=255))
    createdBy_id = Column(Integer, ForeignKey('User.id'))
    creationDate = Column(DateTime)

    createdBy = relationship('User', foreign_keys=[createdBy_id])

    def __repr__(self):
        return "<ForumCategoryImage(id='%s', mimeType='%s', url='%s')>" % (self.id, self.mimeType, self.url)


class ForumCategoryTranscription(Model):
    __tablename__ = 'ForumCategoryTranscription'
    language = Column(String(length=2), primary_key=True)
    transcription = Column(String(length=255), primary_key=True)
    version = Column(Integer)
    forumCategory_id = Column(Integer, ForeignKey('ForumCategory.id'))
    creationDate = Column(DateTime)
    createdBy_id = Column(Integer, ForeignKey('User.id'))

    createdBy = relationship('User', foreign_keys=[createdBy_id])
    forumCategory = relationship('ForumCategory', foreign_keys=[
                                 forumCategory_id], back_populates='transcription')


class ForumCategoryUserSubscription(Model):
    __tablename__ = 'ForumCategoryUserSubscription'
    user_id = Column(Integer, ForeignKey('User.id'), primary_key=True)
    category_id = Column(Integer, ForeignKey(
        'ForumCategory.id'), primary_key=True)
    version = Column(Integer)

    # TODO: create m:n relationship here!


class ForumPost(Model):
    __tablename__ = 'ForumPost'
    id = Column(Integer, primary_key=True)
    version = Column(Integer)
    thread_id = Column(Integer, ForeignKey('ForumThread.id'))
    category_id = Column(Integer, ForeignKey('ForumCategory.id'))
    language = Column(String(length=2))
    author_id = Column(Integer, ForeignKey('User.id'))
    title = Column(String(length=255))
    content = Column(Text)
    contentAsHtml = Column(Text)
    tags = Column(Text)
    parentPost_id = Column(Integer, ForeignKey('ForumPost.id'))

    createdBy_id = Column(Integer, ForeignKey('User.id'))
    modifiedBy_id = Column(Integer, ForeignKey('User.id'))
    deletedBy_id = Column(Integer, ForeignKey('User.id'))

    creationDate = Column(DateTime)
    modificationDate = Column(DateTime)
    deletionDate = Column(DateTime)

    deleted = Column(Boolean)
    reportedAsSpam = Column(Boolean)
    reported = Column(Boolean)
    reportedBy_id = Column(Integer, ForeignKey('User.id'))
    reportedDate = Column(DateTime)
    reportedReason = Column(String(length=255))
    reportedComment = Column(Text)

    category = relationship('ForumCategory', back_populates='posts')
    author = relationship('User', foreign_keys=[author_id])
    createdBy = relationship('User', foreign_keys=[createdBy_id])
    modifiedBy = relationship('User', foreign_keys=[modifiedBy_id])
    deletedBy = relationship('User', foreign_keys=[deletedBy_id])
    reportedBy = relationship('User', foreign_keys=[reportedBy_id])

    thread = relationship(
        'ForumThread', back_populates='posts', foreign_keys=[thread_id])
    parent = relationship('ForumPost', foreign_keys=[
                          parentPost_id], back_populates='children')
    children = relationship('ForumPost', remote_side=[
                            id], back_populates='parent')


class ForumPostRating(Model):
    __tablename__ = 'ForumPostRating'
    ratedObject_id = Column(Integer, ForeignKey(
        'ForumPost.id'), primary_key=True)
    ratingUser_id = Column(Integer, ForeignKey('User.id'), primary_key=True)
    version = Column(Integer)
    userEventReceivedLike_id = Column(Integer, ForeignKey('UserEvent.id'))
    type = Column(Enum('UP', 'DOWN'))
    timestamp = Column(DateTime)


class ForumPostRatingNEW(Model):
    __tablename__ = 'ForumPostRatingNEW'
    ratedObject_id = Column(Integer, ForeignKey(
        'ForumPost.id'), primary_key=True)
    ratingUser_id = Column(Integer, ForeignKey('User.id'), primary_key=True)
    version = Column(Integer)
    ratedUser_id = Column(Integer, ForeignKey('User.id'))
    type = Column(Enum('UP', 'DOWN'))
    timestamp = Column(DateTime)


class ForumThread(Model):
    __tablename__ = 'ForumThread'
    id = Column(Integer, primary_key=True)
    version = Column(Integer)
    type = Column(Enum('QUESTION', 'DISCUSSION'))
    typeConfirmed = Column(Boolean)
    typeConfirmedBy_id = Column(Integer, ForeignKey('User.id'))
    typeConfirmedDate = Column(DateTime)
    category_id = Column(Integer, ForeignKey('ForumCategory.id'))
    language = Column(String(length=2))
    transcription = Column(String(length=255))
    threadType = Column(
        Enum('FORUM', 'FIRST_AID', 'APP_QUESTION', 'APP_QUESTION_PARENT'))
    firstAidPostedBy_id = Column(Integer, ForeignKey('User.id'))
    firstPost_id = Column(Integer, ForeignKey('ForumPost.id'))
    lastPost_id = Column(Integer, ForeignKey('ForumPost.id'))
    createdBy_id = Column(Integer, ForeignKey('User.id'))
    creationDate = Column(DateTime)
    modificationDate = Column(DateTime)
    stickiness = Column(Integer)
    answered = Column(Boolean)
    closed = Column(Boolean)
    relatedThreads = Column(String(length=255))
    relatedThreadsLastUpdate = Column(DateTime)

    posts = relationship(
        'ForumPost', back_populates='thread', primaryjoin="and_(ForumThread.id==ForumPost.thread_id)")
    firstPost = relationship('ForumPost', foreign_keys=[firstPost_id])
    lastPost = relationship('ForumPost', foreign_keys=[lastPost_id])
    category = relationship('ForumCategory', foreign_keys=[
                            category_id], back_populates='threads')


class ForumThreadUserSubscription(Model):
    __tablename__ = 'ForumThreadUserSubscription'
    user_id = Column(Integer, ForeignKey('User.id'), primary_key=True)
    thread_id = Column(Integer, ForeignKey('ForumThread.id'), primary_key=True)
    version = Column(Integer)
    noFurtherMails = Column(Boolean)


class ForumUserCategoryProgress(Model):
    __tablename__ = 'ForumUserCategoryProgress'
    user_id = Column(Integer, ForeignKey('User.id'), primary_key=True)
    category_id = Column(Integer, ForeignKey(
        'ForumCategory.id'), primary_key=True)
    version = Column(Integer)
    lastPostRead_id = Column(Integer, ForeignKey('ForumPost.id'))
    lastCategoryReadDate = Column(DateTime)


class ForumUserGlobalProgress(Model):
    __tablename__ = 'ForumUserGlobalProgress'
    user_id = Column(Integer, ForeignKey('User.id'), primary_key=True)
    language = Column(String(length=2), primary_key=True)
    version = Column(Integer)
    lastPostRead_id = Column(Integer, ForeignKey('ForumPost.id'))
    lastPostReadDate = Column(DateTime)


class ForumUserProgress(Model):
    __tablename__ = 'ForumUserProgress'
    user_id = Column(Integer, ForeignKey('User.id'), primary_key=True)
    thread_id = Column(Integer, ForeignKey('ForumThread.id'), primary_key=True)
    version = Column(Integer)
    firstPostReadDate = Column(DateTime)
    lastPostRead_id = Column(Integer, ForeignKey('ForumPost.id'))
    lastPostReadLanguage = Column(String(length=2))
    lastPostReadDate = Column(DateTime)
