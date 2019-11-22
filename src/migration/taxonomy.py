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
from time import time

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


class TagDir:
    IFA_ID = 'ifa'
    HIHONOR_ID = "hihonor"
    HUAWEI_EVENT_ID = "huawei-event"
    MOBILITY_ID = "mobility"
    FIVEG_ID = "5g"
    AI_ID = "ai"
    SMART_HOME_ID = "smart-home"
    WEARABLES_ID = "wearables"
    VIRTUAL_REALITY_ID = "virtual-reality"
    GAMES_ID = "games"
    HARDWARE_ID = "hardware"
    APPS_ID = "apps"
    TIPS_AND_TRICKS_ID = "tips-and-tricks"
    VIDEO_ID = "video"
    COMMUNITY_ID = "community"
    MWC_ID = "mwc"
    WWDC_ID = "wwdc"
    CES_ID = "ces"
    EGX_ID = "egx"
    E3_ID = "e3"
    DISRUPT_ID = "disrupt"

    IAA_ID = "iaa"
    PARIS_MOTOR_SHOW_ID = "paris-motor-show"

    GOOGLE_IO_ID = "google-io"
    APPLE_EVENT_ID = "apple-event"
    GOOGLE_PIXEL_3_EVENT_ID = "google-pixel-3-event"
    HUAWEI_MATE_20_EVENT_ID = "huawei-mate-20-event"
    SDC18_EVENT_ID = "samsung-developer-conference"
    SAMSUNG_UNPACKED_ID = "samsung-unpacked"

    AUGMENTED_REALITY_ID = "augmented-reality"
    ANDROID_FOR_BEGINNERS_ID = "android-for-beginners"
    OPINION_ID = "opinion"
    WIKIPIT_ID = "wikipit"
    POLL_ID = "poll"
    APPS_OF_THE_WEEK_ID = "apps-of-the-week"
    GADGET_OF_THE_WEEK_ID = "gadget-of-the-week"
    INTERVIEW_ID = "interview"
    REVIEW_ID = "review"
    INSIDE_ANDROIDPIT_ID = "inside-androidpit"
    DRONES_ID = "drones"
    BLACK_FRIDAY_ID = "black-friday"
    THROWBACK_THURSDAY_ID = "throwback-thursday"
    WINNERS_AND_LOSERS_ID = "winners-and-losers"

    directory = {}

    def __init__(self):
        self.add(self.COMMUNITY_ID, "androidpit",
                 "Community", "en", "de", "it")
        self.add(self.COMMUNITY_ID, "androidpit", "Comunidad", "es")
        self.add(self.COMMUNITY_ID, "androidpit", "Communauté", "fr")
        self.add(self.COMMUNITY_ID, "androidpit", "Comunidade", "pt")

        # Conferences / congresses / events
        self.add(self.IFA_ID, "ifa", "IFA")
        self.add(self.MWC_ID, "mwc", "MWC")
        self.add(self.WWDC_ID, "wwdc", "WWDC")
        self.add(self.CES_ID, "ces", "CES")
        self.add(self.EGX_ID, "egx", "EGX")
        self.add(self.E3_ID, "e3", "E3")
        self.add(self.DISRUPT_ID, "disrupt", "Disrupt")

        # IAA
        self.add(self.
                 IAA_ID,
                 "iaa-internationale-automobil-ausstellung",
                 "IAA Internationale Automobil-Ausstellung",
                 "de")
        self.add(self.
                 IAA_ID,
                 "salon-de-l-automobile-de-francfort",
                 "Salon de l'automobile de Francfort",
                 "fr")
        self.add(self.
                 IAA_ID,
                 "salone-dell-automobile-di-francoforte",
                 "Salone dell'automobile di Francoforte",
                 "it")
        self.add(self.
                 IAA_ID,
                 "salon-del-automovil-de-francfort",
                 "Salón del Automóvil de Fráncfort",
                 "es")
        self.add(self.
                 IAA_ID,
                 "international-motor-show-germany",
                 "International Motor Show Germany",
                 "en")

        # Paris Motor Show
        self.add(self.PARIS_MOTOR_SHOW_ID, "pariser-autosalon",
                 "Pariser Autosalon", "de")
        self.add(self.PARIS_MOTOR_SHOW_ID,
                 "paris-motor-show", "Paris Motor Show", "en")
        self.add(self.PARIS_MOTOR_SHOW_ID, "mondial-paris-motor-show",
                 "Mondial Paris Motor Show", "fr")
        self.add(self.
                 PARIS_MOTOR_SHOW_ID,
                 "salone-dell-automobile-di-parigi",
                 "Salone dell'automobile di Parigi",
                 "it")
        self.add(self.
                 PARIS_MOTOR_SHOW_ID,
                 "salon-del-automovil-de-paris",
                 "Salón del Automóvil de París",
                 "es")

        self.add(self.GOOGLE_IO_ID, "google-io", "Google IO")
        self.add(self.APPLE_EVENT_ID, "apple-event", "Apple Event")
        self.add(self.GOOGLE_PIXEL_3_EVENT_ID,
                 "google-pixel-3-event", "Google Pixel 3 Event")
        self.add(self.HUAWEI_MATE_20_EVENT_ID,
                 "huawei-mate-20-event", "Huawei Mate 20 Event")
        self.add(self.SDC18_EVENT_ID, "samsung-developer-conference",
                 "Samsung Developer Conference")
        self.add(self.SAMSUNG_UNPACKED_ID,
                 "samsung-unpacked", "Samsung Unpacked")
        self.add(self.HIHONOR_ID, "hihonor", "HiHonor")

        # Huawei Event
        self.add(self.HUAWEI_EVENT_ID, "huawei-event",
                 "Huawei Event", "de", "en", "pt", "es")
        self.add(self.HUAWEI_EVENT_ID, "evento-huawei", "Evento Huawei", "it")
        self.add(self.HUAWEI_EVENT_ID, "evenement-huawei",
                 "Événement Huawei", "fr")

        # Other events
        self.add(self.BLACK_FRIDAY_ID, "black-friday",
                 "Black Friday", "en", "de", "pt")
        self.addWithHeading(self.THROWBACK_THURSDAY_ID,
                            "throwback-thursday", "#TBT", "Throwback Thursday")

        # Mobility
        self.add(self.MOBILITY_ID, "mobility", "Mobility", "en", "it")
        self.add(self.MOBILITY_ID, "mobilitaet", "Mobilität", "de")
        self.add(self.MOBILITY_ID, "mobilite", "Mobilité", "fr")
        self.add(self.MOBILITY_ID, "movilidad", "Movilidad", "es")
        self.add(self.MOBILITY_ID, "mobilidade", "Mobilidade", "pt")

        # 5G
        self.add(self.FIVEG_ID, "5g", "5G")

        # AI
        self.add(self.AI_ID, "ai", "AI", "en", "de", "it")
        self.add(self.AI_ID, "ia", "IA", "fr", "es")

        # Smart Home
        self.add(self.SMART_HOME_ID, "smart-home",
                 "Smart Home", "de", "en", "es", "pt", "it")
        self.add(self.SMART_HOME_ID, "maison-connectee",
                 "Maison connectée", "fr")

        # Wearables
        self.add(self.WEARABLES_ID, "wearables",
                 "Wearables", "en", "de", "es", "pt")
        self.add(self.WEARABLES_ID, "wearable", "Wearable", "fr")
        self.add(self.WEARABLES_ID, "indossabili", "Indossabili", "it")

        # Virtual reality
        self.add(self.VIRTUAL_REALITY_ID, "virtual-reality",
                 "Virtual Reality", "en", "de")
        self.add(self.VIRTUAL_REALITY_ID, "realidad-virtual",
                 "Realidad Virtual", "es")
        self.add(self.VIRTUAL_REALITY_ID, "realite-virtuelle",
                 "Réalité virtuelle", "fr")
        self.add(self.VIRTUAL_REALITY_ID, "realidade-virtual",
                 "Realidade Virtual", "pt")
        self.add(self.VIRTUAL_REALITY_ID,
                 "realta-virtuale", "Realtà virtuale", "it")

        # Augmented reality
        self.add(self.AUGMENTED_REALITY_ID, "augmented-reality",
                 "Augmented Reality", "en", "de")
        self.add(self.AUGMENTED_REALITY_ID,
                 "realite-augmentee", "Réalité augmentée", "fr")
        self.add(self.AUGMENTED_REALITY_ID,
                 "realta-aumentata", "Realtà aumentata", "it")
        self.add(self.AUGMENTED_REALITY_ID, "realidad-aumentada",
                 "Realidad aumentada", "es")
        self.add(self.AUGMENTED_REALITY_ID, "realidade-aumentada",
                 "Realidade Aumentada", "pt")

        # Games
        self.add(self.GAMES_ID, "games", "Games", "de", "en")
        self.add(self.GAMES_ID, "jeux", "Jeux", "fr")
        self.add(self.GAMES_ID, "jogos", "Jogos", "pt")
        self.add(self.GAMES_ID, "juegos", "Juegos", "es")
        self.add(self.GAMES_ID, "giochi", "Giochi", "it")

        # Android for beginners
        self.add(self.ANDROID_FOR_BEGINNERS_ID,
                 "android-fuer-anfaenger", "Android für Anfänger", "de")
        self.add(self.ANDROID_FOR_BEGINNERS_ID,
                 "android-for-beginners", "Android for Beginners", "en")
        self.add(self.
                 ANDROID_FOR_BEGINNERS_ID,
                 "android-per-principianti",
                 "Android per Principianti",
                 "it")
        self.add(self.
                 ANDROID_FOR_BEGINNERS_ID,
                 "android-para-principiantes",
                 "Android para Principiantes",
                 "es",
                 "pt")
        self.add(self.
                 ANDROID_FOR_BEGINNERS_ID,
                 "android-pour-les-debutants",
                 "Android pour les debutants",
                 "fr")

        # Opinion
        self.add(self.OPINION_ID, "opinion", "Opinion", "en", "it", "fr")
        self.add(self.OPINION_ID, "opinion", "Opinión", "es")
        self.add(self.OPINION_ID, "kommentar", "Kommentar", "de")
        self.add(self.OPINION_ID, "opiniao", "Opinião", "pt")

        # WikiPIT
        self.add(self.WIKIPIT_ID, "wikipit", "WikiPIT")

        # Poll
        self.add(self.POLL_ID, "encuesta", "Encuesta", "es")
        self.add(self.POLL_ID, "enquete", "Enquete", "pt")
        self.add(self.POLL_ID, "poll", "Poll", "en")
        self.add(self.POLL_ID, "sondage", "Sondage", "fr")
        self.add(self.POLL_ID, "sondaggio", "Sondaggio", "it")
        self.add(self.POLL_ID, "umfrage", "Umfrage", "de")

        # App of the week
        self.add(self.APPS_OF_THE_WEEK_ID,
                 "apps-da-semana", "Apps da semana", "pt")
        self.add(self.APPS_OF_THE_WEEK_ID, "apps-de-la-semaine",
                 "Apps de la semaine", "fr")
        self.add(self.APPS_OF_THE_WEEK_ID, "apps-de-la-semana",
                 "Apps de la semana", "es")
        self.add(self.APPS_OF_THE_WEEK_ID,
                 "apps-der-woche", "Apps der Woche", "de")
        self.add(self.APPS_OF_THE_WEEK_ID,
                 "apps-of-the-week", "Apps of the week", "en")
        self.add(self.APPS_OF_THE_WEEK_ID, "app-della-settimana",
                 "App della settimana", "it")

        # Gadget of the week
        self.add(self.GADGET_OF_THE_WEEK_ID,
                 "gadget-der-woche", "Gadget der Woche", "de")
        self.add(self.GADGET_OF_THE_WEEK_ID,
                 "gadget-of-the-week", "Gadget of the Week", "en")
        self.add(self.GADGET_OF_THE_WEEK_ID, "gadget-della-settimana",
                 "Gadget della settimana", "it")
        self.add(self.GADGET_OF_THE_WEEK_ID, "gadget-de-la-semana",
                 "Gadget de la semana", "es")
        self.add(self.GADGET_OF_THE_WEEK_ID, "gadget-de-la-semaine",
                 "Gadget de la semaine", "fr")
        self.add(self.GADGET_OF_THE_WEEK_ID,
                 "gadget-da-semana", "Gadget da Semana", "pt")

        # Interview
        self.add(self.INTERVIEW_ID, "interview", "Interview", "de", "en", "fr")
        self.add(self.INTERVIEW_ID, "intervista", "Intervista", "it")
        self.add(self.INTERVIEW_ID, "entrevista", "Entrevista", "es", "pt")

        # Review
        self.add(self.REVIEW_ID, "analise", "Análise", "pt")
        self.add(self.REVIEW_ID, "analisis", "Análisis", "es")
        self.add(self.REVIEW_ID, "recensione", "Recensione", "it")
        self.add(self.REVIEW_ID, "review", "Review", "en")
        self.add(self.REVIEW_ID, "test", "Test", "de", "fr")

        # Inside AndroidPIT
        self.add(self.INSIDE_ANDROIDPIT_ID, "inside-androidpit",
                 "Inside AndroidPIT", "de", "en")
        self.add(self.INSIDE_ANDROIDPIT_ID, "dentro-androidpit",
                 "Dentro de AndroidPIT", "es")
        self.add(self.INSIDE_ANDROIDPIT_ID, "bastidores-androidpit",
                 "Bastidores do AndroidPIT", "pt")
        self.add(self.INSIDE_ANDROIDPIT_ID,
                 "androidpit-inside", "AndroidPIT Inside", "fr")
        self.add(self.INSIDE_ANDROIDPIT_ID,
                 "dentro-androidpit", "Dentro AndroidPIT", "it")

        # Drones
        self.add(self.DRONES_ID, "drones", "Drones", "en", "pt", "fr", "es")
        self.add(self.DRONES_ID, "drohnen", "Drohnen", "de")
        self.add(self.DRONES_ID, "droni", "Droni", "it")

        # Winners and losers
        self.add(self.WINNERS_AND_LOSERS_ID, "gagnants-et-perdants",
                 "Gagnants et perdants", "fr")
        self.add(self.WINNERS_AND_LOSERS_ID, "ganadores-y-perdedores",
                 "Ganadores y perdedores", "es")
        self.add(self.WINNERS_AND_LOSERS_ID, "gewinner-und-verlierer",
                 "Gewinner und Verlierer", "de")
        self.add(self.WINNERS_AND_LOSERS_ID, "vincitori-e-perdenti",
                 "Vincitori e perdenti", "it")
        self.add(self.WINNERS_AND_LOSERS_ID,
                 "winners-and-losers", "Winners and losers", "en")
        self.add(self.WINNERS_AND_LOSERS_ID, "ganhadores-e-perdedores",
                 "Ganhadores e perdedores", "pt")

        # Former news categories
        self.add(self.HARDWARE_ID, "hardware", "Hardware")

        self.add(self.APPS_ID, "apps", "Apps", "de", "en")
        self.add(self.APPS_ID, "aplicaciones", "Aplicaciones", "es")
        self.add(self.APPS_ID, "aplicativos", "Aplicativos", "pt")
        self.add(self.APPS_ID, "applications", "Applications", "fr")
        self.add(self.APPS_ID, "applicazioni", "Applicazioni", "it")

        self.add(self.TIPS_AND_TRICKS_ID,
                 "tipps-und-tricks", "Tipps & Tricks", "de")
        self.add(self.TIPS_AND_TRICKS_ID,
                 "tips-and-tricks", "Tips & Tricks", "en")
        self.add(self.TIPS_AND_TRICKS_ID, "trucos-consejos",
                 "Consejos y trucos", "es")
        self.add(self.TIPS_AND_TRICKS_ID, "dicas-e-curiosidades",
                 "Dicas e Curiosidades", "pt")
        self.add(self.TIPS_AND_TRICKS_ID,
                 "trucs-et-astuces", "Trucs & Astuces", "fr")
        self.add(self.TIPS_AND_TRICKS_ID, "trucchi", "Trucchi", "it")

        self.add(self.VIDEO_ID, "video", "Video", "de", "en", "it")
        self.add(self.VIDEO_ID, "video", "Vídeo", "es", "pt")
        self.add(self.VIDEO_ID, "video", "Vidéo", "fr")

    def add(self, id, transcription, label, *languages):
        if len(languages) == 0:
            languages = ('en', 'de', 'it', 'es', 'fr', 'pt')

        if self.directory.get(id) == None:
            self.directory[id] = {}

        entry = self.directory.get(id)

        for language in languages:
            entry[language] = {
                'slug': transcription,
                'label': label,
                'heading': label,
                'language': language
            }

        self.directory[id] = entry

    def addWithHeading(self, id, transcription, label, heading, *languages):
        if len(languages) == 0:
            languages = ('en', 'de', 'it', 'es', 'fr', 'pt')

        if self.directory.get(id) == None:
            self.directory[id] = {}

        entry = self.directory.get(id)

        for language in languages:
            entry[language] = {
                'slug': transcription,
                'label': label,
                'heading': heading,
                'language': language
            }

        self.directory[id] = entry

    def get(self, id):
        entry = self.directory.get(id)
        return entry


tagDir = TagDir()


def getLanguage(slug):
    try:
        l = w.Term.q.filter(w.Term.taxonomy == 'language',
                            w.Term.slug == slug).all()
        return l
    except Exception as e:
        logging.error(e)
        return []


def getTermTranslations():
    terms = w.Term.q.filter(w.Term.taxonomy == 'term_translations').all()
    term_translations = []
    for term in terms:
        translationIds = phpserialize.loads(bytes(term.description, 'utf-8'))
        for k, termId in translationIds.items():
            translated_term = w.Term.q.filter(w.Term.id == termId).first()
            if translated_term != None:
                term_translations.append(translated_term)
            else:
                print('translationIds', translationIds)
                raise Exception(f'{k} with {termId} not found')

    return term_translations


def findTermTranslationByName(name, termTranslations):
    found = [x for x in termTranslations if x.name == name]
    if len(found) > 0:
        return found[0]
    else:
        return None


def uniqid(prefix=''):
    return prefix + hex(int(time()))[2:10] + hex(int(time()*1000000) % 0x100000)[2:7]


def handleCategories(article):
    categoryIds = extractStringList(article.otherTagIds)
    termTranslations = getTermTranslations()

    try:
        if len(categoryIds) > 0:
            logging.info(f'ensuring categories {categoryIds}')
            wp_categories = []
            for categoryId in categoryIds:

                category = tagDir.get(categoryId)
                if category != None:
                    lang_category = category.get(article.language)

                    wp_category = findTermTranslationByName(
                        lang_category.get('label'), termTranslations)
                    if wp_category != None:
                        wp_categories.append(wp_category)
                    else:
                        # create terms
                        term_translation_desc = {}
                        wp_categories_created = []
                        for k, translation in category.items():
                            slug = translation.get('slug')
                            language = translation.get('language')
                            tterm = w.Term(taxonomy='category', name=translation.get('label'),
                                           slug=f'{slug}-{language}')

                            tterm_languageterm = w.Term.q.filter(
                                w.Term.taxonomy == 'term_language', w.Term.slug == f'pll_{language}').first()
                            if tterm_languageterm == None:
                                raise Exception(
                                    f'term language for {language} not found')

                            tterm.terms.append(tterm_languageterm)
                            # NEED TO add terms for term_translations AND the specific language

                            w.session.add(tterm)
                            w.session.commit()
                            wp_categories_created.append(tterm)
                            term_translation_desc[translation.get(
                                'language')] = tterm.id

                        # create term_translations entity
                        term_translation_unique = uniqid('pll_')
                        term_translation = w.Term(
                            taxonomy='term_translations', name=term_translation_unique, slug=term_translation_unique)
                        term_translation.description = phpserialize.dumps(
                            term_translation_desc)
                        w.session.add(term_translation)
                        w.session.commit()

                        for wp_createdCategory in wp_categories_created:
                            wp_createdCategory.terms.append(term_translation)
                            w.session.add(wp_createdCategory)

                        w.session.commit()

                        # append matching category
                        termTranslations = getTermTranslations()
                        wp_category = findTermTranslationByName(
                            lang_category.get('label'), termTranslations)

                        if wp_category != None:
                            wp_categories.append(wp_category)
                        else:
                            raise Exception(
                                f'unexpected behavoir on category: {lang_category}')
                else:
                    logging.error(f'{categoryId} not handled by tagDir?')
            return wp_categories
        return []
    except Exception as e:
        logging.error(e)
        raise e
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
