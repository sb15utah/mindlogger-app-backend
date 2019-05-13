# -*- coding: utf-8 -*-
from girder import events
from girder.constants import SortDir
from girder.exceptions import ValidationException
from girder.models.user import User
from girder.plugin import GirderPlugin
from girder.settings import SettingDefault
from girder.utility import setting_utilities
from . import rest, constants, providers


@setting_utilities.validator(constants.PluginSettings.PROVIDERS_ENABLED)
def validateProvidersEnabled(doc):
    if not isinstance(doc['value'], (list, tuple)):
        raise ValidationException('The enabled providers must be a list.', 'value')


@setting_utilities.validator(constants.PluginSettings.IGNORE_REGISTRATION_POLICY)
def validateIgnoreRegistrationPolicy(doc):
    if not isinstance(doc['value'], bool):
        raise ValidationException('Ignore registration policy setting must be boolean.', 'value')


@setting_utilities.validator({
    constants.PluginSettings.GOOGLE_CLIENT_ID,
    constants.PluginSettings.GLOBUS_CLIENT_ID,
    constants.PluginSettings.GITHUB_CLIENT_ID,
    constants.PluginSettings.LINKEDIN_CLIENT_ID,
    constants.PluginSettings.BITBUCKET_CLIENT_ID,
    constants.PluginSettings.BOX_CLIENT_ID,
    constants.PluginSettings.GOOGLE_CLIENT_SECRET,
    constants.PluginSettings.GLOBUS_CLIENT_SECRET,
    constants.PluginSettings.GITHUB_CLIENT_SECRET,
    constants.PluginSettings.LINKEDIN_CLIENT_SECRET,
    constants.PluginSettings.BITBUCKET_CLIENT_SECRET,
    constants.PluginSettings.BOX_CLIENT_SECRET
})
def validateOtherSettings(event):
    pass


def checkOauthUser(event):
    """
    If an OAuth2 user without a password tries to log in with a password, we
    want to give them a useful error message.
    """
    user = event.info['user']
    if user.get('oauth'):
        if isinstance(user['oauth'], dict):
            # Handle a legacy format where only 1 provider (Google) was stored
            prettyProviderNames = 'Google'
        else:
            prettyProviderNames = ', '.join(
                providers.idMap[val['provider']].getProviderName(external=True)
                for val in user['oauth']
            )
        raise ValidationException(
            'You don\'t have a password. Please log in with %s, or use the '
            'password reset link.' % prettyProviderNames)


class OAuthPlugin(GirderPlugin):
    DISPLAY_NAME = 'OAuth2 login'
    CLIENT_SOURCE_PATH = 'web_client'

    def load(self, info):
        User().ensureIndex((
            (('oauth.provider', SortDir.ASCENDING),
             ('oauth.id', SortDir.ASCENDING)), {}))
        User().reconnect()

        events.bind('no_password_login_attempt', 'oauth', checkOauthUser)

        info['apiRoot'].oauth = rest.OAuth()

        SettingDefault.defaults[constants.PluginSettings.PROVIDERS_ENABLED] = []