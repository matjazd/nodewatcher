import os

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, Http404
from django.views.decorators.cache import cache_control
from django.views.static import serve

from web.monitor import tasks as monitor_tasks

@cache_control(max_age = 300)
def graph_image(request, graph_id, timespan):
  """
  Serves the graph image, requesting graph redraw when necessary.
  """
  result = cache.get('nodewatcher.graphs.drawn.{0}.{1}'.format(graph_id, timespan))
  if not result:
    # First ensure that the graph is actually drawn
    monitor_tasks.draw_graph.delay(graph_id, timespan).get()
  
  # Send the proper file
  graph_file = os.path.join(settings.GRAPH_DIR, '{0}-{1}.png'.format(graph_id, timespan))
  if settings.DEBUG:
    return serve(request, graph_file, '/')
  else:
    response = HttpResponse()
    response['X-Sendfile'] = graph_file 
    response['Content-Type'] = ''
    return response
