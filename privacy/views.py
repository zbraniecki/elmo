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

'''Views of privacy policies and their history.
'''

from django.core.urlresolvers import reverse
from django.db.models import Count
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponseRedirect, HttpResponse
from django.utils.encoding import force_unicode
from django.views.decorators import cache

from privacy.models import Policy, Comment, LogEntry, ADDITION, CHANGE

# We're not using the permission decorators from django.contrib.auth here
# because we don't have a login-view for one, and it's not giving
# us the flexibility to not use those.

def show_policy(request, id=None):
    """Display the currently active policy, or, if id is given, the 
    specified policy.
    """
    try:
        if id is None:
            p = Policy.objects.get(active=True)
        else:
            p = Policy.objects.get(id=int(id))
    except:
        p = None
    if p is not None and p.active:
        logs = LogEntry.objects.filter(content_type=Policy.contenttype())
        logs = logs.filter(object_id=p.id,
                           action_flag = CHANGE,
                           change_message = 'activate')
        logs = logs.order_by('-action_time')
        activation = logs.values_list('action_time', flat=True)[0]
    else:
        activation = None
    c = RequestContext(request, {"policy": p, "activation": activation})
    return render_to_response("privacy/show-policy.html", c)


def versions(request):
    """Show all policies including their active times.

    If the user has permissions, offers to activate a policy, comment, or
    create a new policy.
    """
    policies = Policy.objects.order_by('-pk')
    policies = policies.annotate(noc=Count('comments'))
    policies = policies.select_related('comments')
    los = LogEntry.objects.filter(content_type=Policy.contenttype())
    details = {}
    for lo in los.order_by('action_time'):
        if lo.object_id not in details:
            detail = {}
            details[lo.object_id] = detail
        else:
            detail = details[lo.object_id]
        if lo.action_flag == ADDITION:
            detail['created'] = lo.action_time
        elif lo.action_flag == CHANGE:
            if lo.change_message not in ('deactivate', 'activate'):
                continue
            if 'active_time' not in detail:
                detail['active_time'] = []
            if lo.change_message == 'activate':
                detail['active_time'].append([lo.action_time])
            else:
                detail['active_time'][-1].append(lo.action_time)
    def do_policies(_pols, _details):
        for _p in _pols:
            _d = _p.__dict__.copy()
            _d.update(_details[str(_p.id)])
            _d['comments'] = _p.comments.all()
            yield _d
    c = RequestContext(request, {"policies": do_policies(policies, details)})
    return render_to_response("privacy/versions.html", c)


def add_policy(request):
    """Add a new policy.

    This handles GET and POST, POST defers to post_policy for the
    actual creation handling.
    """
    if request.method == "POST":
        return post_policy(request)
    try:
        current = Policy.objects.get(active=True).text
    except:
        current = ''
    c = RequestContext(request, {'current': current})
    return render_to_response("privacy/add.html", c)

def post_policy(request):
    if not (request.user.has_perm('privacy.add_policy')
            and request.user.has_perm('privacy.add_comment')):
        return HttpResponseRedirect(reverse('accounts.views.index'))
    p = Policy.objects.create(text = request.POST['content'])
    c = Comment.objects.create(text = request.POST['comment'],
                               policy = p,
                               who = request.user)
    LogEntry.objects.log_action(request.user.id,
                                Policy.contenttype().id, p.id,
                                force_unicode(p), ADDITION)
    LogEntry.objects.log_action(request.user.id,
                                Comment.contenttype().id, c.id,
                                force_unicode(c), ADDITION)
                                
                                
    return HttpResponseRedirect(reverse('privacy.views.show_policy', kwargs={'id':p.id}))

def activate_policy(request):
    """Activate a selected policy, requires privacy.activate_policy
    priviledges.
    """
    if not request.user.has_perm('privacy.activate_policy'):
        return HttpResponseRedirect(reverse('accounts.views.versions'))
    if request.method == "POST":
        try:
            policy = Policy.objects.get(id=int(request.POST['active']))
            if not policy.active:
                # need to change active policy, first, deactivate existing
                # actives, then set the new one active. And create LogEntries.
                qa = Policy.objects.filter(active=True)
                for _p in qa:
                    LogEntry.objects.log_action(request.user.id,
                                                Policy.contenttype().id, _p.id,
                                                force_unicode(_p), CHANGE,
                                                change_message="deactivate")
                qa.update(active=False)
                LogEntry.objects.log_action(request.user.id,
                                            Policy.contenttype().id, policy.id,
                                            force_unicode(policy), CHANGE,
                                            change_message="activate")
                policy.active=True
                policy.save()
        except:
            pass
    return HttpResponseRedirect(reverse('privacy.views.versions'))

def add_comment(request):
    """Add a comment to a policy, requires privacy.add_comment
    priviledges.
    """
    if not request.user.has_perm('privacy.add_comment'):
        return HttpResponseRedirect(reverse('accounts.views.versions'))
    if request.method == "POST":
        try:
            p = Policy.objects.get(id = int(request.POST['policy']))
            c = Comment.objects.create(text=request.POST['comment'],
                                       policy=p,
                                       who=request.user)
            LogEntry.objects.log_action(request.user.id,
                                        Comment.contenttype().id, c.id,
                                        force_unicode(c), ADDITION)
        except Exception, e:
            import pdb
            pdb.set_trace()
            pass
    return HttpResponseRedirect(reverse('privacy.views.versions'))

# XXX, bug 563732; use revision-based etag here.
@cache.cache_control(max_age=5*60*60)
def policy_css(request):
    """Serve shared CSS file."""
    return render_to_response("privacy/shared.css",
                              mimetype="text/css")
