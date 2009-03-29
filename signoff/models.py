from django.db import models

from pushes.models import Push
from life.models import Tree, Locale

class Milestone(models.Model):
    """ stores unique milestones like fx35b4
    The milestone is open for signoff between string_freeze and code
    """
    code = models.CharField(max_length = 30)
    name = models.CharField(max_length = 50, blank = True, null = True)

    def get_start_event(self):
        return Event.objects.get(type=0, milestone=self)

    def get_end_event(self):
        return Event.objects.get(type=1, milestone=self)

    start_event = property(get_start_event)
    end_event = property(get_end_event)

    def __unicode__(self):
        return self.name or self.code

TYPE_CHOICES = (
    (0, 'signoff start'),
    (1, 'signoff end'),
)

class Event(models.Model):
    name = models.CharField(max_length = 50)
    type = models.IntegerField(choices=TYPE_CHOICES)
    date = models.DateField()
    milestone = models.ForeignKey(Milestone, related_name='events')

    def __unicode__(self):
        return '%s for %s (%s)' % (self.name, self.milestone, self.date)

class Signoff(models.Model):
    revision = models.ForeignKey(Push)
    milestone = models.ForeignKey(Milestone, related_name = 'signoffs')
    author = models.CharField(max_length = 50, blank = True, null = True)
    tree = models.ForeignKey(Tree)
    locale = models.ForeignKey(Locale)

    def __unicode__(self):
        return 'Signoff for %s %s by %s' % (self.milestone, self.locale.code, self.author)
