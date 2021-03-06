# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is l10n django site.
#
# The Initial Developer of the Original Code is
# Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2010
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

'''Views for compare-locales output and statistics, in particular dashboards
and progress graphs.
'''

from collections import defaultdict
from datetime import datetime, timedelta
import time

from django.shortcuts import render_to_response
from django.template.loader import render_to_string
from django.http import HttpResponse, HttpResponseNotFound,\
    HttpResponseNotModified
from django.db.models import Min, Max
from django.views.decorators.cache import cache_control
from django.utils import simplejson
from django.utils.http import urlencode
from django.utils.safestring import mark_safe

from l10nstats.models import *
from tinder.views import generateLog

def getRunsBefore(tree, stamp, locales):
    """Get the latest run for each of the given locales and tree.

    Returns a dict of locale code and Run.
    """
    locales = list(locales)
    runs = {}
    while True:
        q = Run.objects.filter(tree=tree, locale__in=locales,
                               srctime__lt=stamp)
        q = q.order_by('-srctime')[:len(locales)*2]
        q = q.select_related('locale')
        if q.count() == 0:
            return runs
        for r in q:
            if r.locale.code not in runs:
                runs[r.locale.code] = r
                locales.remove(r.locale)


def index(request):
    """The main dashboard entry page.
    
    Implemented with a Simile Exhibit.
    """
    # verify args?
    args = []
    if 'locale' in request.GET:
        locales = request.GET.getlist('locale')
        locales = Locale.objects.filter(code__in=locales)
        locales = locales.values_list('code', flat=True)
        if locales:
            args += [('locale', loc) for loc in locales]
    if 'tree' in request.GET:
        trees = request.GET.getlist('tree')
        trees = Tree.objects.filter(code__in=trees)
        trees = trees.values_list('code', flat=True)
        if trees:
            args += [('tree', t) for t in trees]
    return render_to_response('l10nstats/index.html',
                              {'args': mark_safe(urlencode(args))})

schema = {
    "types": {
        "Build": {
            "pluralLabel": "Builds"
            },
        "Priority": {
            "pluralLabel": "Priorities"
            }
        },
    "properties": {
        "completion": {
            "valueType": "number"
            },
        "changed": {
            "valueType": "number"
            },
        "missing": {
            "valueType": "number"
            },
        "report": {
            "valueType": "number"
            },
        "warnings": {
            "valueType": "number"
            },
        "errors": {
            "valueType": "number"
            },
        "obsolete": {
            "valueType": "number"
            },
        "unchanged": {
            "valueType": "number"
            },
        "starttime": {
            "valueType": "date"
            },
        "endtime": {
            "valueType": "date"
            }
        }
    }

@cache_control(max_age=5*60)
def status_json(request):
    """The json output for the builds.
    
    Used by the main dashboard page Exhibit.
    """

    q = Run.objects.filter(active__isnull=False).order_by('tree__code',
                                                          'locale__code')
    if 'tree' in request.GET:
        q = q.filter(tree__code__in=request.GET.getlist('tree'))
    if 'locale' in request.GET:
        q = q.filter(locale__code__in=request.GET.getlist('locale'))
    leafs = ['tree__code', 'locale__code', 'id',
             'missing', 'missingInFiles', 'report', 'warnings',
             'errors', 'unchanged', 'total', 'obsolete', 'changed',
             'completion']
    def toExhibit(d):
        missing = d['missing'] + d['missingInFiles']
        result = 'success'
        tree = d['tree__code']
        locale = d['locale__code']
        if missing or ('errors' in d and d['errors']):
            result = 'failure'
        elif d['obsolete']:
            result = 'warnings'
        rd =  {'id': '%s/%s' % (tree, locale),
                'runid': d['id'],
                'label': locale,
                'locale': locale,
                'tree': tree,
                'type': 'Build',
                'result': result,
                'missing': missing,
                'report': d['report'],
                'warnings': d['warnings'],
                'changed': d['changed'],
                'unchanged': d['unchanged'],
                'total': d['total'],
                'completion': d['completion']
                }
        if 'errors' in d and d['errors']:
            rd['errors'] = d['errors']
        if 'obsolete' in d and d['obsolete']:
            rd['obsolete'] = d['obsolete']
        return rd
    items = map(toExhibit, q.values(*leafs))
    data = {'items': items}
    data.update(schema)
    return HttpResponse(simplejson.dumps(data, indent=2))


def homesnippet(request):
    week_ago = datetime.utcnow() - timedelta(7)
    act = Active.objects.filter(run__srctime__gt=week_ago)
    act = act.order_by('run__tree__code')
    act = act.values_list('run__tree__code', flat=True).distinct()
    return render_to_string('l10nstats/snippet.html', {
            'trees': act,
            })
    


def teamsnippet(request, loc):
    act = Run.objects.filter(locale = loc, active__isnull=False)
    week_ago = datetime.utcnow() - timedelta(7)
    act = act.filter(srctime__gt=week_ago)
    act = act.order_by('tree__code').select_related('tree')
    return render_to_string('l10nstats/team-snippet.html', {
            'actives': act,
            })


def history_plot(request):
    """Progress of a single locale and tree.
    
    Implemented with a Simile Timeplot.
    """
    tree = locale = None
    endtime = datetime.utcnow().replace(microsecond=0)
    starttime = endtime - timedelta(14)
    second = timedelta(0, 1)
    if 'tree' in request.GET:
        try:
            tree = Tree.objects.get(code=request.GET['tree'])
        except Tree.DoesNotExist:
            pass
    if 'locale' in request.GET:
        try:
            locale = Locale.objects.get(code=request.GET['locale'])
        except Locale.DoesNotExist:
            pass
    if 'starttime' in request.GET:
        starttime = datetime.utcfromtimestamp(int(request.GET['starttime']))
    if 'endtime' in request.GET:
        endtime = datetime.utcfromtimestamp(int(request.GET['endtime']))
    if locale is not None and tree is not None:
        q = Run.objects.filter(tree=tree, locale=locale)
        q2 = q.filter(srctime__lte=endtime,
                      srctime__gte=starttime).order_by('srctime')
        p = None
        try:
            p = q2.filter(srctime__lt=starttime).order_by('-srctime')[0]
        except IndexError:
            pass
        def runs(_q, p):
            if p is not None:
                yield {'srctime': starttime,
                       'missing': p.missing + p.missingInFiles + p.report,
                       'obsolete': p.obsolete,
                       'unchanged': p.unchanged}
            r = None
            for r in _q:
                if p is not None:
                    yield {'srctime': r.srctime - second,
                           'missing': p.missing + p.missingInFiles + p.report,
                           'obsolete': p.obsolete,
                           'unchanged': p.unchanged}
                yield {'srctime': r.srctime,
                       'missing': r.missing + r.missingInFiles + r.report,
                       'obsolete': r.obsolete,
                       'unchanged': r.unchanged}
                p = r
            if r is not None:
                yield {'srctime': endtime,
                       'missing': r.missing + r.missingInFiles + r.report,
                       'obsolete': r.obsolete,
                       'unchanged': r.unchanged}
        stamps = {}
        stamps['start'] = int(time.mktime(starttime.timetuple()))
        stamps['end'] = int(time.mktime(endtime.timetuple()))
        stamps['previous'] = stamps['start']*2 - stamps['end']
        stamps['next'] = stamps['end']*2 - stamps['start']
        return render_to_response('l10nstats/history.html',
                                  {'locale': locale.code,
                                   'tree': tree.code,
                                   'starttime': starttime,
                                   'endtime': endtime,
                                   'stamps': stamps,
                                   'runs': runs(q2, p)})
    return HttpResponseNotFound("sorry, gimme tree and locale")

def tree_progress(request, tree):
    """Progress of all locales on a tree.
    
    Display the number of successful vs not locales.
    
    Implemented as Simile Timeplot.
    """
    try:
        tree = Tree.objects.get(code=tree)
    except Tree.DoesNotExist:
        return HttpResponseNotFound("sorry, gimme tree")

    locales = Locale.objects.filter(run__tree=tree, run__active__isnull=False)
    locales = list(locales)
    if not locales:
        return HttpResponse("no statistics for %s" % str(tree))
    q = Run.objects.filter(tree=tree)
    _d = q.aggregate(allStart=Min('srctime'), allEnd=Max('srctime'))
    allStart, allEnd = (_d[k] for k in ('allStart', 'allEnd'))
    displayEnd = allEnd + timedelta(.5)

    endtime = datetime.utcnow().replace(microsecond=0)
    starttime = endtime - timedelta(14)

    if starttime > allEnd:
        # by default, we'd just see a flat graph, show half a day more 
        # than allend
        endtime = displayEnd
        starttime = endtime - timedelta(14)

    if 'starttime' in request.GET:
        try:
            starttime = datetime.utcfromtimestamp(int(request.GET['starttime']))
        except Exception:
            pass
        if starttime < allStart:
            # make sure that even though there nothing to see, 
            # the slider shows all times
            allStart = starttime
    if 'endtime' in request.GET:
        try:
            endtime = datetime.utcfromtimestamp(int(request.GET['endtime']))
        except Exception:
            pass

    q = q.filter(locale__in=locales)
    q2 = q.filter(srctime__lte=endtime,
                  srctime__gte=starttime).order_by('srctime')
    q2 = q2.select_related('locale')

    initial_runs = getRunsBefore(tree, starttime,
                                 locales)
    results = {}
    datadict = defaultdict(dict)
    for loc, r in initial_runs.iteritems():
        datadict[starttime][loc] = r.missing + r.missingInFiles + r.report
    for r in q2:
        datadict[r.srctime][r.locale.code] = r.missing + r.missingInFiles + r.report
    data = [{'srctime': t, 'locales': simplejson.dumps(datadict[t])}
            for t in sorted(datadict.keys())]

    bound = request.GET.get("bound", "0")
    try:
        bound = int(bound)
    except:
        bound = 0

    return render_to_response('l10nstats/tree_progress.html',
                              {'tree': tree.code,
                               'bound': bound,
                               'showBad': 'hideBad' not in request.GET,
                               'startTime': starttime,
                               'endTime': endtime,
                               'explicitEnd': 'endtime' in request.GET,
                               'explicitStart': 'starttime' in request.GET,
                               'allStart': allStart,
                               'allEnd': displayEnd,
                               'data': data})


def grid(request):
    """View to show which runs are against which revisions.

    Parameters are locale and tree. If not given, shows a selection
    page.

    Experimental, might not stay.
    """
    trees = request.GET.getlist('tree')
    locales = request.GET.getlist('locale')
    if not (trees and locales):
        # hook up template here
        return HttpResponse("specify locale and tree")
    epoch = datetime.utcfromtimestamp(0)
    tree = trees[0]
    locale = locales[0]

    # find the runs for this locale and tree
    runs = Run.objects.filter(locale__code=locale,
                              tree__code=tree)[:100]
    changesets = Changeset.objects.filter(run__in=runs).distinct()
    changesets = changesets.order_by('push__push_date')
    changesets = changesets.select_related('push__repository')

    table = defaultdict(list)
    x = set()
    y = set()
    for run in runs:
        revs = run.revisions.all()
        l10n = None
        en = []
        for rev in revs:
            if rev.repository.forest_id is not None:
                l10n = rev
            else:
                en.append(rev)
        en.sort(key=lambda _rev: _rev.repository.name)
        en = tuple(en)
        x.add(l10n)
        y.add(en)
        table[(l10n,en)].append(run)
    X = sorted(x, key=lambda cs: cs.push and cs.push.push_date or epoch)
    Y = sorted(y, key=lambda t: map(lambda cs: cs.push and cs.push.push_date or epoch, t))
    rows = []
    for y in Y:
        row = [(x,y) in table and table[(x,y)] or None for x in X]
        rows.append(row)
    return render_to_response('l10nstats/grid.html',
                              {'X': X,
                               'rows': zip(Y, rows)})


class JSONAdaptor(object):
    """Helper class to make the json output from compare-locales
    easier to digest for the django templating language.
    """
    def __init__(self, node, base):
        self.fragment = node[0]
        self.base = base
        data = node[1]
        self.children = data.get('children', [])
        if 'value' in data:
            self.value = data['value']
            if 'obsoleteFile' in self.value:
                self.fileIs = 'obsolete'
            elif 'missingFile' in self.value:
                self.fileIs = 'missing'
            elif ('missingEntity' in self.value or 
                  'obsoleteEntity' in self.value or
                  'warning' in self.value or
                  'error' in self.value):
                errors = [{'key': e, 'class': 'error'}
                          for e in self.value.get('error', [])]
                warnings = [{'key': e, 'class': 'warning'}
                          for e in self.value.get('warning', [])]
                entities = \
                    [{'key': e, 'class': 'missing'}
                     for e in self.value.get('missingEntity', [])] + \
                     [{'key': e, 'class': 'obsolete'}
                     for e in self.value.get('obsoleteEntity', [])]
                entities.sort(key=lambda d: d['key'])
                self.entities = errors + warnings + entities
    @classmethod
    def adaptChildren(cls, _lst, base=''):
        for node in _lst:
            yield JSONAdaptor(node, base)
    def __iter__(self):
        if self.base:
            base = self.base + '/' + self.fragment
        else:
            base = self.fragment
        return self.adaptChildren(self.children, base)
    @property
    def path(self):
        if self.base:
            return self.base + '/' + self.fragment
        return self.fragment

def compare(request):
    """HTML pretty-fied output of compare-locales.
    """
    run = Run.objects.get(id=request.GET['run'])
    json = ''
    for step in run.build.steps.filter(name__startswith='moz_inspectlocales'):
        for log in step.logs.all():
            for chunk in generateLog(run.build.builder.master.name,
                                     log.filename):
                if chunk['channel'] == 5:
                    json += chunk['data']
    json = simplejson.loads(json)
    nodes = JSONAdaptor.adaptChildren(json['details'].get('children', []))
    summary = json['summary']
    if 'keys' not in summary:
        summary['keys'] = 0
    # create table widths for the progress bar
    _width = 300
    widths = {}
    for k in ('changed', 'missing', 'missingInFiles', 'report', 'unchanged'):
        widths[k] = summary.get(k, 0)*300/summary['total']
    return render_to_response('l10nstats/compare.html',
                              {'run': run,
                               'nodes': nodes,
                               'widths': widths,
                               'summary': summary})
