import rrdtool
import time
import os
import subprocess
import re

# Models
from wlanlj.nodes.models import StatsSolar
from django.conf import settings
from datetime import datetime
from xml.etree import cElementTree as ElementTree

# Defining some constants and classes for easier usage later
AverageCF = "AVERAGE"
MinCF = "MIN"
MaxCF = "MAX"
GaugeDST = "GAUGE"
CounterDST = "COUNTER"

class RoundRobinArchive:
  def __init__(self, cf, xff, steps, rows):
    self.cf = cf
    self.xff = xff
    self.steps = steps
    self.rows = rows
  
  def __str__(self):
    return "RRA:%s:%s:%s:%s" % (self.cf, self.xff, self.steps, self.rows)

class DataSource:
  def __init__(self, name, type, heartbeat):
    self.name = name
    self.type = type
    self.heartbeat = heartbeat
  
  def __str__(self):
    return "DS:%s:%s:%s:U:U" % (self.name, self.type, self.heartbeat)

class RRAConfiguration:
  last_update = 0

  # Standard archives
  archives = [
    RoundRobinArchive(
      cf = AverageCF,
      xff = 0.5,
      steps = 1,
      rows = 600
    ),
    RoundRobinArchive(
      cf = AverageCF,
      xff = 0.5,
      steps = 6,
      rows = 700
    ),
    RoundRobinArchive(
      cf = AverageCF,
      xff = 0.5,
      steps = 24,
      rows = 775
    ),
    RoundRobinArchive(
      cf = AverageCF,
      xff = 0.5,
      steps = 288,
      rows = 797
    ),
    RoundRobinArchive(
      cf = MinCF,
      xff = 0.5,
      steps = 1,
      rows = 600
    ),
    RoundRobinArchive(
      cf = MinCF,
      xff = 0.5,
      steps = 6,
      rows = 700
    ),
    RoundRobinArchive(
      cf = MinCF,
      xff = 0.5,
      steps = 24,
      rows = 775
    ),
    RoundRobinArchive(
      cf = MinCF,
      xff = 0.5,
      steps = 288,
      rows = 797
    ),
    RoundRobinArchive(
      cf = MaxCF,
      xff = 0.5,
      steps = 1,
      rows = 600
    ),
    RoundRobinArchive(
      cf = MaxCF,
      xff = 0.5,
      steps = 6,
      rows = 700
    ),
    RoundRobinArchive(
      cf = MaxCF,
      xff = 0.5,
      steps = 24,
      rows = 775
    ),
    RoundRobinArchive(
      cf = MaxCF,
      xff = 0.5,
      steps = 288,
      rows = 797
    ),
  ]

class RRALocalTraffic(RRAConfiguration):
  interval = 300
  sources = [
    DataSource(
      'toinet',
      type = CounterDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'frominet',
      type = CounterDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'internal',
      type = CounterDST,
      heartbeat = interval * 2
    )
  ]
  graph = [
    "AREA:toinet#FFD5CC",
    "AREA:frominet#CCFFCC::STACK",
    "AREA:internal#CCE5FF::STACK",
    "LINE1:toinet#CF7E6C:Out     ",
    r'GPRINT:toinet:LAST:Current\:%8.2lf %s',
    r'GPRINT:toinet:AVERAGE:Average\:%8.2lf %s',
    r'GPRINT:toinet:MAX:Maximum\:%8.2lf %s\n',
    "LINE1:frominet#6CCF6C:In      :STACK",
    r'GPRINT:frominet:LAST:Current\:%8.2lf %s',
    r'GPRINT:frominet:AVERAGE:Average\:%8.2lf %s',
    r'GPRINT:frominet:MAX:Maximum\:%8.2lf %s\n',
    "LINE1:internal#6C9CCF:Internal:STACK",
    r'GPRINT:internal:LAST:Current\:%8.2lf %s',
    r'GPRINT:internal:AVERAGE:Average\:%8.2lf %s',
    r'GPRINT:internal:MAX:Maximum\:%8.2lf %s\n',
    '--lower-limit', '0'
  ]

class RRANodesByStatus(RRAConfiguration):
  interval = 300
  sources = [
    DataSource(
      'up',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'down',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'visible',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'invalid',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'pending',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'duped',
      type = GaugeDST,
      heartbeat = interval * 2
    )
  ]
  graph = [
    "LINE1:up#007B0F:up     ",
    r'GPRINT:up:LAST:Current\:%8.2lf',
    r'GPRINT:up:AVERAGE:Average\:%8.2lf',
    r'GPRINT:up:MAX:Maximum\:%8.2lf\n',
    "LINE1:visible#00ADD1:visible",
    r'GPRINT:visible:LAST:Current\:%8.2lf',
    r'GPRINT:visible:AVERAGE:Average\:%8.2lf',
    r'GPRINT:visible:MAX:Maximum\:%8.2lf\n',
    "LINE1:down#CB0000:down   ",
    r'GPRINT:down:LAST:Current\:%8.2lf',
    r'GPRINT:down:AVERAGE:Average\:%8.2lf',
    r'GPRINT:down:MAX:Maximum\:%8.2lf\n',
    "LINE1:duped#7E0097:duped  ",
    r'GPRINT:duped:LAST:Current\:%8.2lf',
    r'GPRINT:duped:AVERAGE:Average\:%8.2lf',
    r'GPRINT:duped:MAX:Maximum\:%8.2lf\n',
    "LINE1:invalid#F8C901:invalid",
    r'GPRINT:invalid:LAST:Current\:%8.2lf',
    r'GPRINT:invalid:AVERAGE:Average\:%8.2lf',
    r'GPRINT:invalid:MAX:Maximum\:%8.2lf\n',
    "LINE1:pending#B1B1B1:pending",
    r'GPRINT:pending:LAST:Current\:%8.2lf',
    r'GPRINT:pending:AVERAGE:Average\:%8.2lf',
    r'GPRINT:pending:MAX:Maximum\:%8.2lf\n',
    '--lower-limit', '0'
  ]

class RRAIface(RRAConfiguration):
  interval = 300
  sources = [
    DataSource(
      'upload',
      type = CounterDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'download',
      type = CounterDST,
      heartbeat = interval * 2
    )
  ]
  graph = [
    "LINE2:upload#DE0056:Upload [B/s]",
    r'GPRINT:upload:LAST:  Current\:%8.2lf %s',
    r'GPRINT:upload:AVERAGE:Average\:%8.2lf %s',
    r'GPRINT:upload:MAX:Maximum\:%8.2lf %s\n',
    "LINE2:download#A150AA:Download [B/s]",
    r'GPRINT:download:LAST:Current\:%8.2lf %s',
    r'GPRINT:download:AVERAGE:Average\:%8.2lf %s',
    r'GPRINT:download:MAX:Maximum\:%8.2lf %s\n',
    '--lower-limit', '0'
  ]

class RRAClients(RRAConfiguration):
  interval = 300
  sources = [
    DataSource(
      'clients',
      type = GaugeDST,
      heartbeat = interval * 2
    )
  ]
  graph = [
    "LINE2:clients#008310:Clients",
    r'GPRINT:clients:LAST:  Current\:%8.2lf',
    r'GPRINT:clients:AVERAGE:Average\:%8.2lf',
    r'GPRINT:clients:MAX:Maximum\:%8.2lf\n',
    '--units-exponent', '0',
    '--lower-limit', '0'
  ]

class RRARTT(RRAConfiguration):
  interval = 300
  sources = [
    DataSource(
      'rtt',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'rtt_min',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'rtt_max',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
  ]
  graph = [
    "LINE1:rtt#0000ff:RTT [ms]",
    r'GPRINT:rtt:LAST:  Current\:%8.2lf',
    r'GPRINT:rtt:AVERAGE:Average\:%8.2lf',
    r'GPRINT:rtt:MAX:Maximum\:%8.2lf\n',
    '--alt-y-grid',
    '--units-exponent', '0',
    '--lower-limit', '0'
  ]

class RRAPacketLoss(RRAConfiguration):
  interval = 300
  sources = [
    DataSource(
      'loss_def',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'loss_100',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'loss_500',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'loss_1000',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'loss_1480',
      type = GaugeDST,
      heartbeat = interval * 2
    )
  ]
  graph = [
    "LINE1:loss_def#0080ff:65 byte packets",
    r'GPRINT:loss_def:LAST:  Current\:%8.2lf',
    r'GPRINT:loss_def:AVERAGE:Average\:%8.2lf',
    r'GPRINT:loss_def:MAX:Maximum\:%8.2lf\n',
    "LINE1:loss_100#7fff00:100 byte packets",
    r'GPRINT:loss_100:LAST: Current\:%8.2lf',
    r'GPRINT:loss_100:AVERAGE:Average\:%8.2lf',
    r'GPRINT:loss_100:MAX:Maximum\:%8.2lf\n',
    "LINE1:loss_500#4b0082:500 byte packets",
    r'GPRINT:loss_500:LAST: Current\:%8.2lf',
    r'GPRINT:loss_500:AVERAGE:Average\:%8.2lf',
    r'GPRINT:loss_500:MAX:Maximum\:%8.2lf\n',
    "LINE1:loss_1000#ff0000:1000 byte packets",
    r'GPRINT:loss_1000:LAST:Current\:%8.2lf',
    r'GPRINT:loss_1000:AVERAGE:Average\:%8.2lf',
    r'GPRINT:loss_1000:MAX:Maximum\:%8.2lf\n',
    "LINE1:loss_1480#ffd700:1480 byte packets",
    r'GPRINT:loss_1480:LAST:Current\:%8.2lf',
    r'GPRINT:loss_1480:AVERAGE:Average\:%8.2lf',
    r'GPRINT:loss_1480:MAX:Maximum\:%8.2lf\n',
    '--alt-y-grid',
    '--units-exponent', '0',
    '--lower-limit', '0',
    '--upper-limit', '100'
  ]

class RRALinkQuality(RRAConfiguration):
  interval = 300
  sources = [
    DataSource(
      'lq',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'ilq',
      type = GaugeDST,
      heartbeat = interval * 2
    )
  ]
  graph = [
    "LINE1:lq#33ADFF:LQ",
    r'GPRINT:lq:LAST:  Current\:%8.2lf',
    r'GPRINT:lq:AVERAGE:Average\:%8.2lf',
    r'GPRINT:lq:MAX:Maximum\:%8.2lf\n',
    "LINE1:ilq#206C9F:ILQ",
    r'GPRINT:ilq:LAST: Current\:%8.2lf',
    r'GPRINT:ilq:AVERAGE:Average\:%8.2lf',
    r'GPRINT:ilq:MAX:Maximum\:%8.2lf\n',
    '--lower-limit', '0',
    '--upper-limit', '1'
  ]

class RRALoadAverage(RRAConfiguration):
  interval = 300
  sources = [
    DataSource(
      'la1min',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'la5min',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'la15min',
      type = GaugeDST,
      heartbeat = interval * 2
    )
  ]
  graph = [
    "LINE1:la1min#EACC00:1 Minute",
    r'GPRINT:la1min:LAST:  Current\:%8.2lf',
    r'GPRINT:la1min:AVERAGE:Average\:%8.2lf',
    r'GPRINT:la1min:MAX:Maximum\:%8.2lf\n',
    "LINE1:la5min#EA8F00:5 Minutes",
    r'GPRINT:la5min:LAST: Current\:%8.2lf',
    r'GPRINT:la5min:AVERAGE:Average\:%8.2lf',
    r'GPRINT:la5min:MAX:Maximum\:%8.2lf\n',
    "LINE1:la15min#FF0000:15 Minutes",
    r'GPRINT:la15min:LAST:Current\:%8.2lf',
    r'GPRINT:la15min:AVERAGE:Average\:%8.2lf',
    r'GPRINT:la15min:MAX:Maximum\:%8.2lf\n',
    '--lower-limit', '0',
    '--upper-limit', '1'
  ]

class RRANumProc(RRAConfiguration):
  interval = 300
  sources = [
    DataSource(
      'nproc',
      type = GaugeDST,
      heartbeat = interval * 2
    )
  ]
  graph = [
    "LINE2:nproc#00CB33:Number of Processes",
    r'GPRINT:nproc:LAST:  Current\:%8.2lf',
    r'GPRINT:nproc:AVERAGE:Average\:%8.2lf',
    r'GPRINT:nproc:MAX:Maximum\:%8.2lf\n',
    '--alt-y-grid',
    '--units-exponent', '0',
    '--lower-limit', '0'
  ]

class RRAMemUsage(RRAConfiguration):
  interval = 300
  sources = [
    DataSource(
      'memfree',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'buffers',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'cached',
      type = GaugeDST,
      heartbeat = interval * 2
    )
  ]
  graph = [
    "AREA:memfree#8F005C:Free Memory [KB]",
    r'GPRINT:memfree:LAST:  Current\:%8.2lf',
    r'GPRINT:memfree:AVERAGE:Average\:%8.2lf',
    r'GPRINT:memfree:MAX:Maximum\:%8.2lf\n',
    "AREA:buffers#FF5700:Buffers [KB]:STACK",
    r'GPRINT:buffers:LAST:      Current\:%8.2lf',
    r'GPRINT:buffers:AVERAGE:Average\:%8.2lf',
    r'GPRINT:buffers:MAX:Maximum\:%8.2lf\n',
    "AREA:cached#FFC73B:Cached [KB]:STACK",
    r'GPRINT:cached:LAST:       Current\:%8.2lf',
    r'GPRINT:cached:AVERAGE:Average\:%8.2lf',
    r'GPRINT:cached:MAX:Maximum\:%8.2lf\n',
    '--lower-limit', '0'
  ]

class RRAWifiCells(RRAConfiguration):
  interval = 300
  sources = [
    DataSource(
      'cells',
      type = GaugeDST,
      heartbeat = interval * 2
    )
  ]
  graph = [
    "LINE1:cells#00EE00:Cells",
    r'GPRINT:cells:LAST:  Current\:%8.2lf',
    r'GPRINT:cells:AVERAGE:Average\:%8.2lf',
    r'GPRINT:cells:MAX:Maximum\:%8.2lf\n',
    '--lower-limit', '0'
  ]

class RRAOlsrPeers(RRAConfiguration):
  interval = 300
  sources = [
    DataSource(
      'peers',
      type = GaugeDST,
      heartbeat = interval * 2
    )
  ]
  graph = [
    "LINE1:peers#EEBA00:Peers",
    r'GPRINT:peers:LAST:  Current\:%8.2lf',
    r'GPRINT:peers:AVERAGE:Average\:%8.2lf',
    r'GPRINT:peers:MAX:Maximum\:%8.2lf\n',
    '--lower-limit', '0'
  ]

class RRASolar(RRAConfiguration):
  db_model = StatsSolar
  interval = 1800
  sources = [
    DataSource(
      'batvoltage',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'solvoltage',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'charge',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'state',
      type = GaugeDST,
      heartbeat = interval * 2
    ),
    DataSource(
      'load',
      type = GaugeDST,
      heartbeat = interval * 2
    )
  ]
  graph = [
    # State definitions for background areas
    "CDEF:boost=state,0.8,1.2,LIMIT,state,EQ,INF,0,IF",
    "CDEF:equalize=state,1.8,2.2,LIMIT,state,EQ,INF,0,IF",
    "CDEF:absorption=state,2.8,3.2,LIMIT,state,EQ,INF,0,IF",
    "CDEF:float=state,3.8,4.2,LIMIT,state,EQ,INF,0,IF",
    "CDEF:inval=state,UN,INF,0,IF",
    
    # Graphical elements
    r"COMMENT:States (background color)\:",
    "AREA:boost#FEF6F6:Boost",
    "AREA:equalize#FEFCE7:Equalize",
    "AREA:absorption#E7EBFE:Absorption",
    r"AREA:float#EDFEED:Float\n",
    "AREA:inval#FFFFFF",

    "LINE2:batvoltage#6B7FD3:Battery [V]",
    r'GPRINT:batvoltage:LAST:    Current\:%8.2lf',
    r'GPRINT:batvoltage:AVERAGE:Average\:%8.2lf',
    r'GPRINT:batvoltage:MAX:Maximum\:%8.2lf\n',
    "LINE2:solvoltage#FF00A3:Solar panel [V]",
    r'GPRINT:solvoltage:LAST:Current\:%8.2lf',
    r'GPRINT:solvoltage:AVERAGE:Average\:%8.2lf',
    r'GPRINT:solvoltage:MAX:Maximum\:%8.2lf\n',
    "LINE2:charge#CBFE66:Charge [A]",
    r'GPRINT:charge:LAST:     Current\:%8.2lf',
    r'GPRINT:charge:AVERAGE:Average\:%8.2lf',
    r'GPRINT:charge:MAX:Maximum\:%8.2lf\n',
    "LINE2:load#BAE366:Load [A]",
    r'GPRINT:load:LAST:       Current\:%8.2lf',
    r'GPRINT:load:AVERAGE:Average\:%8.2lf',
    r'GPRINT:load:MAX:Maximum\:%8.2lf\n',
    '--alt-y-grid',
    '--units-exponent', '0',
    '--lower-limit', '0'
  ]

class RRA:
  """
  A wrapper class for managing round-robin archives via RRDTool.
  """
  @staticmethod
  def convert(conf, archive):
    """
    Converts 
    """
    try:
      os.stat(archive)
    except OSError:
      return
    
    # Dump the archive into XML form
    process = subprocess.Popen(
      ['/usr/bin/rrdtool', 'dump', archive],
      stdout = subprocess.PIPE,
      stderr = subprocess.PIPE
    )
    
    # Make any transformations needed
    xml = ElementTree.parse(process.stdout)
    wanted_source_names = [source.name for source in conf.sources]
    start_offset = 3
    changed = False
    
    # A simple marker to rescan sources as something has been modified
    class RescanSources(Exception): pass
    
    while True:
      data_sources = xml.findall('/ds')
      data_source_names = [source.findtext('./name').strip() for source in data_sources]
      
      try:
        for ds in data_source_names:
          if ds not in wanted_source_names:
            print "WARNING: Removal of sources currently not supported!"
            # If we remove something we must continue the loop
            # raise RescanSources
        
        for idx, ds in enumerate(wanted_source_names):
          if ds not in data_source_names:
            print "INFO: Adding data source '%s' to RRD '%s.'" % (ds, os.path.basename(archive))
            
            # Update header
            dse = ElementTree.Element("ds")
            ElementTree.SubElement(dse, "name").text = conf.sources[idx].name
            ElementTree.SubElement(dse, "type").text = conf.sources[idx].type
            ElementTree.SubElement(dse, "minimal_heartbeat").text = str(conf.sources[idx].heartbeat) 
            ElementTree.SubElement(dse, "min").text = "NaN"
            ElementTree.SubElement(dse, "max").text = "NaN"
            ElementTree.SubElement(dse, "last_ds").text = "UNKN"
            ElementTree.SubElement(dse, "value").text = "0.0000000000e+00"
            ElementTree.SubElement(dse, "unknown_sec").text = "0"
            xml.getroot().insert(start_offset + idx, dse)
            
            # Update all RRAs
            for rra in xml.findall('/rra'):
              # Update RRA header
              cdp = rra.find('./cdp_prep')
              dse = ElementTree.Element("ds")
              ElementTree.SubElement(dse, "primary_value").text = "NaN"
              ElementTree.SubElement(dse, "secondary_value").text = "NaN"
              ElementTree.SubElement(dse, "value").text = "NaN"
              ElementTree.SubElement(dse, "unknown_datapoints").text = "0"
              cdp.insert(idx, dse)
              
              # Update all RRA datapoints
              for row in rra.findall('./database/row'):
                v = ElementTree.Element("v")
                v.text = "NaN"
                row.insert(idx, v)
            
            changed = True
        
        break
      except RescanSources:
        pass
    
    # Add RRAs when they have changed (only addition is supported)
    for wanted_rra in conf.archives:
      for rra in xml.findall('/rra'):
        cf = rra.findtext('./cf').strip()
        steps = int(rra.findtext('./pdp_per_row').strip())
        rows = len(rra.findall('./database/row'))
        xff = float(rra.findtext('./params/xff').strip())
        
        match = all([
          cf == wanted_rra.cf,
          steps == wanted_rra.steps,
          rows == wanted_rra.rows,
          xff == wanted_rra.xff
        ])
        
        if match:
          break
      else:
        # Not found in existing RRAs, we need to add it
        print "INFO: Adding new RRA '%s' to '%s'." % (wanted_rra, os.path.basename(archive)) 
        changed =  True
        
        rra = ElementTree.SubElement(xml.getroot(), "rra")
        ElementTree.SubElement(rra, "cf").text = wanted_rra.cf
        ElementTree.SubElement(rra, "pdp_per_row").text = str(wanted_rra.steps)
        params = ElementTree.SubElement(rra, "params")
        ElementTree.SubElement(params, "xff").text = str(wanted_rra.xff)
        cdp_prep = ElementTree.SubElement(rra, "cdp_prep")
        
        for ds in conf.sources:
          dse = ElementTree.SubElement(cdp_prep, "ds")
          ElementTree.SubElement(dse, "primary_value").text = "NaN"
          ElementTree.SubElement(dse, "secondary_value").text = "NaN"
          ElementTree.SubElement(dse, "value").text = "NaN"
          ElementTree.SubElement(dse, "unknown_datapoints").text = "0"
        
        database = ElementTree.SubElement(rra, "database")
        for row in xrange(wanted_rra.rows):
          row = ElementTree.SubElement(database, "row")
          for v in xrange(len(conf.sources)):
            ElementTree.SubElement(row, "v").text = "NaN"
    
    if changed:
      try:
        os.rename(archive, "%s__bak" % archive)
        process = subprocess.Popen(
          ['/usr/bin/rrdtool', 'restore', '-', archive],
          stdin = subprocess.PIPE,
          stdout = subprocess.PIPE,
          stderr = subprocess.PIPE
        )
        
        # Fix all empty last_ds values otherwise rrdtool will complain on restore
        for last_ds in xml.findall('/ds/last_ds'):
          if not last_ds.text:
            last_ds.text = "UNKN"
        
        process.communicate(ElementTree.tostring(xml.getroot()))
        if process.returncode != 0:
          raise Exception
        
        try:
          os.unlink("%s__bak" % archive)
        except:
          pass
      except:
        os.rename("%s__bak" % archive, archive)
        raise
  
  @staticmethod
  def create(conf, archive):
    """
    Creates a new RRD archive.
    """
    options = [
      archive,
      '--start', str(int(time.time()))
    ]
    options = options + [str(x) for x in conf.sources]
    options = options + [str(x) for x in conf.archives]
    rrdtool.create(*options)

  @staticmethod
  def update(node, conf, archive, *values):
    """
    Updates an existing RRD archive or creates a new one if needed.
    """
    if not os.path.isfile(archive):
      RRA.create(conf, archive)
    
    rrdtool.update(
      archive,
      "N:" + ":".join([str(x) for x in values])
    )

    # Record data in database store if set
    now = time.time()
    if 'db_model' in conf.__dict__ and now - conf.last_update >= conf.interval:
      try:
        data = {}
        for i, x in enumerate(conf.sources):
          data[x.name] = values[i]
        
        m = conf.db_model(**data)
        m.node = node
        m.timestamp = datetime.now()
        m.save()
        conf.last_update = now
      except ValueError:
        pass
  
  @staticmethod
  def graph(conf, title, graph, archive, **kwargs):
    """
    Renders a graph from data points.
    """
    args = []
    for i, source in enumerate(conf.sources):
      args.append("DEF:%s=%s:%s:AVERAGE" % (source.name, archive, source.name))
      args.append("DEF:%s_cmin=%s:%s:MIN" % (source.name, archive, source.name))
      args.append("DEF:%s_cmax=%s:%s:MAX" % (source.name, archive, source.name))
    
    if kwargs.get('end_time') is None:
      end_time = int(time.time())
    else:
      end_time = int(kwargs.get('end_time'))

    if kwargs.get('dead') == True:
      args.append('--pango-markup')
      title = '%s <span foreground="red">[OUT OF DATE]</span>' % title

    args = args + conf.graph
    args.append('--font')
    args.append('DEFAULT:0:DejaVu Sans Mono')
    
    args.append('--disable-rrdtool-tag')

    for prefix, timespan in settings.GRAPH_TIMESPANS:
      options = [
        str(os.path.join(settings.GRAPH_DIR, "%s_%s" % (prefix, graph))),
        '--width', '500',
        '--height', '120',
        '--start', str(end_time - timespan),
        '--end', str(end_time - 180),
        '--title', title
      ]
      
      rrdtool.graph(*(options + args))

