# -*- coding: utf-8 -*-
from . import constants
from girder.api import access
from girder.api.describe import Description, describeRoute
from girder.api.rest import Resource
from girder.models.setting import Setting


class GoogleAnalytics(Resource):
    def __init__(self):
        super(GoogleAnalytics, self).__init__()
        self.resourceName = 'google_analytics'
        self.route('GET', ('id',), self.getId)

    @access.public
    @describeRoute(
        Description('Public url for getting the Google Analytics tracking id.')
    )
    def getId(self, params):
        trackingId = Setting().get(constants.PluginSettings.GOOGLE_ANALYTICS_TRACKING_ID)
        return {'google_analytics_id': trackingId}