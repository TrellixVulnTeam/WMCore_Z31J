from __future__ import (division, print_function)

import json
import logging
import re
from urllib import urlencode

from WMCore.Services.Service import Service


def unflattenJSON(data):
    """Tranform input to unflatten JSON format"""
    columns = data['desc']['columns']
    return [row2dict(columns, row) for row in data['result']]


def row2dict(columns, row):
    """Convert rows to dictionaries with column keys from description"""
    robj = {}
    for k, v in zip(columns, row):
        robj.setdefault(k, v)
    return robj


class CRIC(Service):
    """
    Class which provides client APIs to the CRIC service.
    """

    def __init__(self, url=None, logger=None):
        params = {}
        defaultURL = "https://cms-cric.cern.ch/"
        params['endpoint'] = url or defaultURL
        params.setdefault('cacheduration', 3600)
        params.setdefault('accept_type', 'application/json')
        params.setdefault('content_type', 'application/json')
        params['logger'] = logger if logger else logging.getLogger()
        Service.__init__(self, params)
        self['logger'].info("DEBUG: Initializing CRIC with url: %s", self['endpoint'])

    def _getResult(self, uri, callname="", args=None, unflatJson=True):
        """
        Either fetch data from the cache file or query the data-service
        :param metricNumber: a number corresponding to the SSB metric
        :return: a dictionary
        """
        cachedApi = "%s.json" % callname
        apiUrl = '%s?json&preset=%s' % (uri, callname)

        self['logger'].info('DEBUG: Fetching data from %s, with args %s', apiUrl, args)
        # need to make our own encoding, otherwise Requests class screws it up
        if args:
            apiUrl = "%s&%s" % (apiUrl, urlencode(args, doseq=True))

        data = self.refreshCache(cachedApi, apiUrl)
        results = data.read()
        data.close()

        results = json.loads(results)
        if unflatJson:
            results = unflattenJSON(results)
        return results

    def whoAmI(self):
        """
        Given the authentication mechanism used for this request (x509 so far),
        return information about myself, like DN/ roles/groups, etc
        :return: FIXME FIXME a list of dictionary?
        """
        uri = "/api/accounts/user/query/"
        userinfo = self._getResult(uri, callname='whoami', unflatJson=False)
        return userinfo['result']

    # TODO how about renaming it to userNameToDN???
    def userNameDn(self, username):
        """
        Convert CERN Nice username to DN.
        :param username: string with the username
        :return: a string wit the user's DN
        """
        ### TODO: use a different cache file and try again if the user is still not there
        userdn = ""
        uri = "/api/accounts/user/query/"
        userinfo = self._getResult(uri, callname='people')
        for x in userinfo:
            if x['username'] == username:
                userdn = x['dn']
                break
        return userdn

    # TODO should we rename it to getAllPSNs???
    def getAllCMSNames(self):
        """
        _getAllCMSNames_

        Retrieve all CMSNames from CRIC
        :return: a flat list of CMS site names
        """
        uri = "/api/cms/site/query/"
        extraArgs = {"rcsite_state": "ANY"}
        sitenames = self._getResult(uri, callname='site-names', args=extraArgs)

        cmsnames = [x['alias'] for x in sitenames if x['type'] == 'psn']
        return cmsnames

    def getAllPhEDExNodeNames(self, pattern=None, excludeBuffer=False):
        """
        _getAllPhEDExNodeNames_
        Retrieve all PNNs from CRIC and filter them out if a pattern has been
        provided.
        :param pattern: a regex to be applied to filter the output
        :param excludeBuffer: flag to exclude T1 Buffer endpoints
        :return: a flat list of PNNs
        """
        uri = "/api/cms/site/query/"
        extraArgs = {"rcsite_state": "ANY"}
        sitenames = self._getResult(uri, callname='site-names', args=extraArgs)

        nodeNames = [x['alias'] for x in sitenames if x['type'] == 'phedex']
        if excludeBuffer:
            nodeNames = [x for x in nodeNames if not x.endswith("_Buffer")]
        if pattern and isinstance(pattern, basestring):
            pattern = re.compile(pattern)
            nodeNames = [x for x in nodeNames if pattern.match(x)]
        return nodeNames

    def PNNstoPSNs(self, pnns):
        """
        Given a list of PNNs, return all their PSNs

        :param pnns: a string or a list of PNNs
        :return: a list with unique PSNs matching those PNNs
        """
        if isinstance(pnns, basestring):
            pnns = [pnns]

        uri = "/api/cms/site/query/"
        extraArgs = {"rcsite_state": "ANY"}
        mapping = self._getResult(uri, callname='data-processing', args=extraArgs)

        psns = set()
        for pnn in pnns:
            if pnn == "T0_CH_CERN_Export" or pnn.endswith("_MSS") or pnn.endswith("_Buffer"):
                continue
            psnSet = set()
            for item in mapping:
                if pnn == item['phedex_name']:
                    psnSet.add(item['psn_name'])
            if psnSet:
                psns.update(psnSet)
            else:
                self["logger"].warning("No PSNs for PNN: %s" % pnn)
        return list(psns)

    def PSNstoPNNs(self, psns):
        """
        Given a list of PSNs, return all their PNNs

        :param psns: a string or a list of PSNs
        :return: a list with unique PNNs matching those PSNs
        """
        if isinstance(psns, basestring):
            psns = [psns]

        uri = "/api/cms/site/query/"
        extraArgs = {"rcsite_state": "ANY"}
        mapping = self._getResult(uri, callname='data-processing', args=extraArgs)

        pnns = set()
        for psn in psns:
            pnnSet = set()
            for item in mapping:
                if item['psn_name'] == psn:
                    pnnSet.add(item['phedex_name'])
            if pnnSet:
                pnns.update(pnnSet)
            else:
                self["logger"].warning("No PNNs for PSN: %s" % psn)
        return list(pnns)

    def PSNtoPNNMap(self, psnPattern=''):
        """
        Given a PSN regex pattern, return a map of PSN to PNNs
        :param psnPattern: a pattern string
        :return: a dictionary of PNNs list keyed by their PSN
        """
        if not isinstance(psnPattern, basestring):
            raise TypeError('psnPattern argument must be of type basestring')

        mapping = {}
        uri = "/api/cms/site/query/"
        extraArgs = {"rcsite_state": "ANY"}
        psnPattern = re.compile(psnPattern)
        results = self._getResult(uri, callname='data-processing', args=extraArgs)

        for entry in results:
            if psnPattern.match(entry['psn_name']):
                mapping.setdefault(entry['psn_name'], set()).add(entry['phedex_name'])
        return mapping
