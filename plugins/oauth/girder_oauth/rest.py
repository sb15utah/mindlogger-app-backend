# -*- coding: utf-8 -*-
import cherrypy
import datetime
import six

from girderformindlogger import events
from girderformindlogger.constants import AccessType
from girderformindlogger.exceptions import RestException
from girderformindlogger.api.describe import Description, autoDescribeRoute
from girderformindlogger.api.rest import Resource
from girderformindlogger.api import access
from girderformindlogger.models.setting import Setting
from girderformindlogger.models.token import Token

from . import providers
from .settings import PluginSettings


class OAuth(Resource):
    def __init__(self):
        super(OAuth, self).__init__()
        self.resourceName = 'oauth'

        self.route('GET', ('provider',), self.listProviders)
        self.route('GET', (':provider', 'callback'), self.callback)

    def _createStateToken(self, redirect):
        csrfToken = Token().createToken(days=0.25)

        # The delimiter is arbitrary, but a dot doesn't need to be URL-encoded
        state = '%s.%s' % (csrfToken['_id'], redirect)
        return state

    def _validateCsrfToken(self, state):
        """
        Tests the CSRF token value in the cookie to authenticate the user as
        the originator of the OAuth2 login. Raises a RestException if the token
        is invalid.
        """
        csrfTokenId, _, redirect = state.partition('.')

        token = Token().load(csrfTokenId, objectId=False, level=AccessType.READ)
        if token is None:
            raise RestException('Invalid CSRF token (state="%s").' % state, code=403)

        Token().remove(token)

        if token['expires'] < datetime.datetime.utcnow():
            raise RestException('Expired CSRF token (state="%s").' % state,
                                code=403)

        if not redirect:
            raise RestException('No redirect location (state="%s").' % state)

        return redirect

    @access.public
    @autoDescribeRoute(
        Description('Get the list of enabled OAuth2 providers and their URLs.')
        .notes('By default, returns an object mapping names of providers to '
               'the appropriate URL.')
        .param('redirect', 'Where the user should be redirected upon completion'
               ' of the OAuth2 flow.')
        .param('list', 'Whether to return the providers as an ordered list.',
               required=False, dataType='boolean', default=False)
    )
    def listProviders(self, redirect, list):
        enabledNames = Setting().get(PluginSettings.PROVIDERS_ENABLED)

        enabledProviders = [
            provider
            for providerName, provider in six.viewitems(providers.idMap)
            if providerName in enabledNames
        ]
        if enabledProviders:
            state = self._createStateToken(redirect)
        else:
            state = None

        if list:
            return [
                {
                    'id': provider.getProviderName(external=False),
                    'name': provider.getProviderName(external=True),
                    'url': provider.getUrl(state)
                }
                for provider in enabledProviders
            ]
        else:
            return {
                provider.getProviderName(external=True): provider.getUrl(state)
                for provider in enabledProviders
            }

    @access.public
    @autoDescribeRoute(
        Description('Callback called by OAuth providers.')
        .param('provider', 'The provider name.', paramType='path')
        .param('state', 'Opaque state string.', required=False)
        .param('code', 'Authorization code from provider.', required=False)
        .param('error', 'Error message from provider.', required=False),
        hide=True
    )
    def callback(self, provider, state, code, error):
        if error is not None:
            raise RestException("Provider returned error: '%s'." % error, code=502)

        self.requireParams({'state': state, 'code': code})

        providerName = provider
        provider = providers.idMap.get(providerName)
        if not provider:
            raise RestException('Unknown provider "%s".' % providerName)

        redirect = self._validateCsrfToken(state)

        providerObj = provider(cherrypy.url())
        token = providerObj.getToken(code)

        event = events.trigger('oauth.auth_callback.before', {
            'provider': provider,
            'token': token
        })
        if event.defaultPrevented:
            raise cherrypy.HTTPRedirect(redirect)

        user = providerObj.getUser(token)

        event = events.trigger('oauth.auth_callback.after', {
            'provider': provider,
            'token': token,
            'user': user
        })
        if event.defaultPrevented:
            raise cherrypy.HTTPRedirect(redirect)

        girderToken = self.sendAuthTokenCookie(user)
        try:
            redirect = redirect.format(girderToken=str(girderToken['_id']))
        except KeyError:
            pass  # in case there's another {} that's not handled by format

        raise cherrypy.HTTPRedirect(redirect)
