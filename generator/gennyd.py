#!/usr/bin/python
#
# nodewatcher firmware generator daemon
#
# Copyright (C) 2009 by Jernej Kos <kostko@unimatrix-one.org>
#

# First parse options (this must be done here since they contain import paths
# that must be parsed before Django models can be imported)
import sys, os, re
from optparse import OptionParser

print "============================================================================"
print "                   nodewatcher firmware generator daemon                   "
print "============================================================================"

parser = OptionParser()
parser.add_option('--path', dest = 'path', help = 'Path that contains nodewatcher "frontend" Python module')
parser.add_option('--settings', dest = 'settings', help = 'Django settings to use')
parser.add_option('--destination', dest = 'destination', help = 'Firmware destination directory')
options, args = parser.parse_args()

if not options.path:
  print "ERROR: Path specification is required!\n"
  parser.print_help()
  exit(1)
elif not options.settings:
  print "ERROR: Settings specification is required!\n"
  parser.print_help()
  exit(1)
elif not options.destination:
  print "ERROR: Firmware destination directory is required!\n"
  parser.print_help()
  exit(1)

# Setup import paths, since we are using Django models
sys.path.append(os.path.abspath(options.path))
os.environ['DJANGO_SETTINGS_MODULE'] = options.settings

# Django stuff
from django.core.mail import send_mail
from django.utils.translation import ugettext as _
from django.template import loader, Context
from django.conf import settings

# Other stuff
from beanstalk import serverconn
from beanstalk import job
from config_generator import OpenWrtConfig, portLayouts
import logging
import hashlib
from traceback import format_exc
import pwd
from zipfile import ZipFile, ZIP_DEFLATED
from base64 import urlsafe_b64encode
from glob import glob

WORKDIR = os.getcwd()
DESTINATION = options.destination
IMAGEBUILDERS = (
  "imagebuilder.atheros",
  "imagebuilder.brcm24",
  "imagebuilder.broadcom",
  "imagebuilder.ar71xx",
  "imagebuilder.nextgen.ar71xx",
  "imagebuilder.nextgen.atheros",
)

def no_unicodes(x):
  """
  Converts all unicodes to str instances.
  """
  for k, v in x.iteritems():
    if isinstance(v, unicode):
      x[k] = v.encode('utf8')

  return x

def generate_image(d):
  """
  Generates an image accoording to given configuration.
  """
  logging.debug(repr(d))

  if d['imagebuilder'] not in IMAGEBUILDERS:
    raise Exception("Invalid imagebuilder specified!")
  
  x = OpenWrtConfig()
  x.setUUID(d['uuid'])
  x.setOpenwrtVersion(d['openwrt_ver'])
  x.setArch(d['arch'])
  x.setPortLayout(d['port_layout'])
  x.setWifiIface(d['iface_wifi'], d['driver'], d['channel'])
  x.setWifiAnt(d['rx_ant'], d['tx_ant'])
  x.setLanIface(d['iface_lan'])
  x.setNodeType("adhoc")
  x.setPassword(d['root_pass'])
  x.setHostname(d['hostname'])
  x.setIp(d['ip'])
  x.setSSID(d['ssid'])
  
  # Add WAN interface and all subnets
  if d['wan_dhcp']:
    x.addInterface("wan", d['iface_wan'], init = True)
  else:
    x.addInterface("wan", d['iface_wan'], d['wan_ip'], d['wan_cidr'], d['wan_gw'], init = True)

  for subnet in d['subnets']:
    x.addSubnet(str(subnet['iface']), str(subnet['network']), subnet['cidr'], subnet['dhcp'], True)

  x.setCaptivePortal(d['captive_portal'])
  if d['vpn']:
    x.setVpn(d['vpn_username'], d['vpn_password'], d['vpn_mac'], d['vpn_limit'])
  
  if d['lan_wifi_bridge']:
    x.enableLanWifiBridge()
  
  if d['lan_wan_switch']:
    x.switchWanToLan()
  
  # Add optional packages
  for package in d['opt_pkg']:
    x.addPackage(package)
  
  # Cleanup stuff from previous builds
  os.chdir(WORKDIR)
  os.system("rm -rf build/files/*")
  os.system("rm -rf build/%s/bin/*" % d['imagebuilder'])
  os.mkdir("build/files/etc")
  x.generate("build/files/etc")

  if d['only_config']:
    # Just pack configuration and send it
    prefix = hashlib.md5(os.urandom(32)).hexdigest()[0:16]
    tempfile = os.path.join(DESTINATION, prefix + "-config.zip")
    zip = ZipFile(tempfile, 'w', ZIP_DEFLATED)
    os.chdir('build/files')
    for root, dirs, files in os.walk("etc"):
      for file in files:
        zip.write(os.path.join(root, file))
    zip.close()
    
    # Generate checksum
    f = open(tempfile, 'r')
    checksum = hashlib.md5(f.read())
    f.close()
    
    # We can take just first 22 characters as checksums are fixed size and we can reconstruct it
    filechecksum = urlsafe_b64encode(checksum.digest())[:22]
    checksum = checksum.hexdigest()
    
    result = "%s-%s-config-%s.zip" % (d['hostname'], d['router_name'], filechecksum)
    destination = os.path.join(DESTINATION, result)
    os.rename(tempfile, destination)

    # Send an e-mail
    t = loader.get_template('generator/email_config.txt')
    c = Context({
      'hostname'  : d['hostname'],
      'ip'        : d['ip'],
      'username'  : d['vpn_username'],
      'config'    : result,
      'checksum'  : checksum,
      'network'   : { 'name'        : settings.NETWORK_NAME,
                      'home'        : settings.NETWORK_HOME,
                      'contact'     : settings.NETWORK_CONTACT,
                      'description' : getattr(settings, 'NETWORK_DESCRIPTION', None)
                    },
      'images_bindist_url' : getattr(settings, 'IMAGES_BINDIST_URL', None)
    })

    send_mail(
      settings.EMAIL_SUBJECT_PREFIX + (_("Configuration for %s/%s") % (d['hostname'], d['ip'])),
      t.render(c),
      settings.EMAIL_IMAGE_GENERATOR_SENDER,
      [d['email']],
      fail_silently = False
    )
  else:
    # Generate full image
    x.build("build/%s" % d['imagebuilder'])
    
    # Read image version
    try:
      f = open(glob('%s/build/%s/build_dir/target-*/root-*/etc/version' % (WORKDIR, d['imagebuilder']))[0], 'r')
      version = f.read().strip()
      version = re.sub(r'\W+', '_', version)
      version = re.sub(r'_+', '_', version)
      f.close()
    except:
      version = 'unknown'

    # Get resulting image
    files = []
    for file, type in d['imagefiles']:
      file = str(file)
      source = "%s/build/%s/bin/%s" % (WORKDIR, d['imagebuilder'], file)

      f = open(source, 'r')
      checksum = hashlib.md5(f.read())
      f.close()
      
      # We can take just first 22 characters as checksums are fixed size and we can reconstruct it
      filechecksum = urlsafe_b64encode(checksum.digest())[:22]
      checksum = checksum.hexdigest()
      
      ext = os.path.splitext(file)[1]
      router_name = d['router_name'].replace('-', '')

      result = "%s-%s-%s%s-%s%s" % (d['hostname'], router_name, version, ("-%s" % type if type else "-all"), filechecksum, ext)      
      destination = os.path.join(DESTINATION, result)
      os.rename(source, destination)
      files.append({ 'name' : result, 'checksum' : checksum })

    # Send an e-mail
    t = loader.get_template('generator/email.txt')
    c = Context({
      'hostname'  : d['hostname'],
      'ip'        : d['ip'],
      'username'  : d['vpn_username'],
      'files'     : files,
      'network'   : { 'name'        : settings.NETWORK_NAME,
                      'home'        : settings.NETWORK_HOME,
                      'contact'     : settings.NETWORK_CONTACT,
                      'description' : getattr(settings, 'NETWORK_DESCRIPTION', None)
                    },
      'images_bindist_url' : getattr(settings, 'IMAGES_BINDIST_URL', None)
    })
    
    send_mail(
      settings.EMAIL_SUBJECT_PREFIX + (_("Router images for %s/%s") % (d['hostname'], d['ip'])),
      t.render(c),
      settings.EMAIL_IMAGE_GENERATOR_SENDER,
      [d['email']],
      fail_silently = False
    )

# Configure logger
logging.basicConfig(level = logging.DEBUG,
                    format = '%(asctime)s %(levelname)-8s %(message)s',
                    datefmt = '%a, %d %b %Y %H:%M:%S',
                    filename = os.path.join(WORKDIR, 'generator.log'),
                    filemode = 'a')

if settings.IMAGE_GENERATOR_USER:
  # Change ownership for the build directory
  os.system("chown -R {0}:{0} build".format(settings.IMAGE_GENERATOR_USER))

  # Drop user privileges
  try:
    info = pwd.getpwnam(settings.IMAGE_GENERATOR_USER)
    os.setgid(info.pw_gid)
    os.setuid(info.pw_uid)
  except:
    print "ERROR: Unable to change to '{0}' user!".format(settings.IMAGE_GENERATOR_USER)
    exit(1)

logging.info("nodewatcher firmware generator daemon v0.1 starting up...")

c = serverconn.ServerConn("127.0.0.1", 11300)
c.job = job.Job
c.use("generator")

logging.info("Connected to local beanstalkd instance.")

try:
  while True:
    j = c.reserve()
    j.Finish()

    try:
      logging.info("Generating an image for '%s/%s'..." % (j.data['vpn_username'], j.data['ip']))
      generate_image(no_unicodes(j.data))
      logging.info("Image generation successful!")
    except:
      logging.error(format_exc())
      logging.warning("Image generation has failed!")

      # Send an e-mail
      d = no_unicodes(j.data)
      t = loader.get_template('generator/email_failed.txt')
      ctx = Context({
        'hostname'  : d['hostname'],
        'ip'        : d['ip'],
        'username'  : d['vpn_username'],
        'network'   : { 'name'        : settings.NETWORK_NAME,
                        'home'        : settings.NETWORK_HOME,
                        'contact'     : settings.NETWORK_CONTACT,
                        'description' : getattr(settings, 'NETWORK_DESCRIPTION', None)
                      },
        'images_bindist_url' : getattr(settings, 'IMAGES_BINDIST_URL', None)
      })

      send_mail(
        settings.EMAIL_SUBJECT_PREFIX + (_("Image generation failed for %s/%s") % (d['hostname'], d['ip'])),
        t.render(ctx),
        settings.EMAIL_IMAGE_GENERATOR_SENDER,
        [d['email']],
        fail_silently = False
      )
except KeyboardInterrupt:
  logging.info("Terminating due to user abort.")
except:
  logging.error(format_exc())
  logging.warning("We are going down!")

