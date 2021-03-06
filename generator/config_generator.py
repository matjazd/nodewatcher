#!/usr/bin/python
#
# nodewatcher configuration generator
#
# Copyright (C) 2008 Jernej Kos <kostko@unimatrix-one.org>
#

import os
import ipcalc
import crypt
from datetime import datetime
from random import shuffle

# A list of driver dependent packages
driverPackages = {
  'broadcom' : ['kmod-brcm-wl', 'kmod-wlcompat', 'wlc'],
  'mac80211' : ['kmod-mac80211', 'kmod-b43'],
  'atheros'  : ['kmod-madwifi']
}

# A list of platform dependent packages
platformPackages = {
  'rb433'    : ['kmod-switch']
}

# A list of per-platform switch identifiers (when not set, eth0 is used)
switchIds = {
  'rb433'    : '0'
}

# A list of virtual interface names for some drivers
wifiVirtuals = {
  'atheros'  : 'wifi0'
}

# A list of default antenna mappings for some configurations
wifiAntennas = {
                  # Antenna   Force always or only on default
  'fonera'      : (1,         True),
  'fonera+'     : (1,         True),
  'whr-hp-g54'  : (1,         True),
  'wrt54gl'     : (0,         False),
  'wrt54gs'     : (0,         False),
  'wl-500gp'    : (0,         True),
  'wl-500gp-v1' : (0,         True),
  'wl-500gd'    : (0,         True),
  'rb433'       : (1,         False),
  'rb411'       : (1,         False),
}

# A list of port layouts (do not forget to add new ones to a list of valid
# layouts to build_image.py if you add them here)
portLayouts = {
                #  LAN           WAN
  'wrt54gl'     : ('0 1 2 3 5*', '4 5'),
  'wrt54gs'     : ('1 2 3 4 5*', '0 5'),
  'whr-hp-g54'  : ('1 2 3 4 5*', '0 5'),
  'wl-500gp'    : ('0 1 2 3 5*', '4 5'),
  'wl-500gp-v1' : ('1 2 3 4 5*', '0 5'),
  'wl-500gd'    : ('1 2 3 4 5*', '0 5'),
  'fonera'      : None,
  'fonera+'     : True,
  'rb433'       : True, # ('1 5*',       '2 5')
  'rb411'       : None,

  'tp-wr703n' : None,
  'tp-mr3020' : None,
}

# Optional packages that should be removed when configuring a router-only node
clientOnlyPackages = [
  "splash-ljubljana",
  "splash-maribor",
  "splash-slovenija",
]

class PrimarySubnetTooSmall(Exception):
  pass

class NodeConfig(object):
  """
  A class representing mesh router configuration.
  """
  uuid = ""
  ssid = "open.wlan-lj.net"
  bssid = "02:CA:FF:EE:BA:BE"
  arch = "mipsel"
  openwrtVersion = "old"
  wifiVirtualIface = None
  wifiIface = "wl0"
  wifiDriver = "broadcom"
  wifiChannel = 8
  wifiTxAnt = 1
  wifiRxAnt = 1
  wifiAntDiv = 0
  portLayout = "wrt54gl"
  password = None
  hostname = None
  ip = None
  subnets = None
  vpn = None
  vpnServer = (("46.54.226.43", 9999), ("91.185.203.246", 9999), ("46.54.226.49", 9999))
  tdServer = [("46.54.226.43", [8942, 53, 123]), ("91.185.203.240", [8942, 53, 123])]
  dns = ("10.254.0.1", "10.254.0.2")
  ntp = ("10.254.0.1", "10.254.0.2")
  interfaces = None
  services = None
  captivePortal = False
  packages = None
  wan = None
  nodeType = "adhoc"
  lanIface = "eth0.0"
  lanWifiBridge = False
  lanWifiBridgeIface = "br-mesh"
  primarySubnet = None
  usedOlsrIps = 1
  hasClientSubnet = False
  
  def __init__(self):
    """
    Class constructor.
    """
    self.subnets = []
    self.interfaces = []
    self.services = []
    self.packages = []
  
  def setUUID(self, uuid):
    """
    Sets this node's unique identifier.
    """
    self.uuid = uuid
  
  def setHostname(self, hostname):
    """
    Sets this node's hostname.
    """
    self.hostname = hostname

  def setIp(self, ip):
    """
    Sets this node's IP.
    """
    self.ip = ip

  def setPassword(self, password):
    """
    Sets the root password.
    """
    self.password = password

  def setWifiIface(self, iface, driver, channel = 8):
    """
    Sets the wireless interface name and driver.
    """
    self.wifiIface = iface
    self.wifiDriver = driver
    self.wifiChannel = channel
    
    if driver in wifiVirtuals:
      self.wifiVirtualIface = wifiVirtuals[driver]
    else:
      self.wifiVirtualIface = iface
  
  def setWifiAnt(self, rx, tx):
    """
    Sets the wireless receive/transmit antenna.
    """
    self.wifiRxAnt = rx
    self.wifiTxAnt = tx
    
    if self.wifiRxAnt == self.wifiTxAnt == 3:
      self.wifiAntDiv = 1
    
    if self.portLayout in wifiAntennas:
      ant, force = wifiAntennas[self.portLayout]
      
      if force or rx == tx == 4:
        self.wifiRxAnt = self.wifiTxAnt = ant
  
  def setLanIface(self, iface):
    """
    Sets the LAN interface name.
    """
    self.lanIface = iface
  
  def setOpenwrtVersion(self, version):
    """
    Sets the OpenWRT version.
    """
    self.openwrtVersion = version
  
  def setArch(self, arch):
    """
    Sets the CPU architecture.
    """
    self.arch = arch
  
  def setPortLayout(self, layout):
    """
    Sets the port layout.
    """
    self.portLayout = layout
  
  def setNodeType(self, nodeType):
    """
    Sets the node type.
    """
    self.nodeType = nodeType

  def setSSID(self, ssid):
    """
    Sets the SSID.
    """
    self.ssid = ssid
  
  def addService(self, priority, name):
    """
    Adds a service to be executed on bootup.
    
    @param priority: Service priority code
    @param name: Service name
    """
    self.services.append({ 'priority' : priority,
                           'name'     : name })
  
  def switchWanToLan(self):
    """
    Changes interface configurations so WAN interfaces takes the role
    of the LAN interface. This will only happen when no VLAN tagging
    is possible (there is no port layout configured for that specified
    configuration).
    
    Also VPN must not be configured, otherwise this method will do
    nothing at all.
    """
    if portLayouts[self.portLayout] or self.vpn or not self.hasInterface('wan'):
      return
    
    wan = self.getInterface('wan')
    self.lanIface = wan['name']
    self.removeInterface('wan')
  
  def enableLanWifiBridge(self):
    """
    Enables LAN<->WiFi bridge.
    """
    # Ignore if  there are any subnets configured for LAN interface
    for subnet in self.subnets:
      if subnet['interface'] == self.lanIface:
        return
    
    self.lanWifiBridge = True
  
  def removeInterface(self, id):
    """
    Removes an interface.
    
    @param id: Interface configuration identifier
    """
    for interface in self.interfaces[:]:
      if interface['id'] == id:
        self.interfaces.remove(interface)
        return
  
  def addInterface(self, id, name, ip = None, cidr = None, gateway = None, init = False, olsr = False, type = None):
    """
    Adds a non-standard interface to this node.
    
    @param id: Interface configuration identifier
    @param name: Interface name
    @param ip: IP address or None for DHCP
    @param cidr: CIDR or None in case of DHCP
    @param gateway: Gateway or None in case of DHCP
    @param init: True if the iface should be initialized upon boot
    @param olsr: Should OLSR run on this interface
    @param type: Optional interface type
    """
    netmask = None
    
    if ip:
      if not cidr:
        raise Exception('Static IP configuration requires CIDR parameter!')
      
      network = ipcalc.Network("%s/%s" % (ip, cidr))
      netmask = str(network.netmask())
      
      if gateway and gateway not in ipcalc.Network("%s/%s" % (str(network.network()), cidr)):
        raise Exception('Gateway must be in the same network as the given interface!')
    
    self.interfaces.insert(0, { 'name'     : name,
                                'ip'       : ip,
                                'cidr'     : cidr,
                                'mask'     : netmask,
                                'gateway'  : gateway,
                                'id'       : id,
                                'init'     : init,
                                'olsr'     : olsr,
                                'type'     : type })
  
  def hasInterface(self, id):
    """
    Returns true if the given interface exists.
    """
    for interface in self.interfaces:
      if interface['id'] == id:
        return True
    
    return False
  
  def getInterface(self, id):
    """
    Returns the interface with the given id.
    """
    for interface in self.interfaces:
      if interface['id'] == id:
        return interface
    
    return None
  
  def getInterfaceByName(self, name):
    """
    Returns the interface with the given name.
    """
    for interface in self.interfaces:
      if interface['name'] == name:
        return interface
    
    return None
  
  def addSubnet(self, interface, subnet, cidr, dhcp = False, olsr = True):
    """
    Adds a subnet to this node.
    
    @param interface: Interface name
    @param subnet: Subnet
    @param cidr: CIDR
    @param dhcp: Should this subnet be announced via DHCP
    @param olsr: Should this subnet be announced via OLSR
    """
    if dhcp and cidr <= 28 and interface == self.wifiIface:
      self.hasClientSubnet = True
    
    network = ipcalc.Network("%s/%s" % (subnet, cidr))
    subnet = { 'interface'   : interface,
               'subnet'      : subnet,
               'cidr'        : cidr,
               'mask'        : str(network.netmask()),
               'firstIp'     : str(network.host_first()),
               'dhcp'        : dhcp,
               'olsr'        : olsr }
    
    self.subnets.append(subnet)
    
    if ipcalc.IP(self.ip) in network:
      self.primarySubnet = subnet

  def allocateIpForOlsr(self):
    """
    Allocates an IP address from the primary subnet for use by OLSR
    as interface identifier.
    """
    network = ipcalc.Network("%s/%s" % (self.primarySubnet['subnet'], self.primarySubnet['cidr']))
    ip = str(ipcalc.IP(long(network.network()) + self.usedOlsrIps + 1))
    
    # Sanity check so we don't overstep our bounds
    if ipcalc.IP(ip) not in network:
      raise PrimarySubnetTooSmall
    
    self.usedOlsrIps += 1
    return ip

  def setVpn(self, username, password, mac = None, limit = None):
    """
    Sets VPN parameters.
    
    @param username: Assigned username
    @param password: Assigned password
    @param mac: Assigned MAC address
    @param limit: Egress traffic limit (in kbit/s)
    """
    if not self.hasInterface('wan'):
      raise Exception('VPN requires WAN access configuration!')
    
    if self.primarySubnet['cidr'] > 30:
      # Prevent VPN from being enabled when primary subnet is too small
      # for allocation of additional IP addresses (less than /30)
      return
    
    self.addInterface('vpn', 'tap0', olsr = True)
    self.vpn = { 'username' : username,
                 'password' : password,
                 'mac'      : mac,
                 'limit'    : limit,
                 'ip'       : self.allocateIpForOlsr() }
  
  def setCaptivePortal(self, value):
    """
    Toggles the use of a captive portal for internet connections.
    """
    if value and self.primarySubnet['cidr'] > 28:
      # Prevent captive portal from being enabled when primary subnet is too
      # small for any clients (less than /28)
      self.captivePortal = False
    else:
      self.captivePortal = value

  def addPackage(self, *args):
    """
    Adds packages to be installed.
    """
    for package in args:
      if package not in self.packages:
        self.packages.append(package)
  
  def generate(self, directory):
    """
    Generates the required configuration files.
    
    @param directory: Path to etc directory
    """
    raise Exception("Missing 'generate' method implementation!")
  
  def build(self, destination):
    """
    Builds the image.
    
    @param destination: Path to image build root
    """
    raise Exception("Missing 'setupPackages' method implementation!")

class OpenWrtConfig(NodeConfig):
  def __init__(self):
    """
    Class constructor.
    """
    NodeConfig.__init__(self)
    
    # Add some basic services
    self.addService('S46', 'misc')
    self.addService('K46', 'misc')
  
  def generate(self, directory):
    """
    Generates the required configuration files for OpenWRT.
    """
    self.base = directory
    
    # XXX hardcoded new tplink for openwrt trunk; this is a quick hack for
    #     supporting tp-link wr741nd devices that we need
    if self.openwrtVersion == 'nextgen':
      # Setup passwords
      self.__generatePasswords()

      # Setup authorized public keys
      keyPath = os.path.join(directory, "dropbear")
      os.mkdir(keyPath)
      self.__copyTemplate("keys/authorized_keys", os.path.join(keyPath, "authorized_keys"))
      
      # Write UUID to /etc/uuid
      f = open(os.path.join(directory, 'uuid'), 'w')
      f.write(self.uuid)
      f.close()
      
      # Create the 'config' directory
      configPath = os.path.join(directory, 'config')
      os.mkdir(configPath)
      
      # General configuration
      f = open(os.path.join(configPath, "system"), 'w')
      self.__generateSystemConfig(f)
      
      # Network configuration
      f = open(os.path.join(configPath, "network"), 'w')
      f.write("""
config interface loopback
        option ifname   lo
        option proto    static
        option ipaddr   127.0.0.1
        option netmask  255.0.0.0

config interface mesh
        option proto    static
        option ipaddr   {mesh_ip}
        option netmask  255.255.0.0

config interface clients
        option ifname   eth0
        option type     bridge
        option proto    static
        option ipaddr   {mesh_ip}
        option netmask  {clients_mask}

""".format(
        mesh_ip = self.ip,
        clients_mask = self.subnets[0]['mask'],
        vpn_ip = self.vpn['ip']
      ))
      
      if self.portLayout not in portLayouts or portLayouts.get(self.portLayout) is not None:
        f.write("config switch eth0\n")
        f.write("        option enable_vlan      1\n")
        f.write("\n")
        f.write("config switch_vlan\n")
        f.write("        option device   eth0\n")
        f.write("        option vlan     1\n")
        f.write('        option ports    "0 1 2 3 4"\n')
        f.write("\n")
      
      # Configure tunneldigger interfaces
      ips = [self.vpn['ip']] + [self.allocateIpForOlsr() for _ in xrange(len(self.tdServer) - 1)]
      for idx, ip in zip(xrange(len(self.tdServer)), ips):
        f.write("config interface digger%d\n" % idx)
        f.write("        option ifname   digger%d\n" % idx)
        f.write("        option proto    static\n")
        f.write("        option ipaddr   %s\n" % ip)
        f.write("        option netmask  255.255.0.0\n")
        f.write("\n")
      
      # Configure WAN interface
      wan_interface = {}
      for iface in self.interfaces:
        if iface['id'] == "wan":
          wan_interface = iface
          break
      
      if wan_interface.get('ip', None):
        f.write("config interface wan\n")
        f.write("        option ifname   eth1\n")
        f.write("        option proto    static\n")
        f.write("        option ipaddr   %s\n" % wan_interface['ip'])
        f.write("        option netmask  %s\n" % wan_interface['mask'])
        f.write("        option gateway  %s\n" % wan_interface['gateway'])
      else:
        f.write("config interface wan\n")
        f.write("        option ifname   eth1\n")
        f.write("        option proto    dhcp\n")
      
      f.write("\n")
      f.close()
      
      # Policy routing configuration
      f = open(os.path.join(configPath, "routing"), 'w')
      f.write("""
config table mesh
        option id       20
""")

      for server, ports in self.tdServer:
        f.write("""
config policy
        option dest_ip  '{0}'
        option table    'main'
        option priority 999
""".format(server))
      
      f.write("""
config policy
        option dest_ip  '{subnet}/{cidr}'
        option table    'main'
        option priority 999

config policy
        option device   'eth1'
        option table    'main'
        option priority 999

config policy
        option table    'mesh'
        option priority 1000
""".format(
        subnet = self.subnets[0]['subnet'],
        cidr = self.subnets[0]['cidr']
      ))
      
      f.close()
      
      # Wireless configuration
      # WiFi hack script
      inituci_path = os.path.join(directory, "init.d", "inituci")
      os.mkdir(os.path.join(directory, "init.d"))
      f = open(inituci_path, 'w')
      f.write("""#!/bin/sh /etc/rc.common
START=39

start() {{
      uci delete wireless.radio0.disabled
      uci set wireless.radio0.channel=8
      
      uci set wireless.@wifi-iface[0].device=radio0
      uci set wireless.@wifi-iface[0].network=clients
      uci set wireless.@wifi-iface[0].mode=ap
      uci set wireless.@wifi-iface[0].ssid={ssid}
      uci set wireless.@wifi-iface[0].encryption=none
      
      uci add wireless wifi-iface
      uci set wireless.@wifi-iface[1].device=radio0
      uci set wireless.@wifi-iface[1].network=mesh
      uci set wireless.@wifi-iface[1].mode=adhoc
      uci set wireless.@wifi-iface[1].ssid={mesh_ssid}
      uci set wireless.@wifi-iface[1].bssid=02:CA:FF:EE:BA:BE
      uci set wireless.@wifi-iface[1].encryption=none
      
      uci commit
      /etc/init.d/inituci disable
      /etc/init.d/firewall disable
      /etc/init.d/firewall stop
      /sbin/wifi up
}}
""".format(ssid = self.ssid, mesh_ssid = self.ssid.replace('open', 'mesh')))
      f.close()
      os.chmod(inituci_path, 0755)
 
      # OLSRd configuration
      f = open(os.path.join(configPath, "olsrd"), 'w')
      f.write("""
config olsrd
        option config_file      '/etc/olsrd.conf'
""")
      f.close()
      
      f = open(os.path.join(directory, 'olsrd.conf'), 'w')
      f.write("""
Hna4
{{
  {hna_subnet}  {hna_mask}
}}

AllowNoInt yes
UseHysteresis no
LinkQualityFishEye 0
Willingness 3
LinkQualityLevel 2
LinkQualityAging 0.1
LinkQualityAlgorithm "etx_ff"
FIBMetric "flat"
Pollrate 0.025
TcRedundancy 2
MprCoverage 3
NatThreshold 0.75
SmartGateway no
MainIp {router_id}
SrcIpRoutes yes
RtTable 20

Interface "wlan0-1" "wlan1" "br-clients" {diggers}
{{
  IPv4Multicast 255.255.255.255
  HelloInterval 5.0
  HelloValidityTime 40.0
  TcInterval 7.0
  TcValidityTime 161.0
  MidInterval 18.0
  MidValidityTime 324.0
  HnaInterval 18.0
  HnaValidityTime 324.0
}}
""".format(
        router_id = self.ip,
        hna_subnet = self.subnets[0]['subnet'],
        hna_mask = self.subnets[0]['mask'],
        diggers = " ".join(['"digger%d"' % x for x in xrange(len(self.tdServer))])
      ))
      f.close()
      
      # DHCP configuration
      network = ipcalc.Network("%s/%s" % (self.subnets[0]['subnet'], self.subnets[0]['cidr']))
      start_ip = str(ipcalc.IP(long(network.network()) + 4)).split(".")[-1]
      end_ip = str(network.host_last()).split(".")[-1]
      
      f = open(os.path.join(configPath, "dhcp"), 'w')
      f.write("""
config dnsmasq
        option domainneeded     1
        option boguspriv        1
        option localise_queries 1
        option rebind_protection 0
        option nonegcache       1
        option noresolv         1
        option authoritative    1
        option leasefile        '/tmp/dhcp.leases'
        list server             '10.254.0.1'
        list server             '10.254.0.2'

config dhcp clients
        option interface        clients
        option start    {start_ip}
        option limit    {end_ip}
        option leasetime        30m
        option force    1
""".format(
        start_ip = start_ip,
        end_ip = end_ip
      ))
      f.close()
      
      # Tunneldigger VPN configuration
      if self.vpn:
        f = open(os.path.join(configPath, "tunneldigger"), 'w')
        iface = 0
        
        for server, ports in self.tdServer:
          ports = "\n".join(["        list port               %d" % x for x in ports])
          f.write("""
config broker
        option address          '{broker_ip}'
{broker_ports}
        option uuid             '{uuid}'
        option interface        'digger{iface}'

""".format(broker_ip = server, broker_ports = ports, uuid = self.uuid, iface = iface))
          iface += 1
        
        f.close()
      
      # uhttpd configuration
      f = open(os.path.join(configPath, "uhttpd"), 'w')
      f.write("""
config uhttpd main
        list listen_http        {router_ip}:80
        option home             '/www'
        option cgi_prefix       '/cgi-bin'

        option script_timeout   60
        option network_timeout  30
        option tcp_keepalive    1
""".format(
        router_ip = self.ip
      ))
      f.close()
      return
   
    os.mkdir(os.path.join(directory, 'init.d'))
    
    # Generate iproute2 rt_tables (hardcoded for now)
    os.mkdir(os.path.join(directory, 'iproute2'))
    f = open(os.path.join(directory, 'iproute2', 'rt_tables'), 'w')
    f.write('8\twan\n')
    f.close()
    
    # Configure HTTP server
    self.__copyServiceTemplate('general/httpd.init', 'httpd')
    
    # Prevent the date from going to far into the past on reboot
    miscScriptPath = os.path.join(directory, 'init.d', 'misc')
    f = open(miscScriptPath, 'w')
    self.__generateMiscScript(f)
    os.chmod(miscScriptPath, 0755)

    # Setup passwords
    self.__generatePasswords()
    
    # Write UUID to /etc/uuid
    f = open(os.path.join(directory, 'uuid'), 'w')
    f.write(self.uuid)
    f.close()

    # Create the 'config' directory
    configPath = os.path.join(directory, 'config')
    os.mkdir(configPath)
    
    f = open(os.path.join(configPath, "system"), 'w')
    self.__generateSystemConfig(f)
    
    f = open(os.path.join(configPath, "network"), 'w')
    self.__generateNetworkConfig(f)
    
    f = open(os.path.join(configPath, "wireless"), 'w')
    self.__generateWirelessConfig(f)
    
    f = open(os.path.join(configPath, "ntpclient"), 'w')
    self.__generateNtpClientConfig(f)
    
    # 'dhcp' configuration must be empty, so the init script will use
    # dnsmasq.conf in /etc
    f = open(os.path.join(configPath, "dhcp"), 'w')
    f.close()
    
    # Create the 'olsrd.conf'
    f = open(os.path.join(directory, 'olsrd.conf'), 'w')
    self.__generateOlsrdConfig(f)
    
    # Create the VPN configuration
    if self.vpn:
      self.__generateVpnConfig(os.path.join(directory, 'openvpn'))
    
    # Create the dnsmasq configuration
    f = open(os.path.join(directory, 'dnsmasq.conf'), 'w')
    self.__generateDnsmasqConfig(f)
    
    # Create the captive portal configuration
    if self.captivePortal and self.hasClientSubnet:
      self.__generateCaptivePortalConfig(os.path.join(directory, 'nodogsplash'))
    
    # Setup service symlinks
    if self.openwrtVersion == "old":
      self.__generateServices(os.path.join(directory, 'rc.d'))
  
  def build(self, path):
    """
    Build the image using ImageBuilder.
    """
    if self.openwrtVersion == 'hardcoded-tpl-trunk':
      raise Exception("Cannot generate image for this version!")
    elif self.openwrtVersion == 'nextgen':
      profile_map = {
        "tp-wr741nd" : "TLWR741",
        "tp-wr842nd" : "TLWR842",
        "tp-wr743nd" : "TLWR743",
        "tp-wr841nd" : "TLWR841",
        "tp-wr941nd" : "TLWR941",
        "tp-wr1041nd" : "TLWR1041",
        "tp-wr1043nd" : "TLWR1043",
        "tp-wr703n" : "TLWR703",
        "tp-mr3020" : "TLMR3020",
        
        "fonera"     : "",
      }

      pkg_map = {
        "tp-wr842nd" : ["kmod-usb-serial", "kmod-usb-acm"],
        "tp-wr1043nd" : ["kmod-usb-serial", "kmod-usb-acm"],
        "tp-wr703n" : ["kmod-usb-serial", "kmod-usb-acm"],
        "tp-mr3020" : ["kmod-usb-serial", "kmod-usb-acm"],
      }
      pkgs = " ".join(pkg_map.get(self.portLayout, []))

      buildString = 'make image FILES="../files" PROFILE="%s" PACKAGES="policy-routing olsrd uhttpd tc nodewatcher-core nodewatcher-clients ntpclient hostapd -ppp -ppp-mod-pppoe -wpad-mini kmod-l2tp kmod-l2tp-ip kmod-l2tp-eth tunneldigger %s"' % (profile_map[self.portLayout], pkgs)
      os.chdir(path)
      os.system(buildString)
      return
    
    if self.wifiDriver in driverPackages:
      self.addPackage(*driverPackages[self.wifiDriver])
    
    if self.portLayout in platformPackages:
      self.addPackage(*platformPackages[self.portLayout])

    self.addPackage('ip', 'olsrd', 'ntpclient', 'wireless-tools', 'kmod-softdog', 'hotplug2', 'cronscripts')
    self.addPackage('kmod-ipt-conntrack', 'iptables-mod-conntrack')
    self.addPackage('kmod-ipt-nat', 'iptables-mod-nat')
    self.addPackage('nodewatcher-core', 'nodewatcher-watchdog', 'nodeupgrade')
    self.addPackage('pv', 'netprofscripts')
    self.addPackage('tc', 'kmod-sched')
    #self.addPackage('kmod-ipv6')
    self.addPackage('dnsmasq')
    
    if self.hasClientSubnet:
      self.addPackage('nullhttpd', 'nodewatcher-clients')
    else:
      # Remove optional packages that should not be installed if this is a router-only
      # configuration (without a client subnet)
      for package in clientOnlyPackages:
        if package in self.packages:
          self.packages.remove(package)

    # Build the image
    buildString = 'make image FILES="../files" PACKAGES="-ppp -ppp-mod-pppoe -nas -hostapd-mini %s"' % " ".join(self.packages)
    print buildString
    os.chdir(path)
    os.system(buildString)
  
  def __overwriteService(self, name):
    path = os.path.join(self.base, 'init.d', name)
    open(path, 'w').close()
    os.chmod(path, 0755)
  
  def __copyTemplate(self, name, destination):
    f = open(destination, 'w')
    f.write(open(os.path.join("templates", name), "r").read())
    f.close()
  
  def __copyServiceTemplate(self, template, name):
    path = os.path.join(self.base, 'init.d', name)
    self.__copyTemplate(template, path)
    os.chmod(path, 0755)

  def __generatePasswords(self):
    from random import choice
    import string
    
    if not self.password:
      raise Exception("No password has been defined!")

    f = open(os.path.join(self.base, 'passwd'), 'w')
    salt = "".join([choice(string.letters + string.digits) for i in xrange(8)])
    f.write('root:%s:0:0:root:/tmp:/bin/ash\n' % crypt.md5crypt(self.password, salt))
    f.write('nobody:*:65534:65534:nobody:/var:/bin/false\n')
    f.close()
  
  def __generateVpnConfig(self, directory):
    os.mkdir(directory)
    
    # Configuration
    f = open(os.path.join(directory, 'wlanlj.conf'), 'w')
    f.write('client\n')
    f.write('proto udp\n')
    f.write('dev tap0\n')
    
    vpnServers = list(self.vpnServer)
    shuffle(vpnServers)
    for vpn in vpnServers:
      f.write('remote %s %s\n' % vpn)

    f.write('resolv-retry infinite\n')
    f.write('nobind\n')
    f.write('fast-io\n')
    f.write('persist-key\n')
    f.write('persist-tun\n')
    f.write('ns-cert-type server\n')
    f.write('comp-lzo\n')
    f.write('daemon\n')
    f.write('auth-user-pass /etc/openvpn/wlanlj-password\n')
    f.write('auth-retry nointeract\n')
    f.write('cipher BF-CBC\n')
    f.write('ifconfig %s 255.255.0.0\n' % self.vpn['ip'])
    f.write('verb 3\n')
    f.write('mute 20\n')
    f.write('user nobody\n')
    f.write('group nogroup\n')
    f.write('ca /etc/openvpn/wlanlj-ca.crt\n')
    f.write('tls-auth /etc/openvpn/wlanlj-ta.key 1\n')
    f.close()
    
    # Password file
    f = open(os.path.join(directory, 'wlanlj-password'), 'w')
    f.write(self.vpn['username'] + "\n")
    f.write(self.vpn['password'] + "\n")
    f.close()

    # MAC setup file
    if self.vpn['mac'] is not None:
      up_path = os.path.join(directory, '../init.d/openvpn-mac')
      f = open(up_path, 'w')
      f.write('#!/bin/sh /etc/rc.common\n')
      f.write('# Must run before OpenVPN\n')
      f.write('START=60\n')
      f.write('STOP=60\n')
      f.write('\n')
      f.write('start() {\n')
      f.write('  # This MAC configuration is used to identify this VPN link for\n')
      f.write('  # traffic policy purpuses. If you change this any policy settings\n')
      f.write('  # set on wlan slovenija gateways will cease to work!\n')
      f.write('  openvpn --mktun --dev tap0\n')
      f.write('  ifconfig tap0 hw ether %s\n' % self.vpn['mac'])
      
      if self.vpn['limit']:
        f.write('\n')
        f.write('  # Setup egress limiting on VPN interface\n')
        f.write('  insmod sch_tbf\n')
        f.write('  tc qdisc add dev tap0 root tbf rate %skbit latency 50ms burst 5120\n' % self.vpn['limit'])

      f.write('}\n')
      f.close()
      os.chmod(up_path, 0755)
      self.addService('S60', 'openvpn-mac')
    
    # Copy the key and CA templates
    self.__copyTemplate("openvpn/ta.key", os.path.join(directory, 'wlanlj-ta.key'))
    self.__copyTemplate("openvpn/ca.crt", os.path.join(directory, 'wlanlj-ca.crt'))
    
    # Add package dependencies
    self.addPackage('kmod-tun', 'zlib', 'libopenssl', 'liblzo', 'openvpn')
  
  def __generateCaptivePortalConfig(self, directory):
    os.mkdir(directory)
    os.mkdir(os.path.join(directory, 'htdocs'))
    
    # Basic configuration (static)
    f = open(os.path.join(directory, 'nodogsplash.conf'), 'w')
    f.write('GatewayInterface %s\n' % (self.wifiIface if not self.lanWifiBridge else self.lanWifiBridgeIface))
    f.write('GatewayName wlan-lj.net\n')
    
    subnetSize = 30
    for subnet in self.subnets:
      if subnet['dhcp'] and subnet['interface'] == (self.wifiIface if not self.lanWifiBridge else self.lanWifiBridgeIface):
        f.write('GatewayIPRange %(subnet)s/%(cidr)s\n' % subnet)
        subnetSize = ipcalc.Network("%(subnet)s/%(cidr)s" % subnet).size() - 2
        break
    
    f.write('ClientIdleTimeout 30\n')
    f.write('ClientForceTimeout 360\n')
    f.write('MaxClients %d\n' % subnetSize)
    f.write('\n')
    f.write('FirewallRuleSet preauthenticated-users {\n')
    
    for dns in self.dns:
      f.write('  FirewallRule allow tcp port 53 to %s\n' % dns)
      f.write('  FirewallRule allow udp port 53 to %s\n' % dns)
      f.write('  FirewallRule allow icmp to %s\n' % dns)
    
    f.write('}\n')
    f.write('\n')
    f.write('EmptyRuleSetPolicy authenticated-users passthrough\n')
    f.write('EmptyRuleSetPolicy users-to-router passthrough\n')
    f.write('EmptyRuleSetPolicy trusted-users passthrough\n')
    f.write('EmptyRuleSetPolicy trusted-users-to-router passthrough\n')
    f.close()
    
    # Add the nodogsplash service and package dependencies
    self.addService('S50', 'nodogsplash')
    self.addPackage('kmod-ipt-ipopt', 'iptables-mod-ipopt')
    self.addPackage('libpthread', 'nodogsplash')
  
  def __generateDnsmasqConfig(self, f):
    f.write('domain-needed\n')
    f.write('bogus-priv\n')
    f.write('localise-queries\n')
    f.write('no-negcache\n')
    f.write('no-resolv\n')

    for dns in self.dns:
      f.write('server=%s\n' % dns)
    
    f.write('dhcp-authoritative\n')
    f.write('dhcp-leasefile=/tmp/dhcp.leases\n')
    f.write('\n')
    
    for subnet in self.subnets:
      if subnet['dhcp'] and subnet['cidr'] <= 28:
        network = ipcalc.Network("%s/%s" % (subnet['subnet'], subnet['cidr']))
        offset = 1
        if ipcalc.IP(self.ip) in network:
          # First few IPs of primary subnet might be used for individual interfaces
          offset += self.usedOlsrIps - 1
        
        subnet['ntp'] = self.ntp[0]
        subnet['rangeStart'] = str(ipcalc.IP(long(network.network()) + offset + 1))
        subnet['rangeEnd'] = str(network.host_last())
        
        f.write('# %(subnet)s/%(cidr)s\n' % subnet)
        f.write('dhcp-range=%(interface)s,%(rangeStart)s,%(rangeEnd)s,%(mask)s,30m\n' % subnet)
        f.write('dhcp-option=%(interface)s,3,%(firstIp)s\n' % subnet)
        f.write('dhcp-option=%(interface)s,6,%(firstIp)s\n' % subnet)
        f.write('dhcp-option=%(interface)s,42,%(ntp)s\n' % subnet)
    
    f.close()
  
  def __generateMiscScript(self, f):
    f.write('#!/bin/sh /etc/rc.common\n')
    f.write('START=46\n')
    f.write('STOP=46\n')
    f.write('start() {\n')
    
    # Prevent the time from reseting to far into the past
    t = datetime.today()
    f.write('\tif [ ! -f /etc/datetime.save ]; then\n')
    f.write('\t  echo -n "%02d%02d%02d%02d%04d" > /etc/datetime.save\n' % (t.month, t.day, t.hour, t.minute, t.year))
    f.write('\tfi\n')
    f.write('\tDT=`cat /etc/datetime.save`\n')
    f.write('\tdate $DT\n')
    f.write('\n')
    
    # Allow txtinfo access when selected
    if 'olsrd-mod-txtinfo' in self.packages:
      f.write('\tiptables -A INPUT -p tcp --dport 2006 -j ACCEPT\n')
      f.write('\n')
    
    # Set boot_wait to on if it is not set
    f.write('\tif [ -x /usr/sbin/nvram ]; then\n')
    f.write('\t\tBOOT_WAIT=`nvram get boot_wait`\n')
    f.write('\t\t[ "$BOOT_WAIT" != "on" ] && {\n')
    f.write('\t\t  nvram set boot_wait=on\n')
    f.write('\t\t  nvram commit\n')
    f.write('\t\t}\n')
    
    # Set boardflags on WHR-HP-G54
    if self.portLayout == 'whr-hp-g54':
      f.write('\tBOARDFLAGS=`nvram get boardflags`\n')
      f.write('\t\t[ "$BOARDFLAGS" != "0x3758" ] && {\n')
      f.write('\t\t  nvram set boardflags=0x3758\n')
      f.write('\t\t  nvram commit\n')
      f.write('\t\t}\n')
    
    f.write('\tfi\n')
    
    f.write('}\n')
    
    f.write('stop() {\n')
    f.write('\tDT=`date +%m%d%H%M%Y`\n')
    f.write('\techo $DT > /etc/datetime.save\n')
    f.write('}\n')
    
    f.close()
    
    if self.openwrtVersion == "old":
      # Copy timezone template
      self.__copyTemplate("general/timezone", os.path.join(self.base, 'TZ'))
  
  def __generateServices(self, directory):
    os.mkdir(directory)
    
    for service in self.services:
      os.symlink("/etc/init.d/%(name)s" % service, os.path.join(directory, "%(priority)s%(name)s" % service))
  
  def __generateOlsrdConfig(self, f):
    # Subnet configuration
    if self.subnets:
      f.write('Hna4\n')
      f.write('{\n')
      
      for subnet in self.subnets:
        if subnet['olsr']:
          f.write('  %(subnet)s  %(mask)s\n' % subnet)
      
      f.write('}\n\n')
    
    # General configuration (static)
    f.write('AllowNoInt yes\n')
    f.write('UseHysteresis no\n')
    f.write('LinkQualityFishEye 0\n')
    f.write('Willingness 3\n')
    f.write('LinkQualityLevel 2\n')
    f.write('LinkQualityAging 0.1\n')
    f.write('LinkQualityAlgorithm "etx_ff"\n')
    f.write('FIBMetric "flat"\n')
    f.write('Pollrate 0.025\n')
    f.write('TcRedundancy 2\n')
    f.write('MprCoverage 3\n')
    f.write('NatThreshold 0.75\n')
    f.write('SmartGateway no\n')
    f.write('MainIp {0}\n'.format(self.ip))
    f.write('SrcIpRoutes yes\n')
    f.write('\n')
    
    # Setup txtinfo plugin when selected
    if 'olsrd-mod-txtinfo' in self.packages:
      f.write('LoadPlugin "olsrd_txtinfo.so.0.1"\n')
      f.write('{\n')
      f.write('  PlParam "accept" "0.0.0.0"\n')
      f.write('}\n')
      f.write('\n')
    
    # Setup actions plugin to trigger a nodewatcher script when the default
    # route is added or removed from the routing table
    if self.hasClientSubnet:
      f.write('LoadPlugin "olsrd_actions.so.0.1"\n')
      f.write('{\n')
      f.write('  PlParam "trigger" "0.0.0.0>/etc/actions.d/olsr_gateway_action"\n')
      for dns in self.dns:
        f.write('  PlParam "trigger" "%s>/etc/actions.d/olsr_dns_action"\n' % dns)
      f.write('}\n')
      f.write('\n')
      
      # Add the olsrd-mod-actions package
      self.addPackage('olsrd-mod-actions')
    
    # General interface configuration (static)
    def interfaceConfiguration(name):
      f.write('Interface "{0}"\n'.format(name))
      f.write('{\n')
      f.write('  IPv4Multicast 255.255.255.255\n')
      f.write('  HelloInterval 5.0\n')
      f.write('  HelloValidityTime 40.0\n')
      f.write('  TcInterval 7.0\n')
      f.write('  TcValidityTime 161.0\n')
      f.write('  MidInterval 18.0\n')
      f.write('  MidValidityTime 324.0\n')
      f.write('  HnaInterval 18.0\n')
      f.write('  HnaValidityTime 324.0\n')
      
      f.write('}\n')
      f.write('\n')
    
    # Additional interface configuration
    for interface in self.interfaces:
      if interface['olsr']:
        interfaceConfiguration(interface['name'])
    
    f.close()
  
  def __generateSystemConfig(self, f):
    # System configuration
    f.write('config system\n')
    f.write('\toption hostname %s\n' % self.hostname)
    f.write('\toption uuid "%s"\n' % self.uuid)
    f.write('\toption timezone "CET-1CEST-2,M3.5.0/02:00:00,M10.5.0/03:00:00"\n')
    f.write('\n')
    f.close()
  
  def __generateNetworkConfig(self, f):
    # VLAN configuration
    layout = portLayouts[self.portLayout]
    
    if isinstance(layout, tuple):
      f.write('#### VLAN configuration\n')
      f.write('config switch %s\n' % ("eth0" if not self.portLayout in switchIds else switchIds[self.portLayout]))
      f.write('\toption vlan0 "%s"\n' % layout[0])
      f.write('\toption vlan1 "%s"\n' % layout[1])
      f.write('\n')
    
    # Loopback configuration (static)
    f.write('#### Loopback configuration\n')
    f.write('config interface loopback\n')
    f.write('\toption ifname "lo"\n')
    f.write('\toption proto static\n')
    f.write('\toption ipaddr 127.0.0.1\n')
    f.write('\toption netmask 255.0.0.0\n')
    f.write('\n')
    
    # LAN configuration
    if self.lanIface:
      # When LAN<->WiFi bridge is enabled, this interface is called 'mesh' as firewall
      # rules for 'mesh' interface should be applied.
      try:
        self.addInterface(
          "lan" if not self.lanWifiBridge else "mesh",
          self.lanIface,
          self.allocateIpForOlsr() if not self.lanWifiBridge else self.ip,
          16,
          olsr = True if not self.lanWifiBridge else False,
          init = True,
          type = None if not self.lanWifiBridge else "bridge"
        )
      except PrimarySubnetTooSmall:
        # Not enough IPs for LAN interface, disable it
        self.lanIface = ''
    
    # Add wireless interface configuration (when no LAN<->WiFi bridge is enabled)
    if not self.lanWifiBridge:
      self.addInterface('mesh', self.wifiIface, self.ip, 16, olsr = (self.nodeType == "adhoc"), init = True)
    else:
      # Transfer all WiFi subnets to bridge interface
      for subnet in self.subnets:
        if subnet['interface'] == self.wifiIface:
          subnet['interface'] = self.lanWifiBridgeIface
      
      # Create a virtual bridge interface (for OLSR configuration)
      self.addInterface("mesh", self.lanWifiBridgeIface, self.ip, 16, olsr = True, init = False)
    
    # Other interfaces configuration
    for interface in self.interfaces:
      if interface['init']:
        f.write('config interface %(id)s\n' % interface)
        f.write('\toption ifname "%(name)s"\n' % interface)
        if interface['type']:
          f.write('\toption type %(type)s\n' % interface)
        
        if interface['ip']:
          f.write('\toption proto static\n')
          f.write('\toption ipaddr %(ip)s\n' % interface)
          f.write('\toption netmask %(mask)s\n' % interface)
          
          if interface['gateway']:
            f.write('\toption gateway %(gateway)s\n' % interface)
        else:
          f.write('\toption proto dhcp\n')
        
        f.write('\n')
        
        # Set a fallback IP on WAN interface
        if interface['id'] == 'wan':
          if self.openwrtVersion == "old":
            f.write('config interface fallback\n')
            f.write('\toption ifname "%(name)s:0"\n' % interface)
          else:
            f.write('config alias wanfallback\n')
            f.write('\toption interface wan\n')
          
          f.write('\toption proto static\n')
          f.write('\toption ipaddr 169.254.189.120\n')
          f.write('\toption netmask 255.255.0.0\n')
          f.write('\n')
    
    # VPN route override
    if self.vpn:
      idx = 0
      wanIface = self.getInterface('wan')
      
      for vpn in self.vpnServer:
        f.write('config route vpn%d\n' % idx)
        f.write('\toption interface wan\n')
        f.write('\toption target %s\n' % vpn[0])
        
        # If WAN obtains IP via DHCP, set gateway to 'auto'
        if wanIface['gateway'] == None:
          f.write('\toption gateway auto\n')
        else:
          f.write('\toption gateway %s\n' % wanIface['gateway'])
        
        f.write('\toption metric 0\n')
        f.write('\toption table wan\n')
        f.write('\n')
        idx += 1
    
    # WAN stuff
    if self.hasInterface('wan'):
      f.write('config route wannetwork\n')
      f.write('\toption interface wan\n')
      f.write('\toption target network\n')
      f.write('\toption metric 0\n')
      f.write('\toption table wan\n')
      f.write('\n')
      
      f.write('config route wandefault\n')
      f.write('\toption interface wan\n')
      f.write('\toption target default\n')
      f.write('\toption gateway auto\n')
      f.write('\toption metric 0\n')
      f.write('\toption table wan\n')
      f.write('\n')
    
    # Subnets
    if self.subnets:
      f.write('#### Subnet configuration\n')
      virtualIfaceIds = {}
      
      for subnetId, subnet in enumerate(self.subnets):
        # Ignore small subnets
        if subnet['cidr'] >= 29:
          continue
        
        # Generate subnet configuration
        ifaceId = virtualIfaceIds.setdefault(subnet['interface'], 0)
        virtualIfaceIds[subnet['interface']] += 1
        
        if self.openwrtVersion == "old":
          f.write('config interface subnet%d\n' % subnetId)
          f.write('\toption ifname "%s:%d"\n' % (subnet['interface'], ifaceId))
        else:
          f.write('config alias subnet%d\n' % subnetId)
          f.write('\toption interface %(id)s\n' % self.getInterfaceByName(subnet['interface']))
        
        f.write('\toption proto static\n')
        f.write('\toption ipaddr %(firstIp)s\n' % subnet)
        f.write('\toption netmask %(mask)s\n' % subnet)
        f.write('\n')
    
    f.close()
  
  def __generateWirelessConfig(self, f):
    # Wifi device configuration
    f.write('config wifi-device %s\n' % self.wifiVirtualIface)
    f.write('\toption type %s\n' % self.wifiDriver)
    f.write('\toption channel %s\n' % self.wifiChannel)
    f.write('\toption diversity %s\n' % self.wifiAntDiv)
    f.write('\toption rxantenna %s\n' % self.wifiRxAnt)
    f.write('\toption txantenna %s\n' % self.wifiTxAnt)
    f.write('\n')
    
    # Wifi interface configuration
    f.write('config wifi-iface\n')
    f.write('\toption device %s\n' % self.wifiVirtualIface)
    f.write('\toption network mesh\n')
    f.write('\toption mode %s\n' % self.nodeType)
    f.write('\toption ssid %s\n' % self.ssid)
    
    if self.nodeType == "adhoc":
      f.write('\toption bssid %s\n' % self.bssid)
    
    f.write('\toption hidden 0\n')
    f.write('\toption bgscan 0\n')
    f.write('\toption encryption none\n')
    f.write('\toption mcast_rate 5500\n')
    f.write('\n')
    
    f.close()
  
  def __generateNtpClientConfig(self, f):
    # Ntpclient configuration
    for ntp in self.ntp:
      if self.openwrtVersion == "old":
        f.write('config ntpclient\n')
        f.write('\toption count "1"\n')
      else:
        f.write('config ntpserver\n')
      
      f.write('\toption hostname "%s"\n' % ntp)
      f.write('\toption port "123"\n')
      f.write('\n')
    
    if self.openwrtVersion == "new":
      f.write('config ntpdrift\n')
      f.write('\toption freq 0\n')
      f.write('\n')
      
      f.write('config ntpclient\n')
      f.write('\toption interval 3600\n')
      f.write('\n')
    
    f.close()
    
    # Add ntpclient service
    self.addService('S80', 'ntpclient')
