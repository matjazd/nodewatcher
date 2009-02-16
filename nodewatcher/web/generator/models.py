from django.db import models
from django.contrib.auth.models import User
from ljwifi.nodes.models import Node, Subnet as SubnetAllocation
from ljwifi.generator.types import IfaceType

class Template(models.Model):
  """
  This class represents a preconfigured profile for image generation. This
  corresponds to options passed on to the image generator.
  """
  name = models.CharField(max_length = 50)
  description = models.CharField(max_length = 200)

  # Profile metadata for the generator
  openwrt_version = models.CharField(max_length = 20)
  arch = models.CharField(max_length = 20)
  iface_wifi = models.CharField(max_length = 10)
  iface_lan = models.CharField(max_length = 10)
  iface_wan = models.CharField(max_length = 10)
  driver = models.CharField(max_length = 20)
  channel = models.IntegerField()
  port_layout = models.CharField(max_length = 20)
  imagebuilder = models.CharField(max_length = 100)
  imagefile = models.CharField(max_length = 200)

  def __unicode__(self):
    """
    Return human readable template name.
    """
    return self.name

class IfaceTemplate(models.Model):
  """
  Interface templates.
  """
  template = models.ForeignKey(Template)
  type = models.IntegerField()
  ifname = models.CharField(max_length = 15)

  def __unicode__(self):
    """
    Returns human readable interface type name.
    """
    if self.type == IfaceType.LAN:
      return "LAN"
    elif self.type == IfaceType.WAN:
      return "WAN"
    elif self.type == IfaceType.WiFi:
      return "WiFi"
    else:
      return "Unknown"

class Profile(models.Model):
  """
  This class represents an actual user's configuration profile.
  """
  template = models.ForeignKey(Template)
  node = models.OneToOneField(Node)

  # Specialization information
  root_pass = models.CharField(max_length = 20)
  use_vpn = models.BooleanField()
  use_captive_portal = models.BooleanField()
